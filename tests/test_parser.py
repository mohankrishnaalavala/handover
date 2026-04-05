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
from handover.parsers.chatgpt import ChatGPTParser
from handover.parsers.claude import ClaudeParser
from handover.parsers.gemini import GeminiParser
from handover.parsers.perplexity import PerplexityParser

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
        messages = parser._parse_bulk_jsonl(
            FIXTURES / "claude_bulk.jsonl", conversation_id=second_id
        )
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

    def test_detects_chatgpt_json(self) -> None:
        assert detect_source(str(FIXTURES / "chatgpt_single.json")) == "chatgpt"

    def test_detects_gemini_json(self) -> None:
        assert detect_source(str(FIXTURES / "gemini_single.json")) == "gemini"

    def test_detects_perplexity_json(self) -> None:
        assert detect_source(str(FIXTURES / "perplexity_single.json")) == "perplexity"

    def test_detects_perplexity_by_filename_prefix(self, tmp_path: Path) -> None:
        f = tmp_path / "perplexity_export.json"
        f.write_text('{"conversations": []}')
        assert detect_source(str(f)) == "perplexity"


class TestChatGPTParser:
    def test_parse_returns_user_and_assistant_only(self) -> None:
        parser = ChatGPTParser()
        messages = parser.parse(FIXTURES / "chatgpt_single.json")
        assert all(m.role in ("user", "assistant") for m in messages)

    def test_skips_system_and_tool_nodes(self) -> None:
        parser = ChatGPTParser()
        messages = parser.parse(FIXTURES / "chatgpt_single.json")
        # system-node and tool-node-1 should be excluded
        assert len(messages) == 4

    def test_tree_walk_preserves_order(self) -> None:
        parser = ChatGPTParser()
        messages = parser.parse(FIXTURES / "chatgpt_single.json")
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"
        assert messages[2].role == "user"
        assert messages[3].role == "assistant"

    def test_timestamp_is_iso_string(self) -> None:
        parser = ChatGPTParser()
        messages = parser.parse(FIXTURES / "chatgpt_single.json")
        assert messages[0].timestamp is not None
        assert "T" in messages[0].timestamp  # ISO format

    def test_list_conversations_returns_two_entries(self) -> None:
        parser = ChatGPTParser()
        convs = parser.list_conversations(FIXTURES / "chatgpt_single.json")
        assert len(convs) == 2
        assert convs[0]["id"] == "chatgpt-conv-001"
        assert convs[0]["title"] == "Build a FastAPI service"

    def test_parse_by_id_selects_correct_conversation(self) -> None:
        parser = ChatGPTParser()
        messages = parser.parse_by_id(FIXTURES / "chatgpt_single.json", "chatgpt-conv-002")
        assert len(messages) == 2
        assert "React" in messages[0].content

    def test_missing_file_raises(self) -> None:
        parser = ChatGPTParser()
        with pytest.raises(FileNotFoundError):
            parser.parse(Path("nonexistent_chatgpt.json"))

    def test_format_version(self) -> None:
        parser = ChatGPTParser()
        assert parser.detect_format_version(FIXTURES / "chatgpt_single.json") == "chatgpt-json v1.0"

    def test_returns_conversation_message_instances(self) -> None:
        parser = ChatGPTParser()
        messages = parser.parse(FIXTURES / "chatgpt_single.json")
        assert all(isinstance(m, ConversationMessage) for m in messages)


class TestGeminiParser:
    def test_parse_returns_messages(self) -> None:
        parser = GeminiParser()
        messages = parser.parse(FIXTURES / "gemini_single.json")
        # 2 full exchanges + 1 item with empty requestBody (only assistant added)
        assert len(messages) >= 2

    def test_alternates_user_assistant(self) -> None:
        parser = GeminiParser()
        messages = parser.parse(FIXTURES / "gemini_single.json")
        # First two messages should be user then assistant
        assert messages[0].role == "user"
        assert messages[1].role == "assistant"

    def test_empty_request_body_skipped(self) -> None:
        parser = GeminiParser()
        messages = parser.parse(FIXTURES / "gemini_single.json")
        # The third activity item has empty parts in requestBody — user turn skipped
        roles = [m.role for m in messages]
        # Should not have two consecutive "assistant" entries from first 2 exchanges
        # but the final item contributes only an assistant message
        assert roles.count("user") == 2
        assert roles.count("assistant") == 3

    def test_list_conversations_returns_empty(self) -> None:
        parser = GeminiParser()
        assert parser.list_conversations(FIXTURES / "gemini_single.json") == []

    def test_missing_app_activity_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad_gemini.json"
        bad.write_text('{"data": []}')
        parser = GeminiParser()
        with pytest.raises(ValueError, match="appActivity"):
            parser.parse(bad)

    def test_format_version(self) -> None:
        parser = GeminiParser()
        version = parser.detect_format_version(FIXTURES / "gemini_single.json")
        assert version == "gemini-takeout v1.0"

    def test_returns_conversation_message_instances(self) -> None:
        parser = GeminiParser()
        messages = parser.parse(FIXTURES / "gemini_single.json")
        assert all(isinstance(m, ConversationMessage) for m in messages)


class TestPerplexityParser:
    def test_parse_returns_messages(self) -> None:
        parser = PerplexityParser()
        messages = parser.parse(FIXTURES / "perplexity_single.json")
        assert len(messages) >= 4  # 2 user + 1 assistant with sources appended + 1 assistant

    def test_sources_appended_as_assistant_message(self) -> None:
        parser = PerplexityParser()
        messages = parser.parse(FIXTURES / "perplexity_single.json")
        source_msgs = [m for m in messages if m.content.startswith("Sources:")]
        assert len(source_msgs) == 1
        assert "asyncio" in source_msgs[0].content

    def test_all_roles_normalized(self) -> None:
        parser = PerplexityParser()
        messages = parser.parse(FIXTURES / "perplexity_single.json")
        assert all(m.role in ("user", "assistant") for m in messages)

    def test_list_conversations_returns_two_entries(self) -> None:
        parser = PerplexityParser()
        convs = parser.list_conversations(FIXTURES / "perplexity_bulk.json")
        assert len(convs) == 2
        assert convs[0]["id"] == "perp-bulk-001"
        assert convs[1]["title"] == "Docker best practices"

    def test_parse_by_id_selects_correct_conversation(self) -> None:
        parser = PerplexityParser()
        messages = parser.parse_by_id(FIXTURES / "perplexity_bulk.json", "perp-bulk-002")
        assert "Docker" in messages[0].content

    def test_missing_conversations_key_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad_perp.json"
        bad.write_text('{"messages": []}')
        parser = PerplexityParser()
        with pytest.raises(ValueError, match="conversations"):
            parser.parse(bad)

    def test_format_version(self) -> None:
        parser = PerplexityParser()
        assert (
            parser.detect_format_version(FIXTURES / "perplexity_single.json")
            == "perplexity-json v1.0"
        )

    def test_returns_conversation_message_instances(self) -> None:
        parser = PerplexityParser()
        messages = parser.parse(FIXTURES / "perplexity_single.json")
        assert all(isinstance(m, ConversationMessage) for m in messages)
