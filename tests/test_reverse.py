"""
tests/test_reverse.py

Tests for Phase 4 — reverse handover pipeline.
Covers: ClaudeCodeSessionParser, reverse orchestrator, Generator.generate_handover,
and the CLI reverse/sessions subcommands.

All LLM calls are mocked.
"""

from __future__ import annotations

import builtins as _builtins
from pathlib import Path
from unittest.mock import patch

import pytest

from handover.models import FileChange, SessionContext, SessionMeta, Task
from handover.parsers.claude_code import ClaudeCodeSessionParser

_real_import = _builtins.__import__

FIXTURE = Path(__file__).parent / "fixtures" / "claude_code_session.jsonl"


# ---------------------------------------------------------------------------
# ClaudeCodeSessionParser
# ---------------------------------------------------------------------------


class TestClaudeCodeSessionParser:
    def setup_method(self) -> None:
        self.parser = ClaudeCodeSessionParser()

    def test_parse_returns_conversation_messages(self) -> None:
        messages = self.parser.parse(FIXTURE)
        assert len(messages) >= 2
        roles = {m.role for m in messages}
        assert "user" in roles
        assert "assistant" in roles

    def test_parse_skips_tool_result_only_turns(self) -> None:
        messages = self.parser.parse(FIXTURE)
        # Tool-result-only user turns should be filtered out
        for msg in messages:
            assert msg.content.strip() != ""

    def test_parse_skips_thinking_blocks(self) -> None:
        messages = self.parser.parse(FIXTURE)
        for msg in messages:
            # No thinking block text should appear in content
            assert "signature" not in msg.content

    def test_parse_entries_returns_raw_dicts(self) -> None:
        entries = self.parser.parse_session_entries(FIXTURE)
        assert len(entries) >= 4
        for entry in entries:
            assert entry.get("type") in ("user", "assistant")

    def test_parse_entries_skips_queue_operations(self) -> None:
        entries = self.parser.parse_session_entries(FIXTURE)
        for entry in entries:
            assert entry.get("type") != "queue-operation"

    def test_detect_format_version(self) -> None:
        version = self.parser.detect_format_version(FIXTURE)
        assert version == "2.1.0"

    def test_parse_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            self.parser.parse_session_entries(tmp_path / "nonexistent.jsonl")

    def test_parse_handles_malformed_lines(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.jsonl"
        bad_file.write_text(
            '{"type":"user","message":{"role":"user","content":"hello"},"timestamp":"2026-01-01T00:00:00Z","sessionId":"x","version":"1.0"}\n'
            "not-json-at-all\n"
            '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"hi"}]},"timestamp":"2026-01-01T00:00:01Z","sessionId":"x","version":"1.0"}\n',
            encoding="utf-8",
        )
        messages = self.parser.parse(bad_file)
        assert len(messages) == 2

    def test_project_hash(self) -> None:
        p = Path("/Users/alice/projects/myapp")
        assert ClaudeCodeSessionParser.project_hash(p) == "-Users-alice-projects-myapp"

    def test_project_hash_root(self) -> None:
        p = Path("/tmp")
        assert ClaudeCodeSessionParser.project_hash(p) == "-tmp"

    def test_discover_sessions_returns_empty_for_unknown_project(self, tmp_path: Path) -> None:
        # tmp_path won't have any entries under ~/.claude/projects/
        parser = ClaudeCodeSessionParser()
        sessions = parser.discover_sessions(tmp_path)
        assert sessions == []

    def test_discover_sessions_returns_meta_list(self, tmp_path: Path) -> None:
        """Simulate a ~/.claude/projects/ structure in a tmp dir."""
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        project_hash = ClaudeCodeSessionParser.project_hash(project_path)

        # Patch the home directory to point inside tmp_path
        fake_home = tmp_path / "home"
        sessions_dir = fake_home / ".claude" / "projects" / project_hash
        sessions_dir.mkdir(parents=True)

        # Copy fixture into the fake sessions dir
        import shutil

        shutil.copy(FIXTURE, sessions_dir / "test-session-abc123.jsonl")

        with patch.object(Path, "home", return_value=fake_home):
            parser = ClaudeCodeSessionParser()
            sessions = parser.discover_sessions(project_path)

        assert len(sessions) == 1
        assert isinstance(sessions[0], SessionMeta)
        assert sessions[0].session_id == "test-session-abc123"
        assert sessions[0].git_branch == "feature/api"
        assert sessions[0].message_count >= 4

    def test_list_conversations_from_file(self) -> None:
        convs = self.parser.list_conversations(FIXTURE)
        assert len(convs) == 0  # parent dir has no other session files in test env
        # But if we pass the file itself, result is based on parent directory

    def test_parse_by_id_reads_session_file(self, tmp_path: Path) -> None:
        import shutil

        shutil.copy(FIXTURE, tmp_path / "test-session-abc123.jsonl")
        messages = self.parser.parse_by_id(tmp_path, "test-session-abc123")
        assert len(messages) >= 2


# ---------------------------------------------------------------------------
# reverse orchestrator
# ---------------------------------------------------------------------------


class TestReverse:
    def test_reverse_extracts_file_changes(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        with patch("handover.reverse._extract_with_llm") as mock_llm:
            mock_llm.return_value = {"decisions": [], "next_steps": []}
            ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)

        # Fixture creates main.py (Write), auth.py (Write), then edits main.py (Edit)
        paths = {fc.path for fc in ctx.files_changed}
        assert "/tmp/test-project/main.py" in paths
        assert "/tmp/test-project/auth.py" in paths

    def test_reverse_classifies_write_as_created(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)
        auth_change = next(fc for fc in ctx.files_changed if "auth.py" in fc.path)
        assert auth_change.action == "created"

    def test_reverse_classifies_edit_as_modified(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)
        main_change = next(fc for fc in ctx.files_changed if "main.py" in fc.path)
        # main.py was Written first, then Edited → should be "modified" (second operation wins)
        assert main_change.action == "modified"

    def test_reverse_extracts_commands(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)
        assert any("pytest" in cmd for cmd in ctx.commands_run)

    def test_reverse_extracts_last_action(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)
        assert ctx.last_action != ""

    def test_reverse_estimates_context_usage(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)
        # Fixture has usage data in assistant messages
        assert ctx.context_usage_pct is not None
        assert 0 < ctx.context_usage_pct <= 100

    def test_reverse_reads_git_branch(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)
        assert ctx.git_branch == "feature/api"

    def test_reverse_sets_session_id(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)
        assert ctx.session_id == "test-session-abc123"

    def test_reverse_empty_file_raises(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        empty = tmp_path / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="No session entries"):
            reverse(empty, project_dir=tmp_path, use_llm=False)

    def test_reverse_llm_failure_falls_back_to_heuristics(self, tmp_path: Path) -> None:
        from handover.models import HandoverAPIError
        from handover.reverse import reverse

        with patch("handover.reverse._extract_with_llm", side_effect=HandoverAPIError("quota")):
            ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=True)

        # Should not raise — falls back gracefully
        assert isinstance(ctx, SessionContext)

    def test_reverse_heuristic_extracts_decisions(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)
        # Fixture has "I chose PyJWT..." and "I decided to use async handlers..."
        assert len(ctx.decisions) >= 1

    def test_reverse_with_plan_md(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        plan_content = (
            "# Plan\n\n- [ ] Implement JWT auth\n- [ ] Add PostgreSQL\n- [ ] Write tests\n"  # noqa: E501
        )
        (tmp_path / "PLAN.md").write_text(plan_content, encoding="utf-8")

        ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)
        # JWT auth might match "auth.py" in changed files
        all_tasks = ctx.tasks_completed + ctx.tasks_remaining
        assert len(all_tasks) == 3

    def test_reverse_without_plan_md_returns_empty_tasks(self, tmp_path: Path) -> None:
        from handover.reverse import reverse

        ctx = reverse(FIXTURE, project_dir=tmp_path, use_llm=False)
        assert ctx.tasks_completed == []
        assert ctx.tasks_remaining == []


