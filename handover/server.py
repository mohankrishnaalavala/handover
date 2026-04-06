"""
handover/server.py

Local HTTP bridge for the handover browser extension.
See Phase 3 roadmap — handover serve.

Endpoints:
  GET  /health   — liveness check, returns version
  POST /handover — run full pipeline from raw conversation JSON
  POST /config   — update output_dir and no_llm settings

Port 7437 spells H-A-N-D on a phone keypad.
"""

from __future__ import annotations

import json
import socketserver
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from handover import __version__
from handover import summarizer as _summarizer
from handover.generator import Generator
from handover.models import HandoverAPIError
from handover.parsers import ADAPTER_REGISTRY, get_parser


class _ServerConfig:
    """Mutable server configuration updated via POST /config."""

    def __init__(self) -> None:
        self.output_dir: str = str(Path.cwd())
        self.no_llm: bool = False
        self._lock: threading.Lock = threading.Lock()

    def update(self, output_dir: str | None, no_llm: bool | None) -> None:
        """Thread-safe config update."""
        with self._lock:
            if output_dir is not None:
                self.output_dir = output_dir
            if no_llm is not None:
                self.no_llm = no_llm

    def snapshot(self) -> tuple[str, bool]:
        """Return a consistent (output_dir, no_llm) snapshot."""
        with self._lock:
            return self.output_dir, self.no_llm


_config = _ServerConfig()

_VALID_SOURCES = set(ADAPTER_REGISTRY.keys())


class HandoverHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the handover bridge server."""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Suppress per-request access logs; errors still surface."""

    # ------------------------------------------------------------------
    # CORS helpers
    # ------------------------------------------------------------------

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------
    # Verb handlers
    # ------------------------------------------------------------------

    def do_OPTIONS(self) -> None:  # CORS preflight
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, {"status": "ok", "version": __version__})
        else:
            self._send_json(404, {"status": "error", "message": "Not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length)

        try:
            data: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json(400, {"status": "error", "message": "Request body must be valid JSON"})
            return

        if path == "/handover":
            self._handle_handover(data)
        elif path == "/config":
            self._handle_config(data)
        else:
            self._send_json(404, {"status": "error", "message": "Not found"})

    # ------------------------------------------------------------------
    # Endpoint implementations
    # ------------------------------------------------------------------

    def _handle_config(self, data: dict[str, Any]) -> None:
        """Update server configuration."""
        output_dir = data.get("output_dir")
        no_llm_raw = data.get("no_llm")
        no_llm = bool(no_llm_raw) if no_llm_raw is not None else None
        _config.update(output_dir=output_dir, no_llm=no_llm)
        self._send_json(200, {"status": "ok"})

    def _handle_handover(self, data: dict[str, Any]) -> None:
        """Run the full parse → summarize → generate pipeline."""
        source: str = data.get("source", "claude")
        conversation = data.get("conversation")

        if source not in _VALID_SOURCES:
            valid = ", ".join(sorted(_VALID_SOURCES))
            self._send_json(
                400,
                {"status": "error", "message": f"Unknown source '{source}'. Valid: {valid}"},
            )
            return

        if not conversation:
            self._send_json(400, {"status": "error", "message": "'conversation' field is required"})
            return

        output_dir, no_llm = _config.snapshot()
        tmp_path: Path | None = None

        try:
            # Write conversation data to a temp file for the parser.
            # Wrap in a list so ClaudeParser treats it as a single-conversation
            # JSON export — this preserves name, uuid, and chat_messages.
            suffix = ".json"
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=suffix, delete=False, encoding="utf-8"
            ) as tmp:
                json.dump([conversation], tmp)
                tmp_path = Path(tmp.name)

            # chatgpt.js pre-processes API data into claude-compatible format
            # ({uuid, name, chat_messages}) rather than the native mapping format.
            # Use ClaudeParser when the extension already did the conversion.
            parse_as = (
                "claude"
                if source == "chatgpt" and "chat_messages" in conversation
                else source
            )
            parser = get_parser(parse_as)
            messages = parser.parse(tmp_path)

            if not messages:
                self._send_json(
                    400, {"status": "error", "message": "No messages found in conversation"}
                )
                return

            context = _summarizer.summarize(messages, use_llm=not no_llm)
            context.source = source
            context.conversation_title = conversation.get("name", "")
            context.conversation_id = conversation.get("uuid") or conversation.get("id")
            context.source_version = "extension-live"

            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)

            gen = Generator()
            gen.generate(context, out, dry_run=False)

            self._send_json(
                200,
                {
                    "status": "ok",
                    "claude_md": str(out / "CLAUDE.md"),
                    "plan_md": str(out / "PLAN.md"),
                },
            )

        except HandoverAPIError as exc:
            self._send_json(500, {"status": "error", "message": str(exc)})
        except (ValueError, FileNotFoundError) as exc:
            self._send_json(400, {"status": "error", "message": str(exc)})
        finally:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)


class HandoverServer(socketserver.ThreadingMixIn, HTTPServer):
    """Threaded HTTP server — each request handled in its own thread."""

    daemon_threads = True  # threads die with the main process


def run_server(port: int, output_dir: str, no_llm: bool) -> None:
    """
    Start the handover HTTP bridge and block until Ctrl-C.

    Args:
        port: TCP port to listen on (default 7437).
        output_dir: Directory where CLAUDE.md + PLAN.md are written.
        no_llm: If True, use heuristic extraction only.
    """
    _config.update(output_dir=output_dir, no_llm=no_llm)
    server = HandoverServer(("127.0.0.1", port), HandoverHandler)
    print(f"handover serve  →  http://localhost:{port}")
    print(f"Output dir      →  {output_dir}")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
