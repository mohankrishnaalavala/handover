"""
Tests for handover parser adapters.

Tests cover:
  - ClaudeParser: single-conversation JSON export
  - ClaudeParser: bulk JSONL export
  - ClaudeParser: Markdown export
  - Format auto-detection (detect_source)
  - Error handling for unsupported formats
"""

from pathlib import Path

import pytest

from handover.models import ConversationMessage
from handover.parsers import detect_source
from handover.parsers.claude import ClaudeParser

FIXTURES = Path(__file__).parent / "fixtures"


class TestClaudeParserSingleJSON:
    def test_parse_returns_five_messages(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.json")
        assert len(messages) == 5

    def test_all_roles_normalized(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.json")
        assert all(m.role in ("user", "assistant") for m in messages)

    def test_first_message_is_user(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.json")
        assert messages[0].role == "user"

    def test_messages_in_chronological_order(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.json")
        timestamps = [m.timestamp for m in messages if m.timestamp]
        assert timestamps == sorted(timestamps)

    def test_no_empty_content(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.json")
        assert all(m.content for m in messages)

    def test_format_version_single_json_v1(self) -> None:
        parser = ClaudeParser()
        version = parser.detect_format_version(FIXTURES / "claude_single.json")
        assert version == "single-json v1.0"

    def test_message_ids_populated(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.json")
        assert all(m.message_id is not None for m in messages)

    def test_returns_conversation_message_instances(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.json")
        assert all(isinstance(m, ConversationMessage) for m in messages)


class TestClaudeParserBulkJSONL:
    def test_list_conversations_count(self) -> None:
        parser = ClaudeParser()
        conversations = parser.list_conversations(FIXTURES / "claude_bulk.jsonl")
        assert len(conversations) == 3

    def test_each_conversation_has_required_keys(self) -> None:
        parser = ClaudeParser()
        conversations = parser.list_conversations(FIXTURES / "claude_bulk.jsonl")
        for conv in conversations:
            assert "id" in conv
            assert "title" in conv
            assert "date" in conv

    def test_parse_returns_first_conversation(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_bulk.jsonl")
        assert len(messages) == 2  # first conversation in fixture has 2 messages

    def test_parse_by_conversation_id(self) -> None:
        parser = ClaudeParser()
        conversations = parser.list_conversations(FIXTURES / "claude_bulk.jsonl")
        second_id = conversations[1]["id"]
        messages = parser._parse_bulk_jsonl(FIXTURES / "claude_bulk.jsonl", conversation_id=second_id)
        assert len(messages) == 2
        assert "database schema" in messages[0].content.lower()

    def test_unknown_id_returns_empty(self) -> None:
        parser = ClaudeParser()
        messages = parser._parse_bulk_jsonl(
            FIXTURES / "claude_bulk.jsonl", conversation_id="does-not-exist"
        )
        assert messages == []

    def test_format_version_bulk_jsonl(self) -> None:
        parser = ClaudeParser()
        version = parser.detect_format_version(FIXTURES / "claude_bulk.jsonl")
        assert version == "bulk-jsonl v1.0"

    def test_all_roles_normalized(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_bulk.jsonl")
        assert all(m.role in ("user", "assistant") for m in messages)


class TestClaudeParserMarkdown:
    def test_parse_returns_five_messages(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.md")
        assert len(messages) == 5

    def test_all_roles_normalized(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.md")
        assert all(m.role in ("user", "assistant") for m in messages)

    def test_first_message_is_user(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.md")
        assert messages[0].role == "user"

    def test_no_empty_content(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.md")
        assert all(m.content for m in messages)

    def test_first_user_message_content(self) -> None:
        parser = ClaudeParser()
        messages = parser.parse(FIXTURES / "claude_single.md")
        assert "REST API" in messages[0].content

    def test_format_version_markdown(self) -> None:
        parser = ClaudeParser()
        version = parser.detect_format_version(FIXTURES / "claude_single.md")
        assert version == "markdown v1.0"


class TestParserErrors:
    def test_unsupported_extension_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "chat.xyz"
        bad_file.write_text("{}")
        parser = ClaudeParser()
        with pytest.raises(ValueError, match="Unsupported file format"):
            parser.parse(bad_file)

    def test_missing_file_raises(self) -> None:
        parser = ClaudeParser()
        with pytest.raises(FileNotFoundError):
            parser.parse(Path("nonexistent_file_abc.json"))

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not valid json {{{{")
        parser = ClaudeParser()
        with pytest.raises(ValueError, match="Invalid JSON"):
            parser.parse(bad_json)

    def test_invalid_jsonl_raises(self, tmp_path: Path) -> None:
        bad_jsonl = tmp_path / "bad.jsonl"
        bad_jsonl.write_text("not valid json\n")
        parser = ClaudeParser()
        with pytest.raises(ValueError, match="Invalid JSONL"):
            parser.parse(bad_jsonl)


class TestDetectSource:
    def test_detects_jsonl_as_claude(self) -> None:
        assert detect_source(str(FIXTURES / "claude_bulk.jsonl")) == "claude"

    def test_detects_json_as_claude(self) -> None:
        assert detect_source(str(FIXTURES / "claude_single.json")) == "claude"

    def test_detects_md_as_claude(self) -> None:
        assert detect_source(str(FIXTURES / "claude_single.md")) == "claude"

    def test_unknown_extension_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "chat.csv"
        bad.write_text("a,b,c")
        with pytest.raises(ValueError):
            detect_source(str(bad))

    def test_json_without_claude_markers_raises(self, tmp_path: Path) -> None:
        generic = tmp_path / "generic.json"
        generic.write_text('{"messages": []}')
        with pytest.raises(ValueError):
            detect_source(str(generic))
