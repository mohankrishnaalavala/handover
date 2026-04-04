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
from pathlib import Path

from handover.models import ConversationMessage
from handover.parsers.base import BaseParser

# TODO: implement — see PRD Section 9


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
        # TODO: implement — detect format and delegate to appropriate method
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
                f"Unsupported file format: {suffix}. "
                f"Supported formats: .json, .jsonl, .md"
            )

    def _parse_single_json(self, path: Path) -> list[ConversationMessage]:
        """Parse a single-conversation JSON export from the browser extension."""
        # TODO: implement — see PRD Section 9
        raise NotImplementedError("Single JSON parsing not yet implemented")

    def _parse_bulk_jsonl(self, path: Path) -> list[ConversationMessage]:
        """Parse a bulk JSONL export from Claude Settings → Privacy → Export Data."""
        # TODO: implement — see PRD Section 9
        raise NotImplementedError("Bulk JSONL parsing not yet implemented")

    def _parse_markdown(self, path: Path) -> list[ConversationMessage]:
        """Parse a Markdown export from the browser extension."""
        # TODO: implement — see PRD Section 9
        raise NotImplementedError("Markdown parsing not yet implemented")

    def list_conversations(self, path: Path) -> list[dict]:
        """
        List all conversations in a bulk JSONL export.

        Used by the `handover list` subcommand.

        Args:
            path: Path to the bulk .jsonl export file.

        Returns:
            List of dicts with keys: id, title, date.
        """
        # TODO: implement
        raise NotImplementedError("list_conversations not yet implemented")

    def detect_format_version(self, file_path: Path) -> str:
        """
        Detect the Claude export format version.

        Claude's export format has changed over time. This method sniffs
        the structure to determine which version is present.

        Returns:
            Version string e.g. "single-json v1.0" or "bulk-jsonl v1.0".
        """
        # TODO: implement version detection — see PRD Section 7 note on source_version
        return "unknown"
