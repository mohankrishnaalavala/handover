"""
Tests for handover/updater.py.

Validates incremental updates: task appending, tick preservation,
ADR numbering, conflict markers, backlog merge, dry run, and prompts.
"""

from __future__ import annotations

import json
from pathlib import Path

from handover.models import (
    Backlog,
    BacklogTask,
    Decision,
    HandoverManifest,
    ScaffoldContext,
    Task,
    UpdateDelta,
)
from handover.scaffold_heuristics import extract_scaffold_no_llm
from handover.universal_generator import write_handover_dir
from handover.updater import apply_update

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scaffold() -> ScaffoldContext:
    """Build a populated ScaffoldContext for initial .handover/ creation."""
    from handover.models import HandoverContext

    ctx = HandoverContext(
        source="claude",
        conversation_title="Test Project",
        goal="Build a thing",
        tech_stack={"language": "Python", "framework": "FastAPI"},
        tasks=[
            Task(title="Task A", priority="high", done=True),
            Task(title="Task B"),
        ],
        decisions=[Decision(topic="auth", decision="JWT", rationale="stateless")],
        constraints=["No vendor lock-in"],
        non_goals=["Mobile app"],
        open_questions=["How to handle caching?"],
    )
    scaffold = extract_scaffold_no_llm(ctx)
    scaffold.manifest = HandoverManifest(
        version="1.2.0",
        source="claude",
        target="claude-code",
        project="Test Project",
    )
    scaffold.backlog = Backlog(
        schema_version="1.0",
        updated_at="2026-04-09T00:00:00Z",
        project="Test Project",
        tasks=[
            BacklogTask(id="task-001", title="Task A", priority="high", done=True),
            BacklogTask(id="task-002", title="Task B"),
        ],
    )
    return scaffold


def _setup_handover(tmp_path: Path) -> Path:
    """Write initial .handover/ and return its path."""
    write_handover_dir(_scaffold(), tmp_path)
    return tmp_path / ".handover"


# ---------------------------------------------------------------------------
# Task appending
# ---------------------------------------------------------------------------


class TestAppendTasks:
    def test_new_tasks_appear_under_dated_heading(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        delta = UpdateDelta(
            new_tasks=[Task(title="Task C"), Task(title="Task D", priority="high")],
        )
        apply_update(delta, handover_dir)
        content = (handover_dir / "work" / "tasks.md").read_text()
        assert "## New (added" in content
        assert "- [ ] Task C" in content
        assert "- [ ] Task D *(high priority)*" in content

    def test_existing_done_tasks_preserved(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        delta = UpdateDelta(new_tasks=[Task(title="Task C")])
        apply_update(delta, handover_dir)
        content = (handover_dir / "work" / "tasks.md").read_text()
        assert "- [x] Task A" in content


# ---------------------------------------------------------------------------
# Decision appending
# ---------------------------------------------------------------------------


class TestAppendDecisions:
    def test_new_adr_continues_numbering(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        delta = UpdateDelta(
            new_decisions=[Decision(topic="caching", decision="Redis")],
        )
        apply_update(delta, handover_dir)
        content = (handover_dir / "context" / "decisions.md").read_text()
        assert "## ADR-002" in content
        assert "caching" in content

    def test_revised_decision_marker(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        old = Decision(topic="auth", decision="JWT")
        new = Decision(topic="auth", decision="Session-based")
        delta = UpdateDelta(revised_decisions=[(old, new)])
        apply_update(delta, handover_dir)
        content = (handover_dir / "context" / "decisions.md").read_text()
        assert "## REVISED" in content
        assert "Session-based" in content

    def test_no_conflict_skips_markers(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        old = Decision(topic="auth", decision="JWT")
        new = Decision(topic="auth", decision="Session-based")
        delta = UpdateDelta(revised_decisions=[(old, new)])
        apply_update(delta, handover_dir, no_conflict=True)
        content = (handover_dir / "context" / "decisions.md").read_text()
        assert "## REVISED" not in content


# ---------------------------------------------------------------------------
# Constraints, risks, tech stack
# ---------------------------------------------------------------------------


class TestAppendOtherSections:
    def test_new_constraints_appended(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        delta = UpdateDelta(new_constraints=["Budget limit"])
        apply_update(delta, handover_dir)
        content = (handover_dir / "context" / "constraints.md").read_text()
        assert "Budget limit" in content
        assert "No vendor lock-in" in content

    def test_new_open_questions_appended(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        delta = UpdateDelta(new_open_questions=["What about rate limiting?"])
        apply_update(delta, handover_dir)
        content = (handover_dir / "context" / "risks.md").read_text()
        assert "What about rate limiting?" in content
        assert "How to handle caching?" in content

    def test_new_tech_stack_appended(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        delta = UpdateDelta(new_tech_stack={"database": "PostgreSQL"})
        apply_update(delta, handover_dir)
        content = (handover_dir / "context" / "architecture.md").read_text()
        assert "**Database**: PostgreSQL" in content
        assert "**Language**: Python" in content


# ---------------------------------------------------------------------------
# Backlog merge
# ---------------------------------------------------------------------------


class TestBacklogMerge:
    def test_new_backlog_tasks_appended(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        delta = UpdateDelta(
            new_backlog_tasks=[
                BacklogTask(id="task-003", title="Task C", added_at="2026-04-10"),
            ],
            updated_at="2026-04-10T00:00:00Z",
        )
        apply_update(delta, handover_dir)
        data = json.loads((handover_dir / "work" / "backlog.json").read_text())
        ids = [t["id"] for t in data["tasks"]]
        assert "task-003" in ids
        assert data["updated_at"] == "2026-04-10T00:00:00Z"

    def test_done_backlog_tasks_preserved(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        delta = UpdateDelta(
            new_backlog_tasks=[BacklogTask(id="task-003", title="Task C")],
            preserved_done_backlog=["task-001"],
            updated_at="2026-04-10T00:00:00Z",
        )
        apply_update(delta, handover_dir)
        data = json.loads((handover_dir / "work" / "backlog.json").read_text())
        task_001 = next(t for t in data["tasks"] if t["id"] == "task-001")
        assert task_001["done"] is True


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        original = (handover_dir / "work" / "tasks.md").read_text()
        delta = UpdateDelta(new_tasks=[Task(title="New task")])
        written = apply_update(delta, handover_dir, dry_run=True)
        assert len(written) > 0
        assert (handover_dir / "work" / "tasks.md").read_text() == original


# ---------------------------------------------------------------------------
# Prompt regeneration
# ---------------------------------------------------------------------------


class TestPromptRegeneration:
    def test_prompts_regenerated_with_scaffold(self, tmp_path: Path) -> None:
        handover_dir = _setup_handover(tmp_path)
        scaffold = _scaffold()
        scaffold.manifest.project = "Updated Project"
        delta = UpdateDelta(new_tasks=[Task(title="New task")])
        apply_update(delta, handover_dir, scaffold=scaffold)
        content = (handover_dir / "prompts" / "implement.md").read_text()
        assert "Updated Project" in content
