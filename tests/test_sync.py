"""
Tests for handover/sync.py.

Anthropic API calls are mocked — never hits the real API.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from handover import sync as sync_module
from handover.models import HandoverAPIError
from handover.sync import SyncResult, _tokenize, sync_backlog


def make_mock_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = json.dumps(payload)
    return response


def write_backlog(project: Path, tasks: list[dict]) -> Path:
    work = project / ".handover" / "work"
    work.mkdir(parents=True, exist_ok=True)
    backlog = {
        "schema_version": "1.0",
        "updated_at": "2026-04-01T00:00:00Z",
        "project": "Test",
        "tasks": tasks,
        "milestones": [],
    }
    path = work / "backlog.json"
    path.write_text(json.dumps(backlog, indent=2))
    return path


def write_index(project: Path, content: str) -> Path:
    codebase = project / ".handover" / "codebase"
    codebase.mkdir(parents=True, exist_ok=True)
    path = codebase / "index.md"
    path.write_text(content)
    return path


def base_task(task_id: str, title: str, done: bool = False) -> dict:
    return {
        "id": task_id,
        "title": title,
        "description": "",
        "phase": "1",
        "priority": "high",
        "done": done,
        "tags": [],
        "added_at": "2026-04-01T00:00:00Z",
        "done_at": None,
    }


class TestTokenize:
    def test_filters_stopwords(self) -> None:
        assert "build" not in _tokenize("Build the Hero section")
        assert "hero" in _tokenize("Build the Hero section")

    def test_min_length_three(self) -> None:
        assert _tokenize("Go is ok") == []

    def test_lowercased(self) -> None:
        assert _tokenize("Build Hero") == ["hero"]


class TestSyncBacklogHeuristic:
    def test_marks_task_done_when_tokens_match(self, tmp_path: Path) -> None:
        write_backlog(
            tmp_path,
            [base_task("task-001", "Build Hero component with tagline")],
        )
        write_index(tmp_path, "- src/components/Hero.astro\n- tagline copy")

        result = sync_backlog(tmp_path, use_llm=False)

        assert result.tasks_marked_done == 1
        assert result.task_ids_marked_done == ["task-001"]
        assert result.mode == "heuristic"

    def test_does_not_mark_when_no_evidence(self, tmp_path: Path) -> None:
        write_backlog(
            tmp_path,
            [base_task("task-001", "Implement WebSocket notifications")],
        )
        write_index(tmp_path, "- src/components/Hero.astro")

        result = sync_backlog(tmp_path, use_llm=False)

        assert result.tasks_marked_done == 0

    def test_already_done_preserved(self, tmp_path: Path) -> None:
        write_backlog(
            tmp_path,
            [base_task("task-001", "Build Hero", done=True)],
        )
        write_index(tmp_path, "- src/components/Hero.astro")

        result = sync_backlog(tmp_path, use_llm=False)

        assert result.already_done == 1
        assert result.tasks_marked_done == 0

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        path = write_backlog(
            tmp_path,
            [base_task("task-001", "Build Hero component with tagline")],
        )
        write_index(tmp_path, "- src/components/Hero.astro tagline")
        original = path.read_text()

        result = sync_backlog(tmp_path, use_llm=False, dry_run=True)

        assert result.dry_run is True
        assert result.tasks_marked_done == 1
        assert path.read_text() == original

    def test_writes_done_at_timestamp(self, tmp_path: Path) -> None:
        path = write_backlog(
            tmp_path,
            [base_task("task-001", "Build Hero component with tagline")],
        )
        write_index(tmp_path, "- src/components/Hero.astro tagline")

        sync_backlog(tmp_path, use_llm=False)

        data = json.loads(path.read_text())
        assert data["tasks"][0]["done"] is True
        assert data["tasks"][0]["done_at"] is not None

    def test_missing_backlog_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            sync_backlog(tmp_path, use_llm=False)


class TestSyncBacklogLLM:
    def test_llm_marks_tasks_per_api_response(self, tmp_path: Path) -> None:
        write_backlog(
            tmp_path,
            [
                base_task("task-001", "Build Hero"),
                base_task("task-002", "Build Footer"),
            ],
        )
        write_index(tmp_path, "some index content")

        with patch("handover.sync.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = make_mock_response(
                {"task-001": True, "task-002": False}
            )
            result = sync_backlog(tmp_path, use_llm=True)

        assert result.mode == "llm"
        assert result.task_ids_marked_done == ["task-001"]

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        write_backlog(tmp_path, [base_task("task-001", "Build Hero")])

        with patch("handover.sync.anthropic.Anthropic") as mock_client:
            bad_response = MagicMock()
            bad_response.content = [MagicMock()]
            bad_response.content[0].text = "not json at all"
            mock_client.return_value.messages.create.return_value = bad_response

            with pytest.raises(HandoverAPIError, match="invalid JSON"):
                sync_backlog(tmp_path, use_llm=True)

    def test_auth_error_raises_handover_error(self, tmp_path: Path) -> None:
        import anthropic

        write_backlog(tmp_path, [base_task("task-001", "Build Hero")])

        with patch("handover.sync.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.side_effect = anthropic.AuthenticationError(
                "bad key", response=MagicMock(status_code=401), body=None
            )
            with pytest.raises(HandoverAPIError, match="ANTHROPIC_API_KEY"):
                sync_backlog(tmp_path, use_llm=True)

    def test_strips_markdown_fences(self, tmp_path: Path) -> None:
        write_backlog(tmp_path, [base_task("task-001", "Build Hero")])

        response = MagicMock()
        response.content = [MagicMock()]
        response.content[0].text = '```json\n{"task-001": true}\n```'

        with patch("handover.sync.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = response
            result = sync_backlog(tmp_path, use_llm=True)

        assert result.tasks_marked_done == 1


class TestSyncResultShape:
    def test_empty_backlog(self, tmp_path: Path) -> None:
        write_backlog(tmp_path, [])
        result = sync_backlog(tmp_path, use_llm=False)
        assert isinstance(result, SyncResult)
        assert result.tasks_total == 0
        assert result.tasks_marked_done == 0


class TestGitLogReader:
    def test_not_a_repo_returns_empty(self, tmp_path: Path) -> None:
        assert sync_module._read_git_log(tmp_path) == ""
