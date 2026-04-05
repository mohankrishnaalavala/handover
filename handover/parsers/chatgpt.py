"""
handover/parsers/chatgpt.py

Parser adapter for ChatGPT chat exports (conversations.json).

Export format: a JSON array where each element is a conversation object
containing a `mapping` dict. Each mapping node has:
  {id, message: {author: {role}, content: {parts: [...]}, create_time}, parent, children}

Messages are stored as a tree; we depth-first-walk the children list to
reconstruct the conversation in chronological order.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from handover.models import ConversationMessage
from handover.parsers.base import BaseParser

_SKIP_ROLES = {"system", "tool"}


class ChatGPTParser(BaseParser):
    """Parser for ChatGPT `conversations.json` exports."""

    source_name = "chatgpt"

    def parse(self, file_path: Path) -> list[ConversationMessage]:
        """
        Parse a ChatGPT conversations.json export.

        Picks the first conversation in the array. Use parse_by_id() or
        list_conversations() to select a specific conversation.

        Args:
            file_path: Path to conversations.json.

        Returns:
            List of ConversationMessage in chronological order.

        Raises:
            ValueError: If the file contains no valid conversations.
            FileNotFoundError: If the file does not exist.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Export file not found: {file_path}")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not data:
            raise ValueError(f"Expected a non-empty JSON array in {file_path.name}")

        return self._walk_conversation(data[0], file_path.name)

    def parse_by_id(self, path: Path, conversation_id: str) -> list[ConversationMessage]:
        """
        Parse a single conversation by its ID.

        Args:
            path: Path to conversations.json.
            conversation_id: The conversation UUID to extract.

        Returns:
            List of ConversationMessage in chronological order.

        Raises:
            ValueError: If no conversation with that ID is found.
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        for conv in data:
            if conv.get("id") == conversation_id:
                return self._walk_conversation(conv, path.name)
        raise ValueError(f"No conversation with id={conversation_id!r} found in {path.name}")

    def list_conversations(self, path: Path) -> list[dict[str, str]]:
        """
        Return metadata for all conversations in a ChatGPT export.

        Args:
            path: Path to conversations.json.

        Returns:
            List of dicts with keys: id, title, date.
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        result = []
        for conv in data:
            raw_date = conv.get("create_time", "")
            date_str = _fmt_unix_ts(raw_date) if raw_date else ""
            result.append(
                {
                    "id": conv.get("id", ""),
                    "title": conv.get("title", "Untitled"),
                    "date": date_str,
                }
            )
        return result

    def detect_format_version(self, file_path: Path) -> str:
        return "chatgpt-json v1.0"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _walk_conversation(
        self, conv: dict[str, object], filename: str
    ) -> list[ConversationMessage]:
        """Depth-first walk of the mapping tree to produce ordered messages."""
        mapping: dict[str, dict[str, object]] = conv.get("mapping", {})  # type: ignore[assignment]
        if not mapping:
            raise ValueError(f"No 'mapping' key found in conversation from {filename}")

        # Find the root node (node whose parent is not in mapping, or is None)
        mapping_ids = set(mapping.keys())
        root_id: str | None = None
        for node_id, node in mapping.items():
            parent = node.get("parent")
            if parent is None or parent not in mapping_ids:
                root_id = node_id
                break

        if root_id is None:
            # Fallback: pick the node with no parent key
            for node_id, node in mapping.items():
                if "parent" not in node:
                    root_id = node_id
                    break

        if root_id is None:
            return []

        messages: list[ConversationMessage] = []
        self._dfs(root_id, mapping, messages)
        return messages

    def _dfs(
        self,
        node_id: str,
        mapping: dict[str, dict[str, object]],
        messages: list[ConversationMessage],
    ) -> None:
        """Recursive depth-first traversal."""
        node = mapping.get(node_id)
        if node is None:
            return

        message: dict[str, object] | None = node.get("message")  # type: ignore[assignment]
        if message:
            author: dict[str, object] = message.get("author") or {}  # type: ignore[assignment]
            role = str(author.get("role", ""))
            content_obj: dict[str, object] = message.get("content") or {}  # type: ignore[assignment]
            parts: list[object] = content_obj.get("parts") or []  # type: ignore[assignment]
            text = "\n".join(str(p) for p in parts if p)

            if role not in _SKIP_ROLES and text:
                norm_role = "user" if role == "user" else "assistant"
                ts = message.get("create_time")
                timestamp = _fmt_unix_ts(ts) if ts else None
                messages.append(
                    ConversationMessage(
                        role=norm_role,
                        content=text,
                        timestamp=timestamp,
                    )
                )

        children: list[str] = node.get("children", [])  # type: ignore[assignment]
        for child_id in children:
            self._dfs(child_id, mapping, messages)


def _fmt_unix_ts(ts: object) -> str:
    """Convert a Unix float timestamp to an ISO-8601 string."""
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC).isoformat()  # type: ignore[arg-type]
    except (TypeError, ValueError, OSError):
        return str(ts)