# ---------------------------------------------------------------------------
# Generator.generate_handover
# ---------------------------------------------------------------------------


class TestGeneratorHandover:
    def test_generate_handover_writes_file(self, tmp_path: Path) -> None:
        from handover.generator import Generator

        ctx = SessionContext(
            session_id="abc12345",
            project_name="myapp",
            generated_at="2026-04-05T10:00:00Z",
            started_at="2026-04-05T09:00:00Z",
            git_branch="main",
            files_changed=[FileChange(path="src/api.py", action="created")],
            commands_run=["pytest tests/"],
            decisions=["Chose PyJWT for simplicity"],
            tasks_completed=[Task(title="Implement auth", done=True)],
            tasks_remaining=[Task(title="Add tests")],
            last_action="Write src/api.py",
            context_usage_pct=42,
            next_steps=["Run integration tests"],
        )
        gen = Generator()
        result = gen.generate_handover(ctx, tmp_path, dry_run=False)
        handover_path = tmp_path / "HANDOVER.md"
        assert handover_path.exists()
        content = handover_path.read_text(encoding="utf-8")
        assert "myapp" in content
        assert "abc12345"[:8] in content
        assert "src/api.py" in content
        assert "PyJWT" in content
        assert "HANDOVER.md" in result

    def test_generate_handover_dry_run_does_not_write(self, tmp_path: Path) -> None:
        from handover.generator import Generator

        ctx = SessionContext(session_id="x", project_name="p", generated_at="")
        gen = Generator()
        result = gen.generate_handover(ctx, tmp_path, dry_run=True)
        assert not (tmp_path / "HANDOVER.md").exists()
        assert "HANDOVER.md" in result

    def test_render_handover_md_contains_context_usage(self) -> None:
        from handover.generator import Generator

        ctx = SessionContext(
            session_id="test1234",
            project_name="proj",
            generated_at="2026-01-01T00:00:00Z",
            context_usage_pct=75,
        )
        gen = Generator()
        rendered = gen.render_handover_md(ctx)
        assert "75%" in rendered

    def test_render_handover_md_hides_context_usage_when_none(self) -> None:
        from handover.generator import Generator

        ctx = SessionContext(
            session_id="test1234",
            project_name="proj",
            generated_at="2026-01-01T00:00:00Z",
            context_usage_pct=None,
        )
        gen = Generator()
        rendered = gen.render_handover_md(ctx)
        assert "Context used" not in rendered

    def test_render_handover_md_shows_next_steps(self) -> None:
        from handover.generator import Generator

        ctx = SessionContext(
            session_id="test1234",
            project_name="proj",
            generated_at="2026-01-01T00:00:00Z",
            next_steps=["Run tests", "Deploy to staging"],
        )
        gen = Generator()
        rendered = gen.render_handover_md(ctx)
        assert "Run tests" in rendered
        assert "Deploy to staging" in rendered


