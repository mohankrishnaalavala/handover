"""
Tests for handover/scaffold_extractor.py.

LLM calls are mocked. The heuristic and domain-detection paths are pure
functions and are tested directly.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from handover import scaffold_extractor
from handover.models import (
    ConversationMessage,
    Decision,
    HandoverContext,
    ScaffoldContext,
    Task,
)
from handover.scaffold_extractor import (
    _BODY_FIELDS,
    DOMAIN_RULES,
    DomainRule,
    detect_domains,
    extract_scaffold,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ctx(**overrides) -> HandoverContext:  # type: ignore[no-untyped-def]
    base = HandoverContext(
        source="claude",
        conversation_title="Test Project",
        goal="Build a thing",
        tech_stack={"language": "Python", "framework": "FastAPI"},
        tasks=[
            Task(title="Wire up endpoints", priority="high"),
            Task(title="Add tests", priority="medium"),
        ],
        decisions=[Decision(topic="auth", decision="Use JWT", rationale="stateless")],
        constraints=["Offline-friendly"],
        non_goals=["Mobile app"],
        open_questions=["Caching strategy?"],
    )
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


def _messages() -> list[ConversationMessage]:
    return [
        ConversationMessage(role="user", content="I want a FastAPI service with PostgreSQL."),
        ConversationMessage(role="assistant", content="Sure — we will use pytest for tests."),
    ]


def _llm_payload() -> dict:  # type: ignore[type-arg]
    return {field_name: f"body for {field_name}" for field_name in _BODY_FIELDS}


def _mock_response(payload: dict) -> MagicMock:  # type: ignore[type-arg]
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = json.dumps(payload)
    return response


# ---------------------------------------------------------------------------
# extract_scaffold — LLM path
# ---------------------------------------------------------------------------


class TestExtractScaffoldLLM:
    def test_populates_all_body_fields_from_api_response(self) -> None:
        with patch("handover.scaffold_extractor.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = _mock_response(_llm_payload())
            scaffold = extract_scaffold(_messages(), _ctx(), use_llm=True)

        assert isinstance(scaffold, ScaffoldContext)
        for field_name in _BODY_FIELDS:
            assert getattr(scaffold, field_name) == f"body for {field_name}"

    def test_handles_fenced_json_response(self) -> None:
        fenced_text = "```json\n" + json.dumps(_llm_payload()) + "\n```"
        response = MagicMock()
        response.content = [MagicMock()]
        response.content[0].text = fenced_text
        with patch("handover.scaffold_extractor.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = response
            scaffold = extract_scaffold(_messages(), _ctx(), use_llm=True)
        assert scaffold.overview == "body for overview"

    def test_invalid_json_raises_handover_api_error(self) -> None:
        from handover.models import HandoverAPIError

        bad = MagicMock()
        bad.content = [MagicMock()]
        bad.content[0].text = "not json at all"
        with patch("handover.scaffold_extractor.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = bad
            try:
                extract_scaffold(_messages(), _ctx(), use_llm=True)
            except HandoverAPIError:
                return
        raise AssertionError("expected HandoverAPIError")


# ---------------------------------------------------------------------------
# extract_scaffold — no-LLM path
# ---------------------------------------------------------------------------


class TestExtractScaffoldNoLLM:
    def test_populates_all_body_fields(self) -> None:
        scaffold = extract_scaffold(_messages(), _ctx(), use_llm=False)
        for field_name in _BODY_FIELDS:
            assert getattr(scaffold, field_name) != ""

    def test_decisions_are_adr_format(self) -> None:
        scaffold = extract_scaffold(_messages(), _ctx(), use_llm=False)
        assert "## ADR-001" in scaffold.decisions

    def test_no_api_call_made(self) -> None:
        with patch("handover.scaffold_extractor.anthropic.Anthropic") as mock_client:
            extract_scaffold(_messages(), _ctx(), use_llm=False)
        mock_client.assert_not_called()


# ---------------------------------------------------------------------------
# Manifest + backlog assembly
# ---------------------------------------------------------------------------


class TestManifestAndBacklog:
    def test_manifest_carries_version_source_target(self) -> None:
        scaffold = extract_scaffold(
            _messages(), _ctx(), use_llm=False, target="codex", tool_version="9.9.9"
        )
        assert scaffold.manifest.version == "9.9.9"
        assert scaffold.manifest.source == "claude"
        assert scaffold.manifest.target == "codex"
        assert scaffold.manifest.project == "Test Project"

    def test_backlog_task_ids_are_sequential(self) -> None:
        ctx = _ctx(
            tasks=[
                Task(title="A", priority="high"),
                Task(title="B", priority="medium"),
                Task(title="C", priority="low"),
            ]
        )
        scaffold = extract_scaffold(_messages(), ctx, use_llm=False)
        ids = [t.id for t in scaffold.backlog.tasks]
        assert ids == ["task-001", "task-002", "task-003"]

    def test_backlog_marks_done_tasks(self) -> None:
        ctx = _ctx(tasks=[Task(title="Done", priority="medium", done=True)])
        scaffold = extract_scaffold(_messages(), ctx, use_llm=False)
        assert scaffold.backlog.tasks[0].done is True
        assert scaffold.backlog.tasks[0].done_at is not None


# ---------------------------------------------------------------------------
# Domain detection
# ---------------------------------------------------------------------------


class TestDetectDomains:
    def test_fastapi_in_stack_yields_backend_agent(self) -> None:
        ctx = _ctx(tech_stack={"language": "Python", "framework": "FastAPI"})
        agents, _, _, _ = detect_domains(ctx, [])
        names = [a.name for a in agents]
        assert "backend-agent" in names

    def test_pytest_signal_yields_test_agent(self) -> None:
        ctx = _ctx(tech_stack={"testing": "pytest"})
        agents, _, _, _ = detect_domains(ctx, [])
        names = [a.name for a in agents]
        assert "test-agent" in names

    def test_messages_drive_detection_too(self) -> None:
        ctx = _ctx(tech_stack={})
        msgs = [ConversationMessage(role="user", content="we use react and tailwind")]
        agents, _, _, _ = detect_domains(ctx, msgs)
        assert any(a.name == "frontend-agent" for a in agents)

    def test_default_commands_and_hooks_always_present(self) -> None:
        ctx = HandoverContext()  # no signals at all
        agents, skills, commands, hooks = detect_domains(ctx, [])
        assert agents == []
        assert skills == []
        # Defaults ship regardless
        assert any(c.name == "run-tests" for c in commands)
        assert hooks  # at least one default hook

    def test_empty_input_does_not_raise(self) -> None:
        agents, skills, commands, hooks = detect_domains(HandoverContext(), [])
        assert isinstance(agents, list)
        assert isinstance(skills, list)
        assert isinstance(commands, list)
        assert isinstance(hooks, list)

    def test_registry_extension_via_monkeypatch(self) -> None:
        """Loose-coupling check: adding a DomainRule entry is the only change."""
        custom = DomainRule(
            name="ml-agent",
            description="Machine learning agent",
            keywords=("pytorch", "tensorflow"),
            system_prompt="You build ML pipelines.",
        )
        with patch.object(scaffold_extractor, "DOMAIN_RULES", DOMAIN_RULES + [custom]):
            ctx = _ctx(tech_stack={"ml": "PyTorch"})
            agents, _, _, _ = detect_domains(ctx, [])
        assert any(a.name == "ml-agent" for a in agents)
