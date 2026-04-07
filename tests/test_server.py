"""
tests/test_server.py

Tests for the handover HTTP bridge server (handover/server.py).
All pipeline calls (parser, summarizer, generator) are mocked.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from handover.server import HandoverHandler, HandoverServer, _config

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def server() -> Any:
    """
    Start a HandoverServer on an OS-assigned free port in a daemon thread.
    Yields (server_instance, port).  Shuts down after the test.
    """
    s = HandoverServer(("127.0.0.1", 0), HandoverHandler)
    port: int = s.server_address[1]
    t = threading.Thread(target=s.serve_forever, daemon=True)
    t.start()
    yield s, port
    s.shutdown()


def _get(port: int, path: str) -> tuple[int, dict[str, Any]]:
    """GET helper — returns (status, parsed_json), handles HTTP errors."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}") as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _post(port: int, path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """POST helper — returns (status, parsed_json), handles HTTP errors."""
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_returns_200(server: Any) -> None:
    _, port = server
    status, data = _get(port, "/health")
    assert status == 200
    assert data["status"] == "ok"
    assert "version" in data


def test_health_has_cors_header(server: Any) -> None:
    _, port = server
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as resp:
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"


def test_unknown_get_returns_404(server: Any) -> None:
    _, port = server
    status, data = _get(port, "/nonexistent")
    assert status == 404
    assert data["status"] == "error"


# ---------------------------------------------------------------------------
# /config
# ---------------------------------------------------------------------------


def test_config_updates_output_dir(server: Any) -> None:
    _, port = server
    status, data = _post(port, "/config", {"output_dir": "/tmp/test-output"})
    assert status == 200
    assert data["status"] == "ok"
    assert _config.snapshot()[0] == "/tmp/test-output"


def test_config_updates_no_llm(server: Any) -> None:
    _, port = server
    _post(port, "/config", {"no_llm": True})
    assert _config.snapshot()[1] is True
    _post(port, "/config", {"no_llm": False})
    assert _config.snapshot()[1] is False


def test_config_partial_update_preserves_other_fields(server: Any) -> None:
    _, port = server
    _post(port, "/config", {"output_dir": "/tmp/partial"})
    original_no_llm = _config.snapshot()[1]
    _post(port, "/config", {"no_llm": True})
    assert _config.snapshot()[0] == "/tmp/partial"
    assert _config.snapshot()[1] is True
    # cleanup
    _post(port, "/config", {"no_llm": original_no_llm})


# ---------------------------------------------------------------------------
# /handover — success path
# ---------------------------------------------------------------------------


def _mock_conversation() -> dict[str, Any]:
    return {
        "uuid": "test-uuid",
        "name": "Test Conversation",
        "chat_messages": [
            {"sender": "human", "text": "Build a REST API"},
            {"sender": "assistant", "text": "Sure, here's how."},
        ],
    }


def test_handover_success(server: Any, tmp_path: Path) -> None:
    _, port = server
    _post(port, "/config", {"output_dir": str(tmp_path), "no_llm": True})

    mock_messages = [MagicMock()]
    mock_context = MagicMock()
    mock_context.source = ""

    with (
        patch("handover.server.get_parser") as mock_get_parser,
        patch("handover.server._summarizer.summarize", return_value=mock_context),
        patch("handover.server.Generator") as mock_gen_cls,
    ):
        mock_parser = MagicMock()
        mock_parser.parse.return_value = mock_messages
        mock_get_parser.return_value = mock_parser

        mock_gen = MagicMock()
        mock_gen_cls.return_value = mock_gen

        status, data = _post(
            port,
            "/handover",
            {"source": "claude", "conversation": _mock_conversation()},
        )

    assert status == 200
    assert data["status"] == "ok"
    assert "claude_md" in data
    assert "plan_md" in data
    assert str(tmp_path) in data["claude_md"]


def test_handover_sets_source_on_context(server: Any, tmp_path: Path) -> None:
    _, port = server
    _post(port, "/config", {"output_dir": str(tmp_path), "no_llm": True})

    mock_context = MagicMock()
    mock_context.source = ""

    with (
        patch("handover.server.get_parser") as mock_get_parser,
        patch("handover.server._summarizer.summarize", return_value=mock_context),
        patch("handover.server.Generator") as mock_gen_cls,
    ):
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [MagicMock()]
        mock_get_parser.return_value = mock_parser
        mock_gen_cls.return_value = MagicMock()

        _post(
            port,
            "/handover",
            {"source": "chatgpt", "conversation": _mock_conversation()},
        )

    assert mock_context.source == "chatgpt"


def test_handover_chatgpt_chat_messages_uses_claude_parser(server: Any, tmp_path: Path) -> None:
    """Extension sends chatgpt source with pre-processed chat_messages format.
    Server must use ClaudeParser (not ChatGPTParser) to avoid 'mapping' error."""
    _, port = server
    _post(port, "/config", {"output_dir": str(tmp_path), "no_llm": True})

    mock_context = MagicMock()
    mock_context.source = ""

    with (
        patch("handover.server.get_parser") as mock_get_parser,
        patch("handover.server._summarizer.summarize", return_value=mock_context),
        patch("handover.server.Generator") as mock_gen_cls,
    ):
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [MagicMock()]
        mock_get_parser.return_value = mock_parser
        mock_gen_cls.return_value = MagicMock()

        status, data = _post(
            port,
            "/handover",
            {"source": "chatgpt", "conversation": _mock_conversation()},
        )

    assert status == 200
    # Parser must be requested as "claude" because extension pre-processed the data
    mock_get_parser.assert_called_once_with("claude")
    # But the source label on the context stays "chatgpt"
    assert mock_context.source == "chatgpt"


# ---------------------------------------------------------------------------
# /handover — error paths
# ---------------------------------------------------------------------------


def test_handover_missing_conversation_field(server: Any) -> None:
    _, port = server
    status, data = _post(port, "/handover", {"source": "claude"})
    assert status == 400
    assert data["status"] == "error"
    assert "conversation" in data["message"]


def test_handover_unknown_source(server: Any) -> None:
    _, port = server
    status, data = _post(port, "/handover", {"source": "unknown_ai", "conversation": {"x": 1}})
    assert status == 400
    assert data["status"] == "error"
    assert "unknown_ai" in data["message"]


def test_handover_invalid_json_body(server: Any) -> None:
    _, port = server
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/handover",
        data=b"not json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            status = resp.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    assert status == 400


def test_handover_no_messages_found(server: Any, tmp_path: Path) -> None:
    _, port = server
    _post(port, "/config", {"output_dir": str(tmp_path), "no_llm": True})

    with patch("handover.server.get_parser") as mock_get_parser:
        mock_parser = MagicMock()
        mock_parser.parse.return_value = []
        mock_get_parser.return_value = mock_parser

        status, data = _post(
            port,
            "/handover",
            {"source": "claude", "conversation": _mock_conversation()},
        )

    assert status == 400
    assert data["status"] == "error"


def test_handover_api_error_returns_500(server: Any, tmp_path: Path) -> None:
    _, port = server
    _post(port, "/config", {"output_dir": str(tmp_path), "no_llm": False})

    from handover.models import HandoverAPIError

    with (
        patch("handover.server.get_parser") as mock_get_parser,
        patch(
            "handover.server._summarizer.summarize",
            side_effect=HandoverAPIError("API quota exceeded"),
        ),
    ):
        mock_parser = MagicMock()
        mock_parser.parse.return_value = [MagicMock()]
        mock_get_parser.return_value = mock_parser

        status, data = _post(
            port,
            "/handover",
            {"source": "claude", "conversation": _mock_conversation()},
        )

    assert status == 500
    assert data["status"] == "error"
    assert "API quota exceeded" in data["message"]


# ---------------------------------------------------------------------------
# CORS preflight
# ---------------------------------------------------------------------------


def test_options_preflight(server: Any) -> None:
    _, port = server
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/handover",
        method="OPTIONS",
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 204
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")


# ---------------------------------------------------------------------------
# CLI integration — serve subcommand wiring
# ---------------------------------------------------------------------------


def test_serve_command_exists() -> None:
    from click.testing import CliRunner

    from handover.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["serve", "--help"])
    assert result.exit_code == 0
    assert "7437" in result.output  # default port in help text


