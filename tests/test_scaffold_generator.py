"""
Tests for handover/scaffold_generator.py — the .claude/ workspace writer.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from handover.models import (
    HandoverContext,
    ScaffoldContext,
)
from handover.scaffold_extractor import extract_scaffold
from handover.scaffold_generator import (
    ClaudeWorkspaceExistsError,
    generate_claude_workspace,
)


def _scaffold_with_fastapi() -> ScaffoldContext:
    ctx = HandoverContext(
        source="claude",
        conversation_title="Demo",
        goal="Build a thing",
        tech_stack={"language": "Python", "framework": "FastAPI"},
    )
    return extract_scaffold([], ctx, use_llm=False)


def _empty_scaffold() -> ScaffoldContext:
    """Scaffold with no detected domains and no defaults."""
    ctx = HandoverContext()
    scaffold = extract_scaffold([], ctx, use_llm=False)
    # Strip everything to verify the empty-collection paths.
    scaffold.agents = []
    scaffold.skills = []
    scaffold.commands = []
    scaffold.hooks = []
    return scaffold


# ---------------------------------------------------------------------------
# Domain-driven content
# ---------------------------------------------------------------------------


class TestDomainContent:
    def test_fastapi_creates_backend_agent_file(self, tmp_path: Path) -> None:
        generate_claude_workspace(_scaffold_with_fastapi(), tmp_path)
        assert (tmp_path / ".claude" / "agents" / "backend-agent.md").exists()

    def test_settings_json_is_valid_json(self, tmp_path: Path) -> None:
        generate_claude_workspace(_scaffold_with_fastapi(), tmp_path)
        text = (tmp_path / ".claude" / "settings.json").read_text()
        json.loads(text)  # must not raise

    def test_default_commands_written(self, tmp_path: Path) -> None:
        generate_claude_workspace(_scaffold_with_fastapi(), tmp_path)
        assert (tmp_path / ".claude" / "commands" / "run-tests.md").exists()
        assert (tmp_path / ".claude" / "commands" / "lint.md").exists()


# ---------------------------------------------------------------------------
# Hook scripts
# ---------------------------------------------------------------------------


class TestHookScripts:
    def test_hook_file_is_executable(self, tmp_path: Path) -> None:
        generate_claude_workspace(_scaffold_with_fastapi(), tmp_path)
        hook = tmp_path / ".claude" / "hooks" / "pre-tool-use.sh"
        assert hook.exists()
        assert os.access(hook, os.X_OK)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEmptyScaffold:
    def test_empty_collections_do_not_raise(self, tmp_path: Path) -> None:
        # Should not error and should still write settings.json + create dirs.
        written = generate_claude_workspace(_empty_scaffold(), tmp_path)
        assert (tmp_path / ".claude" / "settings.json").exists()
        # No agent files
        agent_dir = tmp_path / ".claude" / "agents"
        assert not any(agent_dir.glob("*.md"))
        assert any(p.name == "settings.json" for p in written)


class TestOverwriteGuard:
    def test_existing_workspace_blocks_rewrite(self, tmp_path: Path) -> None:
        generate_claude_workspace(_scaffold_with_fastapi(), tmp_path)
        with pytest.raises(ClaudeWorkspaceExistsError):
            generate_claude_workspace(_scaffold_with_fastapi(), tmp_path)

    def test_overwrite_true_replaces(self, tmp_path: Path) -> None:
        generate_claude_workspace(_scaffold_with_fastapi(), tmp_path)
        generate_claude_workspace(_scaffold_with_fastapi(), tmp_path, overwrite=True)
        assert (tmp_path / ".claude" / "agents" / "backend-agent.md").exists()


class TestDryRun:
    def test_dry_run_returns_paths_without_writing(self, tmp_path: Path) -> None:
        written = generate_claude_workspace(_scaffold_with_fastapi(), tmp_path, dry_run=True)
        assert written  # non-empty
        assert not (tmp_path / ".claude").exists()
