"""
handover/parsers/claude.py

Adapter for Claude.ai chat exports.
See PRD Section 9 — Input Formats Supported (Phase 1).

Supports:
  - Claude.ai bulk export (.jsonl) — one JSON object per line
  - Claude.ai single-conversation export (.json) — via browser extension
  - Claude.ai single-conversation export (.md) — via browser extension

Format auto-detection is based on file extension and content sniffing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from handover.models import ConversationMessage
from handover.parsers.base import BaseParser

# Matches **Human:** or **Assistant:** at the start of a line
_MD_HEADER_RE = re.compile(r"^\*\*(Human|Assistant):\*\*\s*", re.MULTILINE)

_ROLE_MAP = {
    "human": "user",
    "user": "user",
    "assistant": "assistant",
}


def _normalize_role(raw_role: str) -> str:
    """Map raw role strings from any Claude export format to 'user' or 'assistant'."""
    normalized = _ROLE_MAP.get(raw_role.lower())
    if normalized is None:
        raise ValueError(f"Unknown role {raw_role!r} in Claude export")
    return normalized


def _messages_from_raw(raw_messages: list[dict]) -> list[ConversationMessage]:  # type: ignore[type-arg]
    """
    Convert a list of raw message dicts (any Claude format variant) to ConversationMessage.

    Handles both format variants:
      v1: {"sender": "human", "text": "...", "created_at": "..."}
      v2: {"role": "user", "content": "...", "created_at": "..."}
    """
    messages = []
    for raw in raw_messages:
        role = _normalize_role(raw.get("sender") or raw.get("role") or "")
        content = raw.get("text") or raw.get("content") or ""
        if not content:
            continue
        messages.append(
            ConversationMessage(
                role=role,
                content=content,
                timestamp=raw.get("created_at"),
                message_id=raw.get("uuid") or raw.get("id"),
            )
        )
    # Sort chronologically; messages without timestamps retain their original order
    messages.sort(key=lambda m: m.timestamp or "")
    return messages


class ClaudeParser(BaseParser):
    """
    Parse Claude.ai conversation exports into ConversationMessage objects.

    Handles bulk JSONL exports (Settings → Privacy → Export Data) and
    single-conversation JSON exports (Claude Conversation Exporter extension).
    """

    source_name = "claude"

    def parse(self, file_path: Path) -> list[ConversationMessage]:
        """
        Parse a Claude export file and return normalized messages.

        Args:
            file_path: Path to the .json, .jsonl, or .md export file.

        Returns:
            List of ConversationMessage objects in chronological order.

        Raises:
            ValueError: If the file format is unrecognized.
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Export file not found: {path}")

        suffix = path.suffix.lower()

        if suffix == ".jsonl":
            return self._parse_bulk_jsonl(path)
        elif suffix == ".json":
            return self._parse_single_json(path)
        elif suffix == ".md":
            return self._parse_markdown(path)
        else:
            raise ValueError(
                f"Unsupported file format: {suffix}. Supported formats: .json, .jsonl, .md"
            )

    def _parse_single_json(self, path: Path) -> list[ConversationMessage]:
        """Parse a single-conversation JSON export from the browser extension,
        or the first conversation from a JSON array bulk export."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}") from e

        # Claude Settings → Export Data gives a JSON array (not JSONL)
        if isinstance(data, list):
            if not data:
                return []
            return _messages_from_raw(data[0].get("chat_messages", []))

        raw_messages = data.get("chat_messages") or data.get("messages") or []
        return _messages_from_raw(raw_messages)

    def _parse_bulk_jsonl(
        self, path: Path, conversation_id: str | None = None
    ) -> list[ConversationMessage]:
        """
        Parse a bulk JSONL export from Claude Settings → Privacy → Export Data.

        Args:
            path: Path to the .jsonl file.
            conversation_id: If given, return messages from that conversation only.
                             If None, return messages from the first conversation.
        """
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSONL line in {path}: {e}") from e

                if conversation_id is None or obj.get("uuid") == conversation_id:
                    return _messages_from_raw(obj.get("chat_messages", []))

        return []

    def _parse_markdown(self, path: Path) -> list[ConversationMessage]:
        """Parse a Markdown export from the browser extension."""
        text = path.read_text(encoding="utf-8")

        # Split on **Human:** / **Assistant:** headers
        parts = _MD_HEADER_RE.split(text)
        # parts = [preamble, role1, content1, role2, content2, ...]
        # Skip preamble (index 0), then iterate in pairs
        messages = []
        for i in range(1, len(parts) - 1, 2):
            raw_role = parts[i]
            content = parts[i + 1].strip()
            if not content:
                continue
            role = _normalize_role(raw_role)
            messages.append(ConversationMessage(role=role, content=content))
        return messages

    def list_conversations(self, path: Path) -> list[dict]:  # type: ignore[type-arg]
        """
        List all conversations in a bulk export (JSONL or JSON array).

        Used by the `handover list` subcommand.

        Args:
            path: Path to the bulk export file (.jsonl or .json array).

        Returns:
            List of dicts with keys: id, title, date.
        """
        suffix = path.suffix.lower()

        # JSON array format — real Claude Settings → Export Data output
        if suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {path}: {e}") from e
            if not isinstance(data, list):
                # Single-conversation JSON — treat as one conversation
                return [
                    {
                        "id": data.get("uuid", ""),
                        "title": data.get("name", "(untitled)"),
                        "date": data.get("created_at", ""),
                    }
                ]
            return [
                {
                    "id": obj.get("uuid", ""),
                    "title": obj.get("name", "(untitled)"),
                    "date": obj.get("created_at", ""),
                }
                for obj in data
            ]

        # JSONL format — one JSON object per line
        result = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSONL line in {path}: {e}") from e
                result.append(
                    {
                        "id": obj.get("uuid", ""),
                        "title": obj.get("name", "(untitled)"),
                        "date": obj.get("created_at", ""),
                    }
                )
        return result

    def parse_by_id(self, path: Path, conversation_id: str) -> list[ConversationMessage]:
        """
        Parse a single conversation by its UUID.

        Handles both JSONL and JSON array bulk exports.
        """
        suffix = path.suffix.lower()

        if suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in {path}: {e}") from e
            if isinstance(data, list):
                for obj in data:
                    if obj.get("uuid") == conversation_id:
                        return _messages_from_raw(obj.get("chat_messages", []))
                return []
            return _messages_from_raw(data.get("chat_messages", []))

        # JSONL — delegate to existing helper
        return self._parse_bulk_jsonl(path, conversation_id=conversation_id)

    def detect_format_version(self, file_path: Path) -> str:
        """
        Detect the Claude export format version.

        Returns:
            Version string e.g. "single-json v1.0", "single-json v2.0", or "bulk-jsonl v1.0".
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".jsonl":
            return "bulk-jsonl v1.0"

        if suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return "unknown"
            # Real Claude bulk export: JSON array of conversations
            if isinstance(data, list):
                return "bulk-json v1.0"
            # v1: {"uuid": ..., "chat_messages": [...], "sender": ...}
            # v2: {"id": ..., "messages": [...], "role": ...}
            if "chat_messages" in data:
                return "single-json v1.0"
            if "messages" in data:
                return "single-json v2.0"

        if suffix == ".md":
            return "markdown v1.0"

        return "unknown"
