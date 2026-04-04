"""
Tests for handover/summarizer.py.

IMPORTANT: All Anthropic API calls must be mocked.
Never hit the real API in tests.

See .claude/skills/anthropic-api.md for the correct mocking pattern.
"""

from unittest.mock import MagicMock, patch

import pytest

from handover.models import ConversationMessage
from handover import summarizer


# TODO: implement tests — see PRD Section 6 and .claude/skills/anthropic-api.md


def test_placeholder() -> None:
    """Placeholder test — replace with real tests during implementation."""
    pass


# Helpers
def make_messages() -> list[ConversationMessage]:
    return [
        ConversationMessage(role="user", content="I want to build a FastAPI REST API with JWT auth."),
        ConversationMessage(role="assistant", content="Let's use Python, FastAPI, and PostgreSQL."),
        ConversationMessage(role="user", content="It must run offline."),
    ]


# class TestSummarizeWithLLM:
#     def test_returns_handover_context(self):
#         mock_response = MagicMock()
#         mock_response.content[0].text = '''{
#             "goal": "Build a FastAPI REST API with JWT auth",
#             "tech_stack": {"language": "Python", "framework": "FastAPI", "database": "PostgreSQL"},
#             "decisions": [{"topic": "auth", "decision": "Use JWT", "rationale": "stateless"}],
#             "tasks": [{"title": "Set up FastAPI", "description": "", "priority": "high", "done": false}],
#             "constraints": ["Must run offline"],
#             "non_goals": [],
#             "open_questions": []
#         }'''
#
#         with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
#             mock_client.return_value.messages.create.return_value = mock_response
#             context = summarizer.summarize(make_messages(), use_llm=True)
#
#         assert context.goal == "Build a FastAPI REST API with JWT auth"
#         assert len(context.tasks) == 1
#         assert len(context.constraints) == 1
#
#
# class TestSummarizeNoLLM:
#     def test_delegates_to_heuristics(self):
#         with patch("handover.heuristics.extract") as mock_extract:
#             mock_extract.return_value = MagicMock()
#             summarizer.summarize(make_messages(), use_llm=False)
#             mock_extract.assert_called_once()
