"""
handover/history.py

History log for all past handover runs.

Writes one JSON line per run to ~/.handover/history.jsonl after every
successful non-dry-run invocation of `handover` main command.

Phase 6 — Ecosystem & Developer Experience.
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import secrets
from pathlib import Path

from handover.models import HistoryEntry

HISTORY_PATH = Path.home() / ".handover" / "history.jsonl"


def make_id() -> str:
    """Generate a short unique handover ID like 'h_3f9a2c1b'."""
    return "h_" + secrets.token_hex(4)


def record(entry: HistoryEntry, path: Path | None = None) -> None:
    """
    Append a HistoryEntry to the history file.

    Args:
        entry: The HistoryEntry to persist.
        path: Override the history file path (used in tests).
              Defaults to HISTORY_PATH resolved at call time.
    """
    _path = path if path is not None else HISTORY_PATH
    _path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(dataclasses.asdict(entry), ensure_ascii=False)
    with _path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load(
    limit: int = 20,
    output_dir: str | None = None,
    path: Path | None = None,
) -> list[HistoryEntry]:
    """
    Load history entries, most recent first.

    Args:
        limit: Maximum number of entries to return.
        output_dir: If set, filter to entries whose output_dir starts with
                    this path (resolves to absolute before comparison).
        path: Override the history file path (used in tests).

    Returns:
        List of HistoryEntry objects, newest first.
    """
    _path = path if path is not None else HISTORY_PATH
    if not _path.exists():
        return []

    entries: list[HistoryEntry] = []
    filter_path = Path(output_dir).resolve() if output_dir else None

    with _path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                entry = HistoryEntry(**raw)
                if filter_path is not None:
                    entry_path = Path(entry.output_dir).resolve()
                    if entry_path != filter_path and filter_path not in entry_path.parents:
                        continue
                entries.append(entry)
            except (json.JSONDecodeError, TypeError):
                continue  # skip malformed lines

    entries.reverse()  # newest first
    return entries[:limit]


def get_by_id(handover_id: str, path: Path | None = None) -> HistoryEntry | None:
    """
    Find a specific history entry by its handover_id.

    Args:
        handover_id: The ID to look for (e.g. "h_3f9a2c1b").
        path: Override the history file path (used in tests).
              Defaults to HISTORY_PATH resolved at call time.

    Returns:
        The matching HistoryEntry, or None if not found.
    """
    _path = path if path is not None else HISTORY_PATH
    if not _path.exists():
        return None

    with _path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                if raw.get("handover_id") == handover_id:
                    return HistoryEntry(**raw)
            except (json.JSONDecodeError, TypeError):
                continue
    return None


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.datetime.utcnow().isoformat() + "Z"
