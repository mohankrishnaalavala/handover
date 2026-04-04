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

from handover.models import HandoverContext, Decision, Task
from handover.generator import Generator


# TODO: implement tests — see PRD Section 10


def test_placeholder() -> None:
    """Placeholder test — replace with real tests during implementation."""
    pass


# Helpers
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
        decisions=[
            Decision(topic="auth", decision="JWT auth", rationale="stateless API"),
        ],
        tasks=[
            Task(title="Set up FastAPI project scaffold", priority="high"),
            Task(title="Implement JWT auth middleware", priority="high"),
        ],
        constraints=["Must run offline"],
        non_goals=["Mobile app (v1)"],
        open_questions=["Which ORM: SQLAlchemy vs Tortoise?"],
    )


# class TestGenerator:
#     def test_generates_claude_md(self, tmp_path):
#         gen = Generator()
#         context = make_context()
#         result = gen.generate(context, output_dir=tmp_path)
#         assert "CLAUDE.md" in result
#         assert "Build a FastAPI REST API" in result["CLAUDE.md"]
#
#     def test_generates_plan_md(self, tmp_path):
#         gen = Generator()
#         context = make_context()
#         result = gen.generate(context, output_dir=tmp_path)
#         assert "PLAN.md" in result
#         assert "Set up FastAPI" in result["PLAN.md"]
#
#     def test_writes_files_to_output_dir(self, tmp_path):
#         gen = Generator()
#         context = make_context()
#         gen.generate(context, output_dir=tmp_path)
#         assert (tmp_path / "CLAUDE.md").exists()
#         assert (tmp_path / "PLAN.md").exists()
#
#     def test_dry_run_does_not_write_files(self, tmp_path):
#         gen = Generator()
#         context = make_context()
#         gen.generate(context, output_dir=tmp_path, dry_run=True)
#         assert not (tmp_path / "CLAUDE.md").exists()
#         assert not (tmp_path / "PLAN.md").exists()
#
#     def test_claude_md_contains_tech_stack(self, tmp_path):
#         gen = Generator()
#         context = make_context()
#         result = gen.generate(context, output_dir=tmp_path)
#         assert "FastAPI" in result["CLAUDE.md"]
#         assert "PostgreSQL" in result["CLAUDE.md"]
