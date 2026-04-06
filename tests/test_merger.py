"""
Tests for handover/merger.py — Phase 6 multi-context merge.

Verifies that:
  - Heuristic merge deduplicates and applies last-wins for scalar fields
  - LLM merge delegates to summarizer (mocked)
  - CLI `handover merge` parses multiple --input files
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from handover.cli import main
from handover.merger import _merge_heuristic, merge_contexts
from handover.models import Decision, HandoverContext, Task

FIXTURES = Path(__file__).parent / "fixtures"


def make_ctx(
    goal: str = "",
    tech_stack: dict | None = None,
    decisions: list | None = None,
    tasks: list | None = None,
    constraints: list | None = None,
    non_goals: list | None = None,
    open_questions: list | None = None,
    source: str = "claude",
) -> HandoverContext:
    return HandoverContext(
        source=source,
        goal=goal,
        tech_stack=tech_stack or {},
        decisions=decisions or [],
        tasks=tasks or [],
        constraints=constraints or [],
        non_goals=non_goals or [],
        open_questions=open_questions or [],
    )


# ---------------------------------------------------------------------------
# Heuristic merge
# ---------------------------------------------------------------------------


class TestHeuristicMerge:
    def test_single_context_returned_unchanged(self) -> None:
        ctx = make_ctx(goal="Build X")
        result = merge_contexts([ctx], use_llm=False)
        assert result.goal == "Build X"

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            merge_contexts([], use_llm=False)

    def test_last_non_empty_goal_wins(self) -> None:
        ctx1 = make_ctx(goal="Old goal")
        ctx2 = make_ctx(goal="New goal")
        result = _merge_heuristic([ctx1, ctx2])
        assert result.goal == "New goal"

    def test_empty_goal_not_overridden(self) -> None:
        ctx1 = make_ctx(goal="Good goal")
        ctx2 = make_ctx(goal="")
        result = _merge_heuristic([ctx1, ctx2])
        assert result.goal == "Good goal"

    def test_tech_stack_merged_later_wins(self) -> None:
        ctx1 = make_ctx(tech_stack={"language": "Python", "db": "SQLite"})
        ctx2 = make_ctx(tech_stack={"db": "PostgreSQL", "framework": "FastAPI"})
        result = _merge_heuristic([ctx1, ctx2])
        assert result.tech_stack["language"] == "Python"
        assert result.tech_stack["db"] == "PostgreSQL"
        assert result.tech_stack["framework"] == "FastAPI"

    def test_decisions_deduplicated(self) -> None:
        d1 = Decision(topic="auth", decision="Use JWT", rationale="stateless")
        d2 = Decision(topic="auth", decision="Use JWT", rationale="still stateless")
        ctx1 = make_ctx(decisions=[d1])
        ctx2 = make_ctx(decisions=[d2])
        result = _merge_heuristic([ctx1, ctx2])
        assert len(result.decisions) == 1

    def test_decisions_different_topics_both_kept(self) -> None:
        d1 = Decision(topic="auth", decision="JWT")
        d2 = Decision(topic="db", decision="PostgreSQL")
        ctx1 = make_ctx(decisions=[d1])
        ctx2 = make_ctx(decisions=[d2])
        result = _merge_heuristic([ctx1, ctx2])
        assert len(result.decisions) == 2

    def test_tasks_deduplicated_by_title(self) -> None:
        t1 = Task(title="Set up project", priority="high")
        t2 = Task(title="Set up project", priority="medium", done=True)
        ctx1 = make_ctx(tasks=[t1])
        ctx2 = make_ctx(tasks=[t2])
        result = _merge_heuristic([ctx1, ctx2])
        assert len(result.tasks) == 1
        # done=True wins
        assert result.tasks[0].done is True

    def test_tasks_case_insensitive_dedup(self) -> None:
        t1 = Task(title="write tests")
        t2 = Task(title="Write Tests")
        ctx1 = make_ctx(tasks=[t1])
        ctx2 = make_ctx(tasks=[t2])
        result = _merge_heuristic([ctx1, ctx2])
        assert len(result.tasks) == 1

    def test_constraints_union_dedup(self) -> None:
        ctx1 = make_ctx(constraints=["Must run offline", "Python 3.11+"])
        ctx2 = make_ctx(constraints=["Must run offline", "No external deps"])
        result = _merge_heuristic([ctx1, ctx2])
        assert len(result.constraints) == 3
        assert "Must run offline" in result.constraints

    def test_open_questions_union(self) -> None:
        ctx1 = make_ctx(open_questions=["Which ORM?"])
        ctx2 = make_ctx(open_questions=["Which cache layer?"])
        result = _merge_heuristic([ctx1, ctx2])
        assert len(result.open_questions) == 2

    def test_source_is_merged(self) -> None:
        ctx1 = make_ctx()
        ctx2 = make_ctx()
        result = _merge_heuristic([ctx1, ctx2])
        assert result.source == "merged"

    def test_three_contexts(self) -> None:
        ctx1 = make_ctx(goal="Goal 1", constraints=["C1"])
        ctx2 = make_ctx(goal="Goal 2", constraints=["C2"])
        ctx3 = make_ctx(goal="Goal 3", constraints=["C1"])
        result = _merge_heuristic([ctx1, ctx2, ctx3])
        assert result.goal == "Goal 3"
        assert len(result.constraints) == 2  # C1 deduped


# ---------------------------------------------------------------------------
# LLM merge (mocked)
# ---------------------------------------------------------------------------


class TestLLMMerge:
    def test_llm_merge_calls_summarizer(self) -> None:
        ctx1 = make_ctx(goal="Session 1 goal")
        ctx2 = make_ctx(goal="Session 2 goal")
        merged_ctx = make_ctx(goal="Unified goal")

        with patch("handover.merger._merge_with_llm", return_value=merged_ctx) as mock:
            result = merge_contexts([ctx1, ctx2], use_llm=True)
        mock.assert_called_once()
        assert result.goal == "Unified goal"

    def test_single_context_skips_llm(self) -> None:
        ctx = make_ctx(goal="Only session")
        with patch("handover.merger._merge_with_llm") as mock:
            result = merge_contexts([ctx], use_llm=True)
        mock.assert_not_called()
        assert result.goal == "Only session"


# ---------------------------------------------------------------------------
# CLI merge subcommand
# ---------------------------------------------------------------------------


class TestMergeCLI:
    def test_merge_two_files_no_llm(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "merge",
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "PLAN.md").exists()

    def test_merge_dry_run(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "merge",
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        assert not (tmp_path / "CLAUDE.md").exists()
        assert "Would write" in result.output

    def test_merge_single_input_error(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "merge",
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
            ],
        )
        assert result.exit_code != 0

    def test_merge_target_codex(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "merge",
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--target",
                "codex",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "AGENTS.md").exists()

    def test_merge_with_mocked_llm(self, tmp_path: Path) -> None:
        """Test LLM mode with mocked Anthropic API."""
        merged_ctx = make_ctx(
            goal="Unified goal",
            tasks=[Task(title="Task 1")],
        )
        with (
            patch("handover.merger._merge_with_llm", return_value=merged_ctx),
            patch("handover.summarizer._summarize_with_llm") as mock_sum,
        ):
            mock_sum.return_value = make_ctx(goal="Session goal")
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "merge",
                    "--input",
                    str(FIXTURES / "claude_single.json"),
                    "--input",
                    str(FIXTURES / "claude_single.json"),
                    "--output",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0, result.output
