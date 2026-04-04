"""
Tests for handover parser adapters.

Tests cover:
  - ClaudeParser: single-conversation JSON export
  - ClaudeParser: bulk JSONL export
  - Format auto-detection
  - Error handling for unsupported formats
"""

from pathlib import Path

import pytest

from handover.parsers.claude import ClaudeParser
from handover.models import ConversationMessage


# TODO: implement tests — see PRD Section 9 and docs/adding-an-adapter.md


def test_placeholder() -> None:
    """Placeholder test — replace with real tests during implementation."""
    pass


# class TestClaudeParserSingleJSON:
#     def test_parse_returns_messages(self):
#         parser = ClaudeParser()
#         messages = parser.parse(Path("tests/fixtures/claude_single.json"))
#         assert len(messages) > 0
#
#     def test_all_roles_are_normalized(self):
#         parser = ClaudeParser()
#         messages = parser.parse(Path("tests/fixtures/claude_single.json"))
#         assert all(m.role in ("user", "assistant") for m in messages)
#
#     def test_first_message_is_from_user(self):
#         parser = ClaudeParser()
#         messages = parser.parse(Path("tests/fixtures/claude_single.json"))
#         assert messages[0].role == "user"
#
#     def test_messages_are_in_chronological_order(self):
#         parser = ClaudeParser()
#         messages = parser.parse(Path("tests/fixtures/claude_single.json"))
#         # Parsing twice should produce the same order
#         assert messages == parser.parse(Path("tests/fixtures/claude_single.json"))
#
#
# class TestClaudeParserBulkJSONL:
#     def test_list_conversations_returns_list(self):
#         parser = ClaudeParser()
#         conversations = parser.list_conversations(Path("tests/fixtures/claude_bulk.jsonl"))
#         assert len(conversations) >= 1
#
#     def test_each_conversation_has_required_keys(self):
#         parser = ClaudeParser()
#         conversations = parser.list_conversations(Path("tests/fixtures/claude_bulk.jsonl"))
#         for conv in conversations:
#             assert "id" in conv
#             assert "title" in conv
#
#
# class TestParserErrorHandling:
#     def test_raises_for_unsupported_extension(self, tmp_path):
#         bad_file = tmp_path / "chat.xyz"
#         bad_file.write_text("{}")
#         parser = ClaudeParser()
#         with pytest.raises(ValueError, match="Unsupported file format"):
#             parser.parse(bad_file)
#
#     def test_raises_for_missing_file(self):
#         parser = ClaudeParser()
#         with pytest.raises(FileNotFoundError):
#             parser.parse(Path("nonexistent.json"))
