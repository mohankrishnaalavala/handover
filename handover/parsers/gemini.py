"""
handover/parsers/gemini.py

Parser adapter for Google Gemini chat exports (Google Takeout).

Export format: a JSON file with a top-level "appActivity" list.
Each item has "requestBody" (user turn) and "responseBody" (assistant turn),
both containing a "parts" list with a "text" field.

Example structure:
  {
    "appActivity": [
      {
        "activityTime": "2024-01-01T10:00:00Z",
        "requestBody": {"parts": [{"text": "..."}]},
        "responseBody": {"parts": [{"text": "..."}]}
      }
    ]
  }
"""

from __future__ import annotations

import json
from pathlib import Path

from handover.models import ConversationMessage
from handover.parsers.base import BaseParser


class GeminiParser(BaseParser):
    """Parser for Google Gemini Google Takeout exports."""

    source_name = "gemini"

    def parse(self, file_path: Path) -> list[ConversationMessage]:
        """
        Parse a Gemini Takeout JSON export.

        Args:
            file_path: Path to the Gemini export JSON file.

        Returns:
            List of ConversationMessage in chronological order.

        Raises:
            ValueError: If the file does not contain 'appActivity'.
            FileNotFoundError: If the file does not exist.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Export file not found: {file_path}")

        data = json.loads(file_path.read_text(encoding="utf-8"))
        activities = data.get("appActivity")
        if activities is None:
            raise ValueError(
                f"Expected 'appActivity' key in {file_path.name}. "
                "Is this a Gemini Google Takeout export?"
            )

        messages: list[ConversationMessage] = []
        for item in activities:
            timestamp = item.get("activityTime", None)

            # User turn
            user_text = _extract_text(item.get("requestBody"))
            if user_text:
                messages.append(
                    ConversationMessage(role="user", content=user_text, timestamp=timestamp)
                )

            # Assistant turn
            assistant_text = _extract_text(item.get("responseBody"))
            if assistant_text:
                messages.append(
                    ConversationMessage(
                        role="assistant", content=assistant_text, timestamp=timestamp
                    )
                )

        return messages

    def detect_format_version(self, file_path: Path) -> str:
        return "gemini-takeout v1.0"


def _extract_text(body: object) -> str:
    """Extract concatenated text from a Gemini requestBody/responseBody dict."""
    if not isinstance(body, dict):
        return ""
    parts = body.get("parts") or []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
    return "\n".join(t for t in texts if t)
