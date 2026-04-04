"""
Tests for handover rule-based heuristics (--no-llm mode).

Each heuristic rule is tested independently.
See PRD Section 8 — --no-llm Rule-Based Extraction Heuristics.
"""

import pytest

from handover.models import ConversationMessage
from handover import heuristics


# TODO: implement tests — see PRD Section 8


def test_placeholder() -> None:
    """Placeholder test — replace with real tests during implementation."""
    pass


# Helpers
def user(content: str) -> ConversationMessage:
    return ConversationMessage(role="user", content=content)


def assistant(content: str) -> ConversationMessage:
    return ConversationMessage(role="assistant", content=content)


# class TestGoalExtraction:
#     def test_extracts_goal_from_intent_keyword(self):
#         messages = [user("I want to build a FastAPI REST API.")]
#         goal = heuristics.extract_goal(messages)
#         assert "FastAPI" in goal or "REST API" in goal
#
#     def test_falls_back_to_first_user_message(self):
#         messages = [user("Explain how authentication works."), assistant("Sure...")]
#         goal = heuristics.extract_goal(messages)
#         assert goal == "Explain how authentication works."
#
#
# class TestDecisionExtraction:
#     def test_extracts_decision_from_lets_use(self):
#         messages = [
#             user("Should we use JWT or sessions?"),
#             assistant("Let's use JWT for a stateless API."),
#         ]
#         decisions = heuristics.extract_decisions(messages)
#         assert len(decisions) >= 1
#         assert any("JWT" in d.decision for d in decisions)
#
#     def test_last_occurrence_wins_for_same_topic(self):
#         messages = [
#             assistant("Let's use PostgreSQL for the database."),
#             assistant("Actually, let's use SQLite for simplicity."),
#         ]
#         decisions = heuristics.extract_decisions(messages)
#         # SQLite should win (last occurrence)
#         decision_texts = [d.decision for d in decisions]
#         assert any("SQLite" in t for t in decision_texts)
#
#
# class TestConstraintExtraction:
#     def test_extracts_must_constraint(self):
#         messages = [user("It must run offline without internet access.")]
#         constraints = heuristics.extract_constraints(messages)
#         assert len(constraints) >= 1
#
#
# class TestNonGoalExtraction:
#     def test_extracts_out_of_scope(self):
#         messages = [user("Mobile app is out of scope for v1.")]
#         non_goals = heuristics.extract_non_goals(messages)
#         assert len(non_goals) >= 1
#
#
# class TestTechStackExtraction:
#     def test_detects_python_and_fastapi(self):
#         messages = [user("We'll use Python with FastAPI and PostgreSQL.")]
#         tech_stack = heuristics.extract_tech_stack(messages)
#         assert "python" in str(tech_stack).lower()
#         assert "fastapi" in str(tech_stack).lower()
