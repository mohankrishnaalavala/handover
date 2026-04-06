"""
Tests for handover/publisher.py — Phase 6 GitHub Gist publishing.

All subprocess calls are mocked — no real network requests or gh CLI invocations.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from handover.cli import main
from handover.publisher import PublisherError, _extract_gist_id, publish, pull

FIXTURES = Path(__file__).parent / "fixtures"

# Realistic gh auth status output (success)
_GH_AUTH_OK = MagicMock(returncode=0, stdout="", stderr="")


def _mock_run_ok(stdout: str = "") -> MagicMock:
    m = MagicMock(returncode=0, stdout=stdout, stderr="")
    return m


def _mock_run_fail(stderr: str = "error") -> MagicMock:
    m = MagicMock(returncode=1, stdout="", stderr=stderr)
    return m


# ---------------------------------------------------------------------------
# _extract_gist_id
# ---------------------------------------------------------------------------


class TestExtractGistId:
    def test_full_url(self) -> None:
        url = "https://gist.github.com/user/abc123def456abc123de"
        assert _extract_gist_id(url) == "abc123def456abc123de"

    def test_url_without_username(self) -> None:
        url = "https://gist.github.com/abc123def456abc123de"
        assert _extract_gist_id(url) == "abc123def456abc123de"

    def test_raw_id(self) -> None:
        gist_id = "abc123def456abc123de"
        assert _extract_gist_id(gist_id) == gist_id

    def test_invalid_raises(self) -> None:
        with pytest.raises(PublisherError, match="Could not extract"):
            _extract_gist_id("not-a-gist-url")


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


class TestPublish:
    def test_publish_returns_url(self) -> None:
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_ok("https://gist.github.com/user/abc123def456abc123de\n"),
            ]
            url = publish({"CLAUDE.md": "# Hello"}, description="test")
        assert url == "https://gist.github.com/user/abc123def456abc123de"

    def test_publish_passes_public_flag(self) -> None:
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_ok("https://gist.github.com/user/abc123def456abc123de\n"),
            ]
            publish({"CLAUDE.md": "# Hello"}, description="test", public=True)
            # Check that --public was in the gh command
            create_call = mock_run.call_args_list[1]
            cmd = create_call[0][0]
            assert "--public" in cmd

    def test_publish_raises_if_gh_not_authenticated(self) -> None:
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run_fail("not authenticated")
            with pytest.raises(PublisherError, match="not installed or not authenticated"):
                publish({"CLAUDE.md": "content"})

    def test_publish_raises_on_gist_create_failure(self) -> None:
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_fail("rate limit exceeded"),
            ]
            with pytest.raises(PublisherError, match="gh gist create failed"):
                publish({"CLAUDE.md": "content"})

    def test_publish_raises_on_unexpected_output(self) -> None:
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_ok("not-a-url"),
            ]
            with pytest.raises(PublisherError, match="Unexpected output"):
                publish({"CLAUDE.md": "content"})

    def test_publish_multiple_files(self) -> None:
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_ok("https://gist.github.com/user/abc123def456abc123de\n"),
            ]
            url = publish(
                {"CLAUDE.md": "# Hello", "PLAN.md": "# Plan"},
                description="multi-file test",
            )
        assert url.startswith("https://")


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------


class TestPull:
    def _gist_api_response(self) -> str:
        return json.dumps(
            {
                "files": {
                    "CLAUDE.md": {"content": "# Pulled content"},
                    "PLAN.md": {"content": "# Pulled plan"},
                }
            }
        )

    def test_pull_writes_files(self, tmp_path: Path) -> None:
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_ok(self._gist_api_response()),
            ]
            written = pull("https://gist.github.com/user/abc123def456abc123de", tmp_path)
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "PLAN.md").exists()
        assert len(written) == 2

    def test_pull_content_correct(self, tmp_path: Path) -> None:
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_ok(self._gist_api_response()),
            ]
            pull("https://gist.github.com/user/abc123def456abc123de", tmp_path)
        assert (tmp_path / "CLAUDE.md").read_text() == "# Pulled content"

    def test_pull_raises_if_no_files(self, tmp_path: Path) -> None:
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_ok(json.dumps({"files": {}})),
            ]
            with pytest.raises(PublisherError, match="No files found"):
                pull("https://gist.github.com/user/abc123def456abc123de", tmp_path)

    def test_pull_raises_on_api_failure(self, tmp_path: Path) -> None:
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_fail("not found"),
            ]
            with pytest.raises(PublisherError, match="Failed to fetch"):
                pull("https://gist.github.com/user/abc123def456abc123de", tmp_path)


# ---------------------------------------------------------------------------
# CLI pull subcommand
# ---------------------------------------------------------------------------


class TestPullCLI:
    def test_pull_command_success(self, tmp_path: Path) -> None:
        runner = CliRunner()
        gist_response = json.dumps({"files": {"CLAUDE.md": {"content": "# Pulled"}}})
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_ok(gist_response),
            ]
            result = runner.invoke(
                main,
                [
                    "pull",
                    "https://gist.github.com/user/abc123def456abc123de",
                    "--output",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0, result.output
        assert "Downloaded" in result.output

    def test_pull_command_error(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run_fail("not authenticated")
            result = runner.invoke(
                main,
                ["pull", "https://gist.github.com/user/abc123def456abc123de"],
            )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# CLI --publish flag
# ---------------------------------------------------------------------------


class TestPublishFlag:
    def test_publish_flag_on_main_command(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_ok("https://gist.github.com/user/abc123def456abc123de\n"),
            ]
            with patch("handover.history.HISTORY_PATH", tmp_path / "history.jsonl"):
                result = runner.invoke(
                    main,
                    [
                        "--input",
                        str(FIXTURES / "claude_single.json"),
                        "--output",
                        str(tmp_path / "out"),
                        "--no-llm",
                        "--publish",
                    ],
                )
        assert result.exit_code == 0, result.output
        assert "Published" in result.output
        assert "gist.github.com" in result.output

    def test_publish_flag_failure_is_warning_not_error(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch("handover.publisher.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _GH_AUTH_OK,
                _mock_run_fail("rate limit"),
            ]
            with patch("handover.history.HISTORY_PATH", tmp_path / "history.jsonl"):
                result = runner.invoke(
                    main,
                    [
                        "--input",
                        str(FIXTURES / "claude_single.json"),
                        "--output",
                        str(tmp_path / "out"),
                        "--no-llm",
                        "--publish",
                    ],
                )
        # Files should still be written even if publish fails
        assert (tmp_path / "out" / "CLAUDE.md").exists()
        assert result.exit_code == 0
