"""
Tests for handover/diff.py.

Validates markdown parsing (tasks, decisions, constraints, tech stack),
round-trip fidelity with write_handover_dir, and delta computation.
"""

from __future__ import annotations

from pathlib import Path

from handover.diff import (
    _parse_constraints_md,
    _parse_decisions_md,
    _parse_goal_md,
    _parse_open_questions_md,
    _parse_tasks_md,
    _parse_tech_stack_md,
    compute_delta,
    parse_existing_handover,
)
from handover.models import (
    Backlog,
    BacklogTask,
    Decision,
    HandoverContext,
    HandoverManifest,
    ScaffoldContext,
    Task,
)
from handover.scaffold_heuristics import extract_scaffold_no_llm
from handover.universal_generator import write_handover_dir

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scaffold(
    goal: str = "Build a thing",
    tech_stack: dict | None = None,
    tasks: list[Task] | None = None,
    decisions: list[Decision] | None = None,
    constraints: list[str] | None = None,
    non_goals: list[str] | None = None,
    open_questions: list[str] | None = None,
) -> tuple[ScaffoldContext, HandoverContext]:
    """Build a ScaffoldContext + its source HandoverContext."""
    ctx = HandoverContext(
        source="claude",
        conversation_title="Test Project",
        goal=goal,
        tech_stack=tech_stack or {"language": "Python"},
        tasks=tasks or [Task(title="Task A", priority="high")],
        decisions=decisions or [Decision(topic="auth", decision="JWT", rationale="stateless")],
        constraints=constraints or ["No vendor lock-in"],
        non_goals=non_goals or ["Mobile app"],
        open_questions=open_questions or ["How to handle auth?"],
    )
    scaffold = extract_scaffold_no_llm(ctx)
    scaffold.manifest = HandoverManifest(
        version="1.1.0",
        source="claude",
        target="claude-code",
        project="Test Project",
    )
    scaffold.backlog = Backlog(
        schema_version="1.0",
        updated_at="2026-04-09T00:00:00Z",
        project="Test Project",
        tasks=[
            BacklogTask(id=f"task-{i + 1:03d}", title=t.title, priority=t.priority, done=t.done)
            for i, t in enumerate(ctx.tasks)
        ],
    )
    return scaffold, ctx


def _write_handover(tmp_path: Path, **kwargs) -> Path:
    """Write .handover/ and return the directory path."""
    scaffold, _ = _make_scaffold(**kwargs)
    write_handover_dir(scaffold, tmp_path)
    return tmp_path / ".handover"


# ---------------------------------------------------------------------------
# Markdown parsers
# ---------------------------------------------------------------------------


class TestParseTasksMd:
    def test_basic_checkbox(self) -> None:
        content = "- [ ] Do something\n- [x] Done thing\n"
        tasks = _parse_tasks_md(content)
        assert len(tasks) == 2
        assert tasks[0].title == "Do something"
        assert tasks[0].done is False
        assert tasks[1].title == "Done thing"
        assert tasks[1].done is True

    def test_high_priority_suffix(self) -> None:
        content = "- [ ] Wire API *(high priority)*\n"
        tasks = _parse_tasks_md(content)
        assert len(tasks) == 1
        assert tasks[0].title == "Wire API"
        assert tasks[0].priority == "high"

    def test_empty_content(self) -> None:
        assert _parse_tasks_md("") == []
        assert _parse_tasks_md("no checkboxes here") == []


class TestParseDecisionsMd:
    def test_adr_format(self) -> None:
        content = (
            "## ADR-001 — Use JWT\n\n"
            "**Status:** Accepted\n\n"
            "**Context:**\n\nStateless is better.\n\n"
            "**Decision:**\n\nJWT for auth.\n\n"
            "**Consequences:**\n\n_TBD_\n"
        )
        decisions = _parse_decisions_md(content)
        assert len(decisions) == 1
        assert decisions[0].topic == "Use JWT"
        assert decisions[0].decision == "JWT for auth."
        assert decisions[0].rationale == "Stateless is better."

    def test_multiple_adrs(self) -> None:
        content = (
            "## ADR-001 — Auth\n\n"
            "**Status:** Accepted\n\n"
            "**Context:**\n\nReason A.\n\n"
            "**Decision:**\n\nJWT.\n\n"
            "**Consequences:**\n\n_TBD_\n\n"
            "## ADR-002 — Database\n\n"
            "**Status:** Accepted\n\n"
            "**Context:**\n\nReason B.\n\n"
            "**Decision:**\n\nPostgres.\n\n"
            "**Consequences:**\n\n_TBD_\n"
        )
        decisions = _parse_decisions_md(content)
        assert len(decisions) == 2
        assert decisions[1].topic == "Database"

    def test_no_decisions_placeholder(self) -> None:
        assert _parse_decisions_md("_No decisions extracted yet._") == []


class TestParseConstraintsMd:
    def test_both_sections(self) -> None:
        content = (
            "## Constraints\n\n- No vendor lock-in\n- Budget limit\n\n"
            "## Non-goals\n\n- Mobile app\n"
        )
        constraints, non_goals = _parse_constraints_md(content)
        assert constraints == ["No vendor lock-in", "Budget limit"]
        assert non_goals == ["Mobile app"]

    def test_empty_placeholder(self) -> None:
        assert _parse_constraints_md("_No constraints or non-goals recorded._") == ([], [])