# ---------------------------------------------------------------------------
# /save-chat
# ---------------------------------------------------------------------------


def _save_chat_payload() -> dict[str, Any]:
    """Minimal payload for POST /save-chat."""
    return {
        "source": "chatgpt",
        "conversation": {
            "uuid": "test-conv-abc123",
            "name": "Test Conversation",
            "chat_messages": [
                {"sender": "human", "text": "Hello"},
                {"sender": "assistant", "text": "Hi there!"},
            ],
        },
    }


def test_save_chat_writes_json_file(server: Any, tmp_path: Path) -> None:
    _, port = server
    _post(port, "/config", {"output_dir": str(tmp_path)})
    status, data = _post(port, "/save-chat", _save_chat_payload())
    assert status == 200, data
    assert data["status"] == "ok"
    saved = tmp_path / "handover-chat-test-conv-abc123.json"
    assert saved.exists()


def test_save_chat_saved_file_is_valid_array(server: Any, tmp_path: Path) -> None:
    _, port = server
    _post(port, "/config", {"output_dir": str(tmp_path)})
    _post(port, "/save-chat", _save_chat_payload())
    saved = tmp_path / "handover-chat-test-conv-abc123.json"
    parsed = json.loads(saved.read_text())
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["uuid"] == "test-conv-abc123"


def test_save_chat_returns_path_and_cli_hint(server: Any, tmp_path: Path) -> None:
    _, port = server
    _post(port, "/config", {"output_dir": str(tmp_path)})
    status, data = _post(port, "/save-chat", _save_chat_payload())
    assert status == 200
    assert "path" in data
    assert "cli_hint" in data
    assert "handover-chat-test-conv-abc123.json" in data["path"]
    assert "handover --input" in data["cli_hint"]


def test_save_chat_missing_conversation_returns_400(server: Any) -> None:
    _, port = server
    status, data = _post(port, "/save-chat", {"source": "chatgpt"})
    assert status == 400
    assert data["status"] == "error"
    assert "conversation" in data["message"]


def test_save_chat_does_not_run_pipeline(server: Any, tmp_path: Path) -> None:
    """Verify that /save-chat writes JSON but does NOT generate CLAUDE.md or PLAN.md."""
    _, port = server
    _post(port, "/config", {"output_dir": str(tmp_path)})
    _post(port, "/save-chat", _save_chat_payload())
    assert not (tmp_path / "CLAUDE.md").exists()
    assert not (tmp_path / "PLAN.md").exists()
    assert (tmp_path / "handover-chat-test-conv-abc123.json").exists()
