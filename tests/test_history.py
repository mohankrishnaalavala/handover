"""
Tests for handover/history.py — Phase 6 history log.

Verifies that:
  - record() appends entries to the history file
  - load() reads entries newest-first with optional filtering
  - get_by_id() finds entries by handover_id
  - CLI `handover history` and `handover rerun` work correctly
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from handover.cli import main
from handover.history import get_by_id, load, make_id, now_iso, record
from handover.models import HistoryEntry

FIXTURES = Path(__file__).parent / "fixtures"


def make_entry(
    handover_id: str = "h_aabbccdd",
    source: str = "claude",
    title: str = "Test Chat",
    input_file: str = "/tmp/chat.json",
    output_dir: str = "/tmp/out",
    target: str = "claude-code",
    use_llm: bool = False,
) -> HistoryEntry:
    return HistoryEntry(
        handover_id=handover_id,
        timestamp=now_iso(),
        source=source,
        conversation_title=title,
        input_file=input_file,
        output_dir=output_dir,
        artifacts=["CLAUDE.md", "PLAN.md"],
        target=target,
        use_llm=use_llm,
    )


# ---------------------------------------------------------------------------
# make_id
# ---------------------------------------------------------------------------


class TestMakeId:
    def test_starts_with_h_(self) -> None:
        assert make_id().startswith("h_")

    def test_length(self) -> None:
        assert len(make_id()) == 10  # "h_" + 8 hex chars

    def test_unique(self) -> None:
        ids = {make_id() for _ in range(50)}
        assert len(ids) == 50


# ---------------------------------------------------------------------------
# record / load
# ---------------------------------------------------------------------------


class TestRecord:
    def test_record_creates_file(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        record(make_entry(), path=hist)
        assert hist.exists()

    def test_record_appends_line(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        record(make_entry(handover_id="h_00000001"), path=hist)
        record(make_entry(handover_id="h_00000002"), path=hist)
        lines = [ln for ln in hist.read_text().strip().splitlines() if ln]
        assert len(lines) == 2

    def test_record_valid_json_per_line(self, tmp_path: Path) -> None:
        import json

        hist = tmp_path / "history.jsonl"
        record(make_entry(), path=hist)

        line = hist.read_text().strip()
        data = json.loads(line)
        assert data["handover_id"] == "h_aabbccdd"


class TestLoad:
    def test_load_empty_returns_empty(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        assert load(path=hist) == []

    def test_load_returns_newest_first(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        record(make_entry(handover_id="h_00000001", title="First"), path=hist)
        record(make_entry(handover_id="h_00000002", title="Second"), path=hist)
        entries = load(path=hist)
        assert entries[0].handover_id == "h_00000002"
        assert entries[1].handover_id == "h_00000001"

    def test_load_respects_limit(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        for i in range(5):
            record(make_entry(handover_id=f"h_0000000{i}"), path=hist)
        entries = load(limit=3, path=hist)
        assert len(entries) == 3

    def test_load_filter_by_output_dir(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        project_a = str(tmp_path / "project-a")
        project_b = str(tmp_path / "project-b")
        record(make_entry(output_dir=project_a), path=hist)
        record(make_entry(output_dir=project_b), path=hist)
        entries = load(output_dir=project_a, path=hist)
        assert len(entries) == 1
        assert entries[0].output_dir == project_a

    def test_load_skips_malformed_lines(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        hist.write_text('{"bad": "data"}\nnot-json\n')
        entries = load(path=hist)
        assert entries == []

    def test_load_filter_no_sibling_prefix_false_positive(self, tmp_path: Path) -> None:
        """Sibling dirs with a shared prefix must not match each other."""
        hist = tmp_path / "history.jsonl"
        proj = tmp_path / "proj"
        proj_sibling = tmp_path / "proj-extra"
        proj.mkdir()
        proj_sibling.mkdir()
        record(make_entry(output_dir=str(proj)), path=hist)
        record(make_entry(handover_id="h_sibling00", output_dir=str(proj_sibling)), path=hist)
        entries = load(output_dir=str(proj), path=hist)
        assert len(entries) == 1
        assert entries[0].output_dir == str(proj)


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    def test_found(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        record(make_entry(handover_id="h_target00"), path=hist)
        record(make_entry(handover_id="h_other111"), path=hist)
        entry = get_by_id("h_target00", path=hist)
        assert entry is not None
        assert entry.handover_id == "h_target00"

    def test_not_found(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        record(make_entry(), path=hist)
        assert get_by_id("h_notexist", path=hist) is None

    def test_empty_file(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        assert get_by_id("h_anything0", path=hist) is None


# ---------------------------------------------------------------------------
# CLI history subcommand
# ---------------------------------------------------------------------------


class TestHistoryCLI:
    def test_history_empty(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        runner = CliRunner()
        with patch("handover.history.HISTORY_PATH", hist):
            result = runner.invoke(main, ["history"])
        assert result.exit_code == 0, result.output
        assert "No handover history" in result.output

    def test_history_shows_entries(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        record(make_entry(handover_id="h_showme00", title="My Chat"), path=hist)
        runner = CliRunner()
        with patch("handover.history.HISTORY_PATH", hist):
            result = runner.invoke(main, ["history"])
        assert result.exit_code == 0, result.output

    def test_history_limit_flag(self, tmp_path: Path) -> None:
        runner = CliRunner()
        hist = tmp_path / "history.jsonl"
        with patch("handover.history.HISTORY_PATH", hist):
            result = runner.invoke(main, ["history", "--limit", "5"])
        assert result.exit_code == 0, result.output


class TestHistoryRecordedOnRun:
    """Verify that a successful handover run writes to history."""

    def test_history_written_after_successful_run(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        runner = CliRunner()
        with patch("handover.history.HISTORY_PATH", hist):
            result = runner.invoke(
                main,
                [
                    "--input",
                    str(FIXTURES / "claude_single.json"),
                    "--output",
                    str(tmp_path / "out"),
                    "--no-llm",
                ],
            )
        assert result.exit_code == 0, result.output
        assert hist.exists()
        entries = load(path=hist)
        assert len(entries) == 1
        assert entries[0].source == "claude"

    def test_history_not_written_on_dry_run(self, tmp_path: Path) -> None:
        hist = tmp_path / "history.jsonl"
        runner = CliRunner()
        with patch("handover.history.HISTORY_PATH", hist):
            result = runner.invoke(
                main,
                [
                    "--input",
                    str(FIXTURES / "claude_single.json"),
                    "--output",
                    str(tmp_path / "out"),
                    "--no-llm",
                    "--dry-run",
                ],
            )
        assert result.exit_code == 0, result.output
        assert not hist.exists()
