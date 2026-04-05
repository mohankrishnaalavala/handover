"""
Tests for handover/generator.py.

Tests verify that:
  - CLAUDE.md and PLAN.md are written to the output directory
  - Generated content matches expected structure
  - Dry-run mode returns content without writing files
  - Custom templates are respected
"""

from pathlib import Path

import pytest

from handover import __version__
from handover.generator import Generator
from handover.models import Decision, HandoverContext, Task


def make_context() -> HandoverContext:
    return HandoverContext(
        schema_version="1.0",
        source="claude",
        source_version="single-json v1.0",
        conversation_title="API Design Discussion",
        conversation_id="abc123",
        extracted_at="2026-04-04T10:30:00Z",
        goal="Build a FastAPI REST API with JWT auth and PostgreSQL",
        tech_stack={"language": "Python", "framework": "FastAPI", "database": "PostgreSQL"},
        decisions=[Decision(topic="auth", decision="JWT auth", rationale="stateless API")],
        tasks=[
            Task(title="Set up FastAPI project scaffold", priority="high"),
            Task(title="Implement JWT auth middleware", priority="high"),
        ],
        constraints=["Must run offline"],
        non_goals=["Mobile app (v1)"],
        open_questions=["Which ORM: SQLAlchemy vs Tortoise?"],
    )


class TestGenerator:
    def test_generates_claude_md_key(self, tmp_path: Path) -> None:
        gen = Generator()
        result = gen.generate(make_context(), output_dir=tmp_path)
        assert "CLAUDE.md" in result

    def test_generates_plan_md_key(self, tmp_path: Path) -> None:
        gen = Generator()
        result = gen.generate(make_context(), output_dir=tmp_path)
        assert "PLAN.md" in result

    def test_claude_md_contains_goal(self, tmp_path: Path) -> None:
        gen = Generator()
        result = gen.generate(make_context(), output_dir=tmp_path)
        assert "FastAPI REST API" in result["CLAUDE.md"]

    def test_claude_md_contains_tech_stack(self, tmp_path: Path) -> None:
        gen = Generator()
        result = gen.generate(make_context(), output_dir=tmp_path)
        assert "FastAPI" in result["CLAUDE.md"]
        assert "PostgreSQL" in result["CLAUDE.md"]

    def test_claude_md_contains_constraint(self, tmp_path: Path) -> None:
        gen = Generator()
        result = gen.generate(make_context(), output_dir=tmp_path)
        assert "Must run offline" in result["CLAUDE.md"]

    def test_plan_md_contains_task(self, tmp_path: Path) -> None:
        gen = Generator()
        result = gen.generate(make_context(), output_dir=tmp_path)
        assert "Set up FastAPI" in result["PLAN.md"]

    def test_writes_files_to_output_dir(self, tmp_path: Path) -> None:
        gen = Generator()
        gen.generate(make_context(), output_dir=tmp_path)
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "PLAN.md").exists()

    def test_dry_run_does_not_write_files(self, tmp_path: Path) -> None:
        gen = Generator()
        gen.generate(make_context(), output_dir=tmp_path, dry_run=True)
        assert not (tmp_path / "CLAUDE.md").exists()
        assert not (tmp_path / "PLAN.md").exists()

    def test_dry_run_returns_content(self, tmp_path: Path) -> None:
        gen = Generator()
        result = gen.generate(make_context(), output_dir=tmp_path, dry_run=True)
        assert result["CLAUDE.md"]
        assert result["PLAN.md"]

    def test_output_dir_created_if_not_exists(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new" / "nested"
        gen = Generator()
        gen.generate(make_context(), output_dir=new_dir)
        assert (new_dir / "CLAUDE.md").exists()

    def test_version_in_comment(self, tmp_path: Path) -> None:
        gen = Generator()
        result = gen.generate(make_context(), output_dir=tmp_path)
        assert __version__ in result["CLAUDE.md"]

    def test_open_question_in_claude_md(self, tmp_path: Path) -> None:
        gen = Generator()
        result = gen.generate(make_context(), output_dir=tmp_path)
        assert "SQLAlchemy" in result["CLAUDE.md"]

    def test_empty_context_renders_without_error(self, tmp_path: Path) -> None:
        gen = Generator()
        empty_ctx = HandoverContext()
        result = gen.generate(empty_ctx, output_dir=tmp_path)
        assert "CLAUDE.md" in result
        assert "PLAN.md" in result

    def test_custom_template_dir_is_used(self, tmp_path: Path) -> None:
        # Create a minimal custom template
        tpl_dir = tmp_path / "templates"
        tpl_dir.mkdir()
        (tpl_dir / "claude_md.j2").write_text("# Custom: {{ context.goal }}\n")
        (tpl_dir / "plan_md.j2").write_text("# Custom Plan\n")

        output_dir = tmp_path / "output"
        gen = Generator(template_dir=tpl_dir)
        result = gen.generate(make_context(), output_dir=output_dir)
        assert result["CLAUDE.md"].startswith("# Custom:")


class TestRenderMethods:
    def test_render_claude_md_returns_string(self) -> None:
        gen = Generator()
        result = gen.render_claude_md(make_context())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_render_plan_md_returns_string(self) -> None:
        gen = Generator()
        result = gen.render_plan_md(make_context())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_plan_md_has_checkbox_for_task(self) -> None:
        gen = Generator()
        result = gen.render_plan_md(make_context())
        assert "[ ]" in result