# ---------------------------------------------------------------------------
# CLI — reverse subcommand
# ---------------------------------------------------------------------------


class TestReverseCLI:
    def test_reverse_command_exists(self) -> None:
        from click.testing import CliRunner

        from handover.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["reverse", "--help"])
        assert result.exit_code == 0
        assert "--session" in result.output
        assert "--no-llm" in result.output

    def test_sessions_command_exists(self) -> None:
        from click.testing import CliRunner

        from handover.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["sessions", "--help"])
        assert result.exit_code == 0
        assert "--project" in result.output

    def test_watch_command_exists(self) -> None:
        from click.testing import CliRunner

        from handover.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["watch", "--help"])
        assert result.exit_code == 0
        assert "--idle" in result.output
        assert "--daemon" in result.output

    def test_reverse_with_session_flag(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from handover.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "reverse",
                "--session",
                str(FIXTURE),
                "--output",
                str(tmp_path),
                "--no-llm",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "HANDOVER.md").exists()

    def test_reverse_dry_run(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from handover.cli import main

        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "reverse",
                "--session",
                str(FIXTURE),
                "--output",
                str(tmp_path),
                "--no-llm",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        assert not (tmp_path / "HANDOVER.md").exists()
        assert "Would write" in result.output

    def test_sessions_no_project_found(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from handover.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["sessions", "--project", str(tmp_path)])
        assert result.exit_code == 0
        assert "No Claude Code sessions found" in result.output

    def test_watch_fails_gracefully_without_watchdog(self, tmp_path: Path) -> None:
        """watch command should show clear error if watchdog is not installed."""
        from click.testing import CliRunner

        from handover.cli import main

        runner = CliRunner()
        with patch("builtins.__import__", side_effect=_fake_import_without_watchdog):
            result = runner.invoke(
                main, ["watch", "--project", str(tmp_path)], catch_exceptions=False
            )
        # Should exit with an error about watchdog
        assert result.exit_code != 0 or "watchdog" in result.output


def _fake_import_without_watchdog(name: str, *args: object, **kwargs: object) -> object:
    if name == "watchdog" or name.startswith("watchdog."):
        raise ImportError("No module named 'watchdog'")
    return _real_import(name, *args, **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Watcher (unit tests — no real filesystem monitoring)
# ---------------------------------------------------------------------------


class TestSessionEventHandler:
    def test_schedules_timer_on_jsonl_file(self, tmp_path: Path) -> None:
        from handover.watcher import _SessionEventHandler

        handler = _SessionEventHandler(
            project_dir=tmp_path, output_dir=tmp_path, no_llm=True, idle_seconds=9999
        )
        handler.on_created("/some/path/session.jsonl")
        assert "/some/path/session.jsonl" in handler._timers
        # Cleanup
        handler._timers["/some/path/session.jsonl"].cancel()

    def test_ignores_non_jsonl_files(self, tmp_path: Path) -> None:
        from handover.watcher import _SessionEventHandler

        handler = _SessionEventHandler(
            project_dir=tmp_path, output_dir=tmp_path, no_llm=True, idle_seconds=9999
        )
        handler.on_created("/some/path/notes.txt")
        assert len(handler._timers) == 0

    def test_resets_timer_on_modify(self, tmp_path: Path) -> None:
        from handover.watcher import _SessionEventHandler

        handler = _SessionEventHandler(
            project_dir=tmp_path, output_dir=tmp_path, no_llm=True, idle_seconds=9999
        )
        handler.on_created("/some/path/session.jsonl")
        first_timer = handler._timers["/some/path/session.jsonl"]
        handler.on_modified("/some/path/session.jsonl")
        second_timer = handler._timers["/some/path/session.jsonl"]
        assert first_timer is not second_timer
        # Cleanup
        second_timer.cancel()
