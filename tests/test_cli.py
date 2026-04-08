"""
Integration tests for handover CLI commands.

Uses Click's CliRunner to invoke commands without spawning a subprocess.
All Anthropic API calls are mocked.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from handover.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def make_mock_api_response(goal: str = "Build a FastAPI REST API") -> MagicMock:
    """Create a mock Anthropic API response for summarizer tests."""
    payload = {
        "goal": goal,
        "tech_stack": {"language": "Python", "framework": "FastAPI"},
        "decisions": [],
        "tasks": [
            {"title": "Set up project", "description": "", "priority": "high", "done": False}
        ],
        "constraints": [],
        "non_goals": [],
        "open_questions": [],
    }
    mock_resp = MagicMock()
    mock_resp.content = [MagicMock()]
    mock_resp.content[0].text = json.dumps(payload)
    return mock_resp


class TestMainCommandNoLLM:
    """Test main command with --no-llm to avoid API calls."""

    def test_basic_single_json_to_output_dir(self, tmp_path: Path) -> None:
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

    def test_dry_run_does_not_write_files(self, tmp_path: Path) -> None:
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
            ],
        )
        assert result.exit_code == 0, result.output
        assert not (tmp_path / "CLAUDE.md").exists()
        assert not (tmp_path / "PLAN.md").exists()

    def test_dry_run_prints_summary(self, tmp_path: Path) -> None:
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
            ],
        )
        assert "Extracted" in result.output or "dry-run" in result.output.lower()
        assert "CLAUDE.md" in result.output

    def test_bulk_jsonl_no_filter(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_bulk.jsonl"),
                "--output",
                str(tmp_path),
                "--no-llm",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "CLAUDE.md").exists()

    def test_bulk_jsonl_with_title_filter(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_bulk.jsonl"),
                "--output",
                str(tmp_path),
                "--title",
                "Auth Strategy",
                "--no-llm",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_bulk_jsonl_bad_title_gives_error(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_bulk.jsonl"),
                "--output",
                str(tmp_path),
                "--title",
                "This Title Does Not Exist XYZ",
                "--no-llm",
            ],
        )
        assert result.exit_code != 0
        assert "No conversation found" in result.output

    def test_explicit_source_flag(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(tmp_path),
                "--source",
                "claude",
                "--no-llm",
            ],
        )
        assert result.exit_code == 0, result.output

    def test_markdown_input(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.md"),
                "--output",
                str(tmp_path),
                "--no-llm",
            ],
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "CLAUDE.md").exists()

    def test_output_dir_created_automatically(self, tmp_path: Path) -> None:
        new_dir = tmp_path / "new" / "nested" / "dir"
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "claude_single.json"),
                "--output",
                str(new_dir),
                "--no-llm",
            ],
        )
        assert result.exit_code == 0, result.output
        assert new_dir.exists()

    def test_missing_input_gives_usage_error(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--output", str(tmp_path)])
        assert result.exit_code != 0

    def test_missing_output_gives_usage_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--input", str(FIXTURES / "claude_single.json")])
        assert result.exit_code != 0

    def test_version_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "handover" in result.output


class TestMainCommandWithLLM:
    """Test main command with LLM mode (mocked Anthropic)."""

    def test_llm_mode_writes_files(self, tmp_path: Path) -> None:
        with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
            mock_client.return_value.messages.create.return_value = make_mock_api_response()
            runner = CliRunner()
            result = runner.invoke(
                main,
                [
                    "--input",
                    str(FIXTURES / "claude_single.json"),
                    "--output",
                    str(tmp_path),
                ],
            )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "CLAUDE.md").exists()


class TestListCommand:
    def test_list_shows_conversations(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", str(FIXTURES / "claude_bulk.jsonl")])
        assert result.exit_code == 0, result.output
        assert "API Design Discussion" in result.output
        assert "Database Schema Planning" in result.output
        assert "Auth Strategy" in result.output

    def test_list_shows_count(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", str(FIXTURES / "claude_bulk.jsonl")])
        assert "3 conversation(s)" in result.output

    def test_list_shows_table_headers(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", str(FIXTURES / "claude_bulk.jsonl")])
        assert "ID" in result.output
        assert "TITLE" in result.output


class TestInitCommand:
    def test_init_creates_template_files(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with (
            runner.isolated_filesystem(temp_dir=tmp_path),
            patch("handover.cli.Path.home", return_value=tmp_path),
        ):
            # Patch Path.home() to use tmp_path so we don't write to real home
            result = runner.invoke(main, ["init"])
        assert result.exit_code == 0, result.output
        assert "Templates scaffolded" in result.output

    def test_init_output_mentions_template_files(self, tmp_path: Path) -> None:
        runner = CliRunner()
        with patch("handover.cli.Path.home", return_value=tmp_path):
            result = runner.invoke(main, ["init"])
        assert ".j2" in result.output


class TestGetParser:
    def test_unknown_source_raises(self) -> None:
        from handover.parsers import get_parser

        with pytest.raises(ValueError, match="No adapter registered"):
            get_parser("unknown_source_xyz")


class TestMultiSourceCLI:
    def test_chatgpt_no_llm_dry_run(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "chatgpt_single.json"),
                "--output",
                str(tmp_path / "out"),
                "--no-llm",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "chatgpt" in result.output.lower()

    def test_gemini_no_llm_dry_run(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "gemini_single.json"),
                "--output",
                str(tmp_path / "out"),
                "--no-llm",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "gemini" in result.output.lower()

    def test_list_perplexity_bulk(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["list", str(FIXTURES / "perplexity_bulk.json")])
        assert result.exit_code == 0, result.output
        assert "perp-bulk-001" in result.output
        assert "FastAPI vs Flask" in result.output

    def test_source_flag_overrides_autodetect(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--input",
                str(FIXTURES / "gemini_single.json"),
                "--output",
                str(tmp_path / "out"),
                "--source",
                "gemini",
                "--no-llm",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output


class TestMergeCommand:
    """Regression tests for the merge subcommand."""

    def test_merge_target_copilot_is_accepted(self, tmp_path: Path) -> None:
        """merge --target copilot must be a valid choice (uses dynamic registry)."""
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
                str(tmp_path / "out"),
                "--target",
                "copilot",
                "--no-llm",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0, result.output
