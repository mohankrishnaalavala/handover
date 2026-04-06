"""
Tests for handover/targets/ — Phase 5 multi-target agent output.

Verifies that:
  - Each target generates the correct file(s) in the output directory
  - dry_run=True returns expected paths without writing any files
  - Registry functions (get_target, list_targets) behave correctly
  - CLI --target flag routes to the correct adapter
  - --target all writes all four formats

No real API calls are made (--no-llm / heuristics used throughout).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from handover.cli import main
from handover.models import Decision, HandoverContext, Task
from handover.targets import TARGET_REGISTRY, get_target, list_targets
from handover.targets.aider import AiderTarget
from handover.targets.claude_code import ClaudeCodeTarget
from handover.targets.codex import CodexTarget
from handover.targets.goose import GooseTarget

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


def make_context() -> HandoverContext:
    """Build a representative HandoverContext for testing."""
    return HandoverContext(
        schema_version="1.0",
        source="claude",
        source_version="single-json v1.0",
        conversation_title="FastAPI Project",
        goal="Build a FastAPI REST API with JWT auth",
        tech_stack={"language": "Python", "framework": "FastAPI"},
        decisions=[
            Decision(topic="auth", decision="Use JWT tokens", rationale="stateless"),
            Decision(topic="db", decision="PostgreSQL via SQLAlchemy", rationale="mature ORM"),
        ],
        tasks=[
            Task(title="Set up project scaffold", priority="high"),
            Task(title="Implement JWT middleware", priority="high"),
            Task(title="Write tests", priority="medium", done=True),
        ],
        constraints=["Must run offline", "Python 3.11+"],
        non_goals=["Mobile app"],
        open_questions=["Which ORM: SQLAlchemy vs Tortoise?"],
    )


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_list_targets_returns_all_four(self) -> None:
        targets = list_targets()
        assert "claude-code" in targets
        assert "codex" in targets
        assert "aider" in targets
        assert "goose" in targets

    def test_list_targets_length(self) -> None:
        assert len(list_targets()) == 4

    def test_get_target_returns_correct_instance(self) -> None:
        assert isinstance(get_target("claude-code"), ClaudeCodeTarget)
        assert isinstance(get_target("codex"), CodexTarget)
        assert isinstance(get_target("aider"), AiderTarget)
        assert isinstance(get_target("goose"), GooseTarget)

    def test_get_target_raises_on_unknown(self) -> None:
        with pytest.raises(ValueError, match="No target registered"):
            get_target("nonexistent-agent")

    def test_target_registry_keys_match_list_targets(self) -> None:
        assert set(TARGET_REGISTRY.keys()) == set(list_targets())


# ---------------------------------------------------------------------------
# ClaudeCodeTarget
# ---------------------------------------------------------------------------


class TestClaudeCodeTarget:
    def test_generates_claude_md(self, tmp_path: Path) -> None:
        t = ClaudeCodeTarget()
        t.generate(make_context(), tmp_path)
        assert (tmp_path / "CLAUDE.md").exists()

    def test_generates_plan_md(self, tmp_path: Path) -> None:
        t = ClaudeCodeTarget()
        t.generate(make_context(), tmp_path)
        assert (tmp_path / "PLAN.md").exists()

    def test_returns_both_paths(self, tmp_path: Path) -> None:
        t = ClaudeCodeTarget()
        paths = t.generate(make_context(), tmp_path)
        names = {p.name for p in paths}
        assert "CLAUDE.md" in names
        assert "PLAN.md" in names

    def test_dry_run_no_files_written(self, tmp_path: Path) -> None:
        t = ClaudeCodeTarget()
        t.generate(make_context(), tmp_path, dry_run=True)
        assert not (tmp_path / "CLAUDE.md").exists()
        assert not (tmp_path / "PLAN.md").exists()

    def test_dry_run_returns_expected_paths(self, tmp_path: Path) -> None:
        t = ClaudeCodeTarget()
        paths = t.generate(make_context(), tmp_path, dry_run=True)
        names = {p.name for p in paths}
        assert "CLAUDE.md" in names
        assert "PLAN.md" in names

    def test_name_property(self) -> None:
        assert ClaudeCodeTarget().name == "claude-code"

    def test_custom_template_dir_respected(self, tmp_path: Path) -> None:
        tpl_dir = tmp_path / "tpls"
        tpl_dir.mkdir()
        (tpl_dir / "claude_md.j2").write_text("# Custom {{ context.goal }}\n")
        (tpl_dir / "plan_md.j2").write_text("# Custom Plan\n")
        out_dir = tmp_path / "out"
        t = ClaudeCodeTarget(template_dir=tpl_dir)
        t.generate(make_context(), out_dir)
        content = (out_dir / "CLAUDE.md").read_text()
        assert content.startswith("# Custom")


# ---------------------------------------------------------------------------
# CodexTarget
# ---------------------------------------------------------------------------


class TestCodexTarget:
    def test_generates_agents_md(self, tmp_path: Path) -> None:
        t = CodexTarget()
        t.generate(make_context(), tmp_path)
        assert (tmp_path / "AGENTS.md").exists()

    def test_returns_agents_md_path(self, tmp_path: Path) -> None:
        t = CodexTarget()
        paths = t.generate(make_context(), tmp_path)
        assert paths[0].name == "AGENTS.md"

    def test_dry_run_no_files_written(self, tmp_path: Path) -> None:
        t = CodexTarget()
        t.generate(make_context(), tmp_path, dry_run=True)
        assert not (tmp_path / "AGENTS.md").exists()

    def test_dry_run_returns_path(self, tmp_path: Path) -> None:
        t = CodexTarget()
        paths = t.generate(make_context(), tmp_path, dry_run=True)
        assert paths[0].name == "AGENTS.md"

    def test_content_contains_goal(self, tmp_path: Path) -> None:
        t = CodexTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "FastAPI REST API" in content

    def test_content_contains_tech_stack(self, tmp_path: Path) -> None:
        t = CodexTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "FastAPI" in content
        assert "Python" in content

    def test_content_contains_tasks(self, tmp_path: Path) -> None:
        t = CodexTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "Set up project scaffold" in content
        assert "Implement JWT middleware" in content

    def test_content_contains_constraints(self, tmp_path: Path) -> None:
        t = CodexTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "Must run offline" in content

    def test_content_has_agent_instructions_header(self, tmp_path: Path) -> None:
        t = CodexTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "# Agent Instructions" in content

    def test_done_task_marked(self, tmp_path: Path) -> None:
        t = CodexTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / "AGENTS.md").read_text()
        assert "[x]" in content  # "Write tests" is done=True

    def test_name_property(self) -> None:
        assert CodexTarget().name == "codex"

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "nested" / "out"
        CodexTarget().generate(make_context(), new_dir)
        assert (new_dir / "AGENTS.md").exists()

    def test_empty_context_renders(self, tmp_path: Path) -> None:
        t = CodexTarget()
        t.generate(HandoverContext(), tmp_path)
        assert (tmp_path / "AGENTS.md").exists()


# ---------------------------------------------------------------------------
# AiderTarget
# ---------------------------------------------------------------------------


class TestAiderTarget:
    def test_generates_aider_conf(self, tmp_path: Path) -> None:
        t = AiderTarget()
        t.generate(make_context(), tmp_path)
        assert (tmp_path / ".aider.conf.yml").exists()

    def test_returns_conf_path(self, tmp_path: Path) -> None:
        t = AiderTarget()
        paths = t.generate(make_context(), tmp_path)
        assert paths[0].name == ".aider.conf.yml"

    def test_dry_run_no_files_written(self, tmp_path: Path) -> None:
        t = AiderTarget()
        t.generate(make_context(), tmp_path, dry_run=True)
        assert not (tmp_path / ".aider.conf.yml").exists()

    def test_dry_run_returns_path(self, tmp_path: Path) -> None:
        t = AiderTarget()
        paths = t.generate(make_context(), tmp_path, dry_run=True)
        assert paths[0].name == ".aider.conf.yml"

    def test_content_has_model_key(self, tmp_path: Path) -> None:
        t = AiderTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / ".aider.conf.yml").read_text()
        assert "model:" in content

    def test_content_has_auto_commits(self, tmp_path: Path) -> None:
        t = AiderTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / ".aider.conf.yml").read_text()
        assert "auto-commits:" in content

    def test_content_has_conventions(self, tmp_path: Path) -> None:
        t = AiderTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / ".aider.conf.yml").read_text()
        assert "conventions:" in content
        assert "Use JWT tokens" in content
        assert "PostgreSQL via SQLAlchemy" in content

    def test_no_conventions_when_no_decisions(self, tmp_path: Path) -> None:
        ctx = HandoverContext(goal="Simple goal")
        t = AiderTarget()
        t.generate(ctx, tmp_path)
        content = (tmp_path / ".aider.conf.yml").read_text()
        assert "conventions:" not in content

    def test_goal_in_comment(self, tmp_path: Path) -> None:
        t = AiderTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / ".aider.conf.yml").read_text()
        assert "Goal:" in content
        assert "FastAPI REST API" in content

    def test_name_property(self) -> None:
        assert AiderTarget().name == "aider"


# ---------------------------------------------------------------------------
# GooseTarget
# ---------------------------------------------------------------------------


class TestGooseTarget:
    def test_generates_goose_context_json(self, tmp_path: Path) -> None:
        t = GooseTarget()
        t.generate(make_context(), tmp_path)
        assert (tmp_path / "goose-context.json").exists()

    def test_returns_json_path(self, tmp_path: Path) -> None:
        t = GooseTarget()
        paths = t.generate(make_context(), tmp_path)
        assert paths[0].name == "goose-context.json"

    def test_dry_run_no_files_written(self, tmp_path: Path) -> None:
        t = GooseTarget()
        t.generate(make_context(), tmp_path, dry_run=True)
        assert not (tmp_path / "goose-context.json").exists()

    def test_dry_run_returns_path(self, tmp_path: Path) -> None:
        t = GooseTarget()
        paths = t.generate(make_context(), tmp_path, dry_run=True)
        assert paths[0].name == "goose-context.json"

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        t = GooseTarget()
        t.generate(make_context(), tmp_path)
        content = (tmp_path / "goose-context.json").read_text()
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_json_has_required_keys(self, tmp_path: Path) -> None:
        t = GooseTarget()
        t.generate(make_context(), tmp_path)
        data = json.loads((tmp_path / "goose-context.json").read_text())
        assert "goal" in data
        assert "tech_stack" in data
        assert "tasks" in data
        assert "constraints" in data
        assert "open_questions" in data

    def test_json_goal_matches_context(self, tmp_path: Path) -> None:
        t = GooseTarget()
        t.generate(make_context(), tmp_path)
        data = json.loads((tmp_path / "goose-context.json").read_text())
        assert data["goal"] == "Build a FastAPI REST API with JWT auth"

    def test_json_tasks_structure(self, tmp_path: Path) -> None:
        t = GooseTarget()
        t.generate(make_context(), tmp_path)
        data = json.loads((tmp_path / "goose-context.json").read_text())
        assert len(data["tasks"]) == 3
        titles = {task["title"] for task in data["tasks"]}
        assert "Set up project scaffold" in titles

    def test_json_task_done_flag(self, tmp_path: Path) -> None:
        t = GooseTarget()
        t.generate(make_context(), tmp_path)
        data = json.loads((tmp_path / "goose-context.json").read_text())
        done_tasks = [t for t in data["tasks"] if t["done"]]
        assert len(done_tasks) == 1
        assert done_tasks[0]["title"] == "Write tests"

    def test_json_constraints(self, tmp_path: Path) -> None:
        t = GooseTarget()
        t.generate(make_context(), tmp_path)
        data = json.loads((tmp_path / "goose-context.json").read_text())
        assert "Must run offline" in data["constraints"]
        assert "Python 3.11+" in data["constraints"]

    def test_name_property(self) -> None:
        assert GooseTarget().name == "goose"

    def test_empty_context_produces_valid_json(self, tmp_path: Path) -> None:
        t = GooseTarget()
        t.generate(HandoverContext(), tmp_path)
        data = json.loads((tmp_path / "goose-context.json").read_text())
        assert data["goal"] == ""
        assert data["tasks"] == []


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


class TestCLITargetFlag:
    def test_default_target_writes_claude_md(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
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

    def test_target_codex_writes_agents_md(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
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

    def test_target_aider_writes_conf(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--target",
                "aider",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / ".aider.conf.yml").exists()

    def test_target_goose_writes_json(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--target",
                "goose",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "goose-context.json").exists()

    def test_target_all_writes_all_formats(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--target",
                "all",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / ".aider.conf.yml").exists()
        assert (tmp_path / "goose-context.json").exists()

    def test_dry_run_with_target_claude_code(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--dry-run",
                "--target",
                "claude-code",
            ],
        )
        assert result.exit_code == 0, result.output
        assert not (tmp_path / "CLAUDE.md").exists()
        assert "CLAUDE.md" in result.output

    def test_dry_run_with_target_codex(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--dry-run",
                "--target",
                "codex",
            ],
        )
        assert result.exit_code == 0, result.output
        assert not (tmp_path / "AGENTS.md").exists()
        assert "AGENTS.md" in result.output

    def test_dry_run_with_target_all(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--dry-run",
                "--target",
                "all",
            ],
        )
        assert result.exit_code == 0, result.output
        # No files written
        assert not (tmp_path / "CLAUDE.md").exists()
        assert not (tmp_path / "AGENTS.md").exists()
        # But all names shown
        assert "CLAUDE.md" in result.output
        assert "AGENTS.md" in result.output
        assert ".aider.conf.yml" in result.output
        assert "goose-context.json" in result.output

    def test_target_codex_output_mentions_codex(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--target",
                "codex",
            ],
        )
        assert "AGENTS.md" in result.output

    def test_invalid_target_shows_error(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--target",
                "not-a-real-agent",
            ],
        )
        assert result.exit_code != 0
