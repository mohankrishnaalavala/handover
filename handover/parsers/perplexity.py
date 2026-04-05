"""
handover/parsers/perplexity.py

Parser adapter for Perplexity AI chat exports.

Export format: a JSON object with a top-level "conversations" array.
Each conversation has: id, title, messages[].
Each message has: role ("user"|"assistant"), content (str), timestamp (ISO str),
and optionally sources (list of {title, url}).

Sources are appended as a synthetic assistant message so they survive into
the CLAUDE.md / PLAN.md artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

from handover.models import ConversationMessage
from handover.parsers.base import BaseParser


class PerplexityParser(BaseParser):
    """Parser for Perplexity AI conversation exports."""

    source_name = "perplexity"

    def parse(self, file_path: Path) -> list[ConversationMessage]:
        """
        Parse a Perplexity export, returning the first conversation found.

        Args:
            file_path: Path to the Perplexity export JSON file.

        Returns:
            List of ConversationMessage in chronological order.

        Raises:
            ValueError: If the file does not contain 'conversations'.
            FileNotFoundError: If the file does not exist.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Export file not found: {file_path}")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        conversations = data.get("conversations")
        if conversations is None:
            raise ValueError(
                f"Expected 'conversations' key in {file_path.name}. Is this a Perplexity export?"
            )
        if not conversations:
            return []

        return self._parse_conversation(conversations[0])

    def parse_by_id(self, path: Path, conversation_id: str) -> list[ConversationMessage]:
        """
        Parse a single Perplexity conversation by its ID.

        Args:
            path: Path to the export JSON file.
            conversation_id: The conversation ID to extract.

        Returns:
            List of ConversationMessage in chronological order.

        Raises:
            ValueError: If no conversation with that ID is found.
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        conversations = data.get("conversations", [])
        for conv in conversations:
            if conv.get("id") == conversation_id:
                return self._parse_conversation(conv)
        raise ValueError(f"No conversation with id={conversation_id!r} found in {path.name}")

    def list_conversations(self, path: Path) -> list[dict[str, str]]:
        """
        Return metadata for all conversations in a Perplexity export.

        Args:
            path: Path to the export JSON file.

        Returns:
            List of dicts with keys: id, title, date.
        """
        data = json.loads(path.read_text(encoding="utf-8"))
        conversations = data.get("conversations", [])
        result = []
        for conv in conversations:
            messages = conv.get("messages") or []
            date = messages[0].get("timestamp", "") if messages else ""
            result.append(
                {
                    "id": conv.get("id", ""),
                    "title": conv.get("title", "Untitled"),
                    "date": date,
                }
            )
        return result

    def detect_format_version(self, file_path: Path) -> str:
        return "perplexity-json v1.0"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _parse_conversation(self, conv: dict[str, object]) -> list[ConversationMessage]:
        """Convert a single conversation dict into ConversationMessage objects."""
        messages: list[ConversationMessage] = []
        raw_messages: list[dict[str, object]] = conv.get("messages", [])  # type: ignore[assignment]

        for msg in raw_messages:
            role = str(msg.get("role", ""))
            content = str(msg.get("content", "")).strip()
            timestamp = str(msg.get("timestamp", "")) or None
            if not content:
                continue

            norm_role = "user" if role == "user" else "assistant"
            messages.append(
                ConversationMessage(role=norm_role, content=content, timestamp=timestamp)
            )

            # Append sources as a synthetic assistant message
            sources: list[dict[str, str]] = msg.get("sources", [])  # type: ignore[assignment]
            if sources and norm_role == "assistant":
                lines = ["Sources:"]
                for src in sources:
                    src_title = src.get("title", "Link")
                    src_url = src.get("url", "")
                    lines.append(f"- [{src_title}]({src_url})" if src_url else f"- {src_title}")
                messages.append(
                    ConversationMessage(
                        role="assistant",
                        content="\n".join(lines),
                        timestamp=timestamp,
                    )
                )

        return messages
