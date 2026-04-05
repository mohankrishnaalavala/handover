"""Tests for handover/models.py — validation guards and data model correctness."""

import pytest

from handover.models import ConversationMessage, Decision, HandoverAPIError, Task


class TestConversationMessage:
    def test_valid_user_role(self) -> None:
        msg = ConversationMessage(role="user", content="hello")
        assert msg.role == "user"

    def test_valid_assistant_role(self) -> None:
        msg = ConversationMessage(role="assistant", content="hi")
        assert msg.role == "assistant"

    def test_invalid_role_raises(self) -> None:
        with pytest.raises(ValueError, match="role must be"):
            ConversationMessage(role="human", content="hello")

    def test_empty_content_raises(self) -> None:
        with pytest.raises(ValueError, match="content must not be empty"):
            ConversationMessage(role="user", content="")

    def test_optional_fields_default_none(self) -> None:
        msg = ConversationMessage(role="user", content="hi")
        assert msg.timestamp is None
        assert msg.message_id is None

    def test_optional_fields_accepted(self) -> None:
        msg = ConversationMessage(
            role="user", content="hi", timestamp="2026-01-01T00:00:00Z", message_id="abc"
        )
        assert msg.timestamp == "2026-01-01T00:00:00Z"
        assert msg.message_id == "abc"


class TestTask:
    def test_default_priority_medium(self) -> None:
        task = Task(title="Do something")
        assert task.priority == "medium"

    def test_high_priority_accepted(self) -> None:
        task = Task(title="Urgent", priority="high")
        assert task.priority == "high"

    def test_low_priority_accepted(self) -> None:
        task = Task(title="Nice to have", priority="low")
        assert task.priority == "low"

    def test_invalid_priority_raises(self) -> None:
        with pytest.raises(ValueError, match="priority must be"):
            Task(title="Bad task", priority="critical")

    def test_done_defaults_false(self) -> None:
        task = Task(title="Pending")
        assert task.done is False


class TestDecision:
    def test_decision_fields(self) -> None:
        d = Decision(topic="database", decision="use PostgreSQL", rationale="ACID compliance")
        assert d.topic == "database"
        assert d.decision == "use PostgreSQL"
        assert d.rationale == "ACID compliance"

    def test_rationale_defaults_empty(self) -> None:
        d = Decision(topic="db", decision="sqlite")
        assert d.rationale == ""


class TestHandoverAPIError:
    def test_is_exception(self) -> None:
        err = HandoverAPIError("API call failed")
        assert isinstance(err, Exception)
        assert str(err) == "API call failed"
