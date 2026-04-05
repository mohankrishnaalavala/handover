"""
Tests for handover/summarizer.py.

IMPORTANT: All Anthropic API calls must be mocked.
Never hit the real API in tests.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from handover import summarizer
from handover.models import ConversationMessage, HandoverAPIError


def make_messages() -> list[ConversationMessage]:
    return [
        ConversationMessage(
            role="user", content="I want to build a FastAPI REST API with JWT auth."
        ),  # noqa: E501
        ConversationMessage(role="assistant", content="Let's use Python, FastAPI, and PostgreSQL."),
        ConversationMessage(role="user", content="It must run offline."),
    ]


def make_mock_response(payload: dict) -> MagicMock:
    """Build a mock Anthropic response object."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = json.dumps(payload)
    return mock_response


_GOOD_PAYLOAD = {
    "goal": "Build a FastAPI REST API with JWT auth",
    "tech_stack": {"language": "Python", "framework": "FastAPI", "database": "PostgreSQL"},
    "decisions": [{"topic": "auth", "decision": "Use JWT", "rationale": "stateless"}],
    "tasks": [{"title": "Set up FastAPI", "description": "", "priority": "high", "done": False}],
    "constraints": ["Must run offline"],
    "non_goals": [],
    "open_questions": [],
}


class TestSummarizeWithLLM:
    def test_returns_handover_context(self) -> None:
        from handover.models import HandoverContext

        with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
            mock_response = make_mock_response(_GOOD_PAYLOAD)
            mock_client.return_value.messages.create.return_value = mock_response
            ctx = summarizer.summarize(make_messages(), use_llm=True)

        assert isinstance(ctx, HandoverContext)

    def test_goal_extracted_correctly(self) -> None:
        with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
            mock_response = make_mock_response(_GOOD_PAYLOAD)
            mock_client.return_value.messages.create.return_value = mock_response
            ctx = summarizer.summarize(make_messages(), use_llm=True)

        assert ctx.goal == "Build a FastAPI REST API with JWT auth"

    def test_decisions_mapped_to_dataclasses(self) -> None:
        from handover.models import Decision

        with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
            mock_response = make_mock_response(_GOOD_PAYLOAD)
            mock_client.return_value.messages.create.return_value = mock_response
            ctx = summarizer.summarize(make_messages(), use_llm=True)

        assert len(ctx.decisions) == 1
        assert isinstance(ctx.decisions[0], Decision)
        assert ctx.decisions[0].topic == "auth"

    def test_tasks_mapped_to_dataclasses(self) -> None:
        from handover.models import Task

        with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
            mock_response = make_mock_response(_GOOD_PAYLOAD)
            mock_client.return_value.messages.create.return_value = mock_response
            ctx = summarizer.summarize(make_messages(), use_llm=True)

        assert len(ctx.tasks) == 1
        assert isinstance(ctx.tasks[0], Task)
        assert ctx.tasks[0].title == "Set up FastAPI"
        assert ctx.tasks[0].priority == "high"

    def test_constraints_populated(self) -> None:
        with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
            mock_response = make_mock_response(_GOOD_PAYLOAD)
            mock_client.return_value.messages.create.return_value = mock_response
            ctx = summarizer.summarize(make_messages(), use_llm=True)

        assert "Must run offline" in ctx.constraints

    def test_api_error_raises_handover_api_error(self) -> None:
        import anthropic

        with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.side_effect = anthropic.APIError(
                message="server error", request=MagicMock(), body=None
            )
            with pytest.raises(HandoverAPIError, match="API error"):
                summarizer.summarize(make_messages(), use_llm=True)

    def test_auth_error_raises_handover_api_error(self) -> None:
        import anthropic

        with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.side_effect = anthropic.AuthenticationError(
                message="invalid key", response=MagicMock(), body=None
            )
            with pytest.raises(HandoverAPIError, match="ANTHROPIC_API_KEY"):
                summarizer.summarize(make_messages(), use_llm=True)

    def test_invalid_json_response_raises(self) -> None:
        bad_response = MagicMock()
        bad_response.content = [MagicMock()]
        bad_response.content[0].text = "This is not JSON at all."

        with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = bad_response
            with pytest.raises(HandoverAPIError, match="invalid JSON"):
                summarizer.summarize(make_messages(), use_llm=True)


class TestSummarizeNoLLM:
    def test_delegates_to_heuristics_extract(self) -> None:
        from unittest.mock import patch as _patch

        from handover.models import HandoverContext

        fake_ctx = HandoverContext()
        with _patch("handover.heuristics.extract", return_value=fake_ctx) as mock_extract:
            result = summarizer.summarize(make_messages(), use_llm=False)
            mock_extract.assert_called_once()
        assert result is fake_ctx

    def test_no_llm_does_not_call_anthropic(self) -> None:
        with patch("handover.summarizer.anthropic") as mock_anthropic:
            summarizer.summarize(make_messages(), use_llm=False)
            mock_anthropic.Anthropic.assert_not_called()

    def test_returns_handover_context(self) -> None:
        from handover.models import HandoverContext

        ctx = summarizer.summarize(make_messages(), use_llm=False)
        assert isinstance(ctx, HandoverContext)


class TestExtractionPrompt:
    def test_prompt_is_module_level_string(self) -> None:
        assert isinstance(summarizer.EXTRACTION_PROMPT, str)
        assert len(summarizer.EXTRACTION_PROMPT) > 100

    def test_prompt_mentions_conflict_resolution(self) -> None:
        assert "LATEST" in summarizer.EXTRACTION_PROMPT or "latest" in summarizer.EXTRACTION_PROMPT