class TestParseTechStackMd:
    def test_key_value_pairs(self) -> None:
        content = "## Tech stack\n\n- **Language**: Python\n- **Framework**: FastAPI\n"
        result = _parse_tech_stack_md(content)
        assert result == {"language": "Python", "framework": "FastAPI"}

    def test_empty(self) -> None:
        assert _parse_tech_stack_md("no tech stack here") == {}


class TestParseGoalMd:
    def test_extract_goal(self) -> None:
        content = "## Goal\n\nBuild a REST API.\n\n## Vision\n\nMore stuff."
        assert _parse_goal_md(content) == "Build a REST API."

    def test_no_goal_section(self) -> None:
        assert _parse_goal_md("random content") == ""


class TestParseOpenQuestionsMd:
    def test_questions(self) -> None:
        content = "## Open questions\n\n- [ ] How to handle auth?\n- [ ] What about caching?\n"
        questions = _parse_open_questions_md(content)
        assert len(questions) == 2
        assert questions[0] == "How to handle auth?"


# ---------------------------------------------------------------------------
# Round-trip test
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_write_then_parse_preserves_data(self, tmp_path: Path) -> None:
        handover_dir = _write_handover(
            tmp_path,
            tasks=[Task(title="Task A", priority="high", done=True), Task(title="Task B")],
            decisions=[Decision(topic="auth", decision="JWT", rationale="stateless")],
            constraints=["No vendor lock-in"],
            non_goals=["Mobile app"],
            open_questions=["How to handle caching?"],
        )

        ctx, backlog = parse_existing_handover(handover_dir)

        assert ctx.goal  # goal is populated
        assert len(ctx.tasks) == 2
        assert ctx.tasks[0].done is True
        assert ctx.tasks[0].title == "Task A"
        assert ctx.tasks[1].done is False
        assert len(ctx.decisions) == 1
        assert ctx.decisions[0].topic == "auth"
        assert "No vendor lock-in" in ctx.constraints
        assert "Mobile app" in ctx.non_goals
        assert "How to handle caching?" in ctx.open_questions
        assert len(backlog.tasks) == 2


# ---------------------------------------------------------------------------
# Delta computation
# ---------------------------------------------------------------------------


class TestComputeDelta:
    def test_new_tasks_detected(self) -> None:
        existing = HandoverContext(tasks=[Task(title="Task A")])
        fresh = HandoverContext(tasks=[Task(title="Task A"), Task(title="Task B")])
        delta = compute_delta(existing, Backlog(), fresh, Backlog())
        assert len(delta.new_tasks) == 1
        assert delta.new_tasks[0].title == "Task B"

    def test_done_tasks_preserved(self) -> None:
        existing = HandoverContext(tasks=[Task(title="Task A", done=True)])
        fresh = HandoverContext(tasks=[Task(title="Task A", done=False)])
        delta = compute_delta(existing, Backlog(), fresh, Backlog())
        assert "Task A" in delta.preserved_done_tasks
        assert len(delta.new_tasks) == 0

    def test_new_decisions_detected(self) -> None:
        existing = HandoverContext(decisions=[Decision(topic="auth", decision="JWT")])
        fresh = HandoverContext(
            decisions=[
                Decision(topic="auth", decision="JWT"),
                Decision(topic="db", decision="Postgres"),
            ]
        )
        delta = compute_delta(existing, Backlog(), fresh, Backlog())
        assert len(delta.new_decisions) == 1
        assert delta.new_decisions[0].topic == "db"

    def test_revised_decision_detected(self) -> None:
        existing = HandoverContext(decisions=[Decision(topic="auth", decision="JWT")])
        fresh = HandoverContext(decisions=[Decision(topic="auth", decision="Session-based")])
        delta = compute_delta(existing, Backlog(), fresh, Backlog())
        assert len(delta.revised_decisions) == 1
        old, new = delta.revised_decisions[0]
        assert old.decision == "JWT"
        assert new.decision == "Session-based"

    def test_new_constraints(self) -> None:
        existing = HandoverContext(constraints=["Budget limit"])
        fresh = HandoverContext(constraints=["Budget limit", "No vendor lock-in"])
        delta = compute_delta(existing, Backlog(), fresh, Backlog())
        assert delta.new_constraints == ["No vendor lock-in"]

    def test_new_tech_stack(self) -> None:
        existing = HandoverContext(tech_stack={"language": "Python"})
        fresh = HandoverContext(tech_stack={"language": "Python", "db": "Postgres"})
        delta = compute_delta(existing, Backlog(), fresh, Backlog())
        assert delta.new_tech_stack == {"db": "Postgres"}

    def test_empty_delta(self) -> None:
        ctx = HandoverContext(
            tasks=[Task(title="A")],
            decisions=[Decision(topic="auth", decision="JWT")],
        )
        delta = compute_delta(ctx, Backlog(), ctx, Backlog())
        assert delta.is_empty

    def test_new_backlog_tasks(self) -> None:
        existing_bl = Backlog(tasks=[BacklogTask(id="task-001", title="A")])
        fresh_bl = Backlog(
            tasks=[
                BacklogTask(id="task-001", title="A"),
                BacklogTask(id="task-002", title="B"),
            ]
        )
        delta = compute_delta(HandoverContext(), existing_bl, HandoverContext(), fresh_bl)
        assert len(delta.new_backlog_tasks) == 1
        assert delta.new_backlog_tasks[0].id == "task-002"

    def test_done_backlog_preserved(self) -> None:
        existing_bl = Backlog(tasks=[BacklogTask(id="task-001", title="A", done=True)])
        delta = compute_delta(HandoverContext(), existing_bl, HandoverContext(), Backlog())
        assert "task-001" in delta.preserved_done_backlog
