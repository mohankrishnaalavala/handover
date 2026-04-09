"""
Tests for handover/universal_generator.py.

Validates the .handover/ directory structure, registry contents,
overwrite guard, and backlog.json schema.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from handover.models import (
    Backlog,
    BacklogTask,
    HandoverManifest,
    ScaffoldContext,
)
from handover.scaffold_heuristics import extract_scaffold_no_llm
from handover.universal_generator import (
    HANDOVER_DIR_FILES,
    HandoverDirExistsError,
    write_handover_dir,
)


def _scaffold() -> ScaffoldContext:
    """Build a fully-populated ScaffoldContext to render against."""
    from handover.models import Decision, HandoverContext, Task

    ctx = HandoverContext(
        source="claude",
        conversation_title="Test Project",
        goal="Build a thing",
        tech_stack={"language": "Python", "framework": "FastAPI"},
        tasks=[Task(title="Wire endpoints", priority="high")],
        decisions=[Decision(topic="auth", decision="JWT", rationale="stateless")],
    )
    scaffold = extract_scaffold_no_llm(ctx)
    scaffold.manifest = HandoverManifest(
        version="1.1.0",
        generated_at="2026-04-09T00:00:00Z",
        source="claude",
        target="claude-code",
        project="Test Project",
    )
    scaffold.backlog = Backlog(
        schema_version="1.0",
        updated_at="2026-04-09T00:00:00Z",
        project="Test Project",
        tasks=[
            BacklogTask(
                id="task-001",
                title="Wire endpoints",
                priority="high",
                added_at="2026-04-09T00:00:00Z",
            )
        ],
    )
    return scaffold


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestWriteHandoverDir:
    def test_all_registry_files_written(self, tmp_path: Path) -> None:
        written = write_handover_dir(_scaffold(), tmp_path)
        # 20 templated files + 1 backlog.json
        assert len(written) == len(HANDOVER_DIR_FILES) + 1
        for path in written:
            assert path.exists(), f"missing: {path}"

    def test_subdirectories_exist(self, tmp_path: Path) -> None:
        write_handover_dir(_scaffold(), tmp_path)
        root = tmp_path / ".handover"
        assert (root / "context").is_dir()
        assert (root / "work").is_dir()
        assert (root / "standards").is_dir()
        assert (root / "prompts").is_dir()

    def test_manifest_file_contains_version(self, tmp_path: Path) -> None:
        write_handover_dir(_scaffold(), tmp_path)
        manifest = (tmp_path / ".handover" / "manifest.yaml").read_text()
        assert "1.1.0" in manifest
        assert "claude" in manifest

    def test_decisions_file_uses_adr_format(self, tmp_path: Path) -> None:
        write_handover_dir(_scaffold(), tmp_path)
        decisions = (tmp_path / ".handover" / "context" / "decisions.md").read_text()
        assert "## ADR-" in decisions

    def test_prompts_render_project_name(self, tmp_path: Path) -> None:
        write_handover_dir(_scaffold(), tmp_path)
        implement = (tmp_path / ".handover" / "prompts" / "implement.md").read_text()
        # Project name from manifest must be substituted, not the raw token
        assert "{{" not in implement
        assert "Test Project" in implement


# ---------------------------------------------------------------------------
# backlog.json
# ---------------------------------------------------------------------------


class TestBacklogJson:
    def test_backlog_json_is_valid_json(self, tmp_path: Path) -> None:
        write_handover_dir(_scaffold(), tmp_path)
        parsed = json.loads((tmp_path / ".handover" / "work" / "backlog.json").read_text())
        assert parsed["schema_version"] == "1.0"
        assert isinstance(parsed["tasks"], list)
        assert parsed["tasks"][0]["id"] == "task-001"

    def test_backlog_required_keys_present(self, tmp_path: Path) -> None:
        write_handover_dir(_scaffold(), tmp_path)
        parsed = json.loads((tmp_path / ".handover" / "work" / "backlog.json").read_text())
        for key in ("schema_version", "updated_at", "project", "tasks", "milestones"):
            assert key in parsed


# ---------------------------------------------------------------------------
# Overwrite guard
# ---------------------------------------------------------------------------


class TestOverwriteGuard:
    def test_existing_dir_without_overwrite_raises(self, tmp_path: Path) -> None:
        write_handover_dir(_scaffold(), tmp_path)
        with pytest.raises(HandoverDirExistsError):
            write_handover_dir(_scaffold(), tmp_path)

    def test_overwrite_true_replaces_files(self, tmp_path: Path) -> None:
        write_handover_dir(_scaffold(), tmp_path)
        # Re-run with overwrite — must succeed and produce the same files.
        written = write_handover_dir(_scaffold(), tmp_path, overwrite=True)
        for path in written:
            assert path.exists()


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_returns_paths_without_writing(self, tmp_path: Path) -> None:
        written = write_handover_dir(_scaffold(), tmp_path, dry_run=True)
        assert len(written) == len(HANDOVER_DIR_FILES) + 1
        # Filesystem must be untouched
        assert not (tmp_path / ".handover").exists()
