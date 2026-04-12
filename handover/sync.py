"""
handover/sync.py

v1.2.1 — Backlog sync from codebase state.

Reads `.handover/work/backlog.json`, correlates tasks against:
  - `.handover/codebase/index.md` (file listing + symbol map)
  - recent `git log` (if the project is a git repo)

Produces an updated backlog with `done: true` + `done_at` set on tasks
the evidence indicates are complete. Symmetric to the forward scaffold
flow: scaffold_extractor turns chat → tasks; sync turns code → task
status.

Two modes:
  - LLM (default): one Claude API call, returns {task_id: bool}
  - Heuristic (`use_llm=False`): keyword match task tokens against
    file paths + symbols in the codebase index

Public API:
  - sync_backlog(project_dir, use_llm) -> SyncResult
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from handover.models import HandoverAPIError

_MODEL = "claude-sonnet-4-6"
_MAX_INDEX_CHARS = 20_000
_MAX_GIT_LOG_ENTRIES = 50

# Tokens that add no signal when keyword-matching task titles.
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "and",
        "the",
        "to",
        "of",
        "for",
        "in",
        "on",
        "with",
        "build",
        "add",
        "create",
        "update",
        "implement",
        "use",
        "run",
        "set",
        "setup",
        "configure",
        "from",
        "into",
        "by",
        "as",
        "at",
        "via",
        "is",
        "are",
        "be",
        "new",
        "all",
        "any",
        "this",
        "that",
    }
)


@dataclass
class SyncResult:
    """Summary of a sync run."""

    tasks_total: int = 0
    tasks_marked_done: int = 0
    already_done: int = 0
    task_ids_marked_done: list[str] = field(default_factory=list)
    mode: str = "heuristic"  # "llm" | "heuristic"
    dry_run: bool = False


SYNC_PROMPT = """\
You are auditing whether backlog tasks are complete based on code evidence.

Given the backlog tasks and the codebase index + recent commits below,
return ONE JSON object mapping task_id to a boolean: true if the task
appears complete, false otherwise.

Be conservative: mark `true` ONLY when there is clear evidence (a matching
file, symbol, commit message, or component) that the task has been
implemented. When in doubt, return `false`.

Return ONLY valid JSON, no markdown fences, no explanation. Example:
{{"task-001": true, "task-002": false, "task-003": true}}

Backlog tasks:
{tasks}

Codebase index (abbreviated):
{index}

Recent git log:
{git_log}
"""


def sync_backlog(
    project_dir: Path,
    *,
    use_llm: bool = True,
    dry_run: bool = False,
) -> SyncResult:
    """
    Update `.handover/work/backlog.json` based on codebase state.

    Args:
        project_dir: Project root (must contain `.handover/work/backlog.json`).
        use_llm: When True, uses Claude to judge task completion. When False,
            falls back to keyword matching.
        dry_run: When True, compute the delta but do not write.

    Returns:
        A `SyncResult` with counts and the list of task IDs newly marked done.

    Raises:
        FileNotFoundError: If the backlog file is missing.
        HandoverAPIError: If use_llm=True and the API call fails.
    """
    backlog_path = project_dir / ".handover" / "work" / "backlog.json"
    if not backlog_path.exists():
        raise FileNotFoundError(
            f".handover/work/backlog.json not found at {backlog_path}. "
            f"Run `handover` first to scaffold the project."
        )

    backlog = json.loads(backlog_path.read_text())
    tasks = backlog.get("tasks", [])

    index_text = _read_index(project_dir)
    git_log = _read_git_log(project_dir)

    if use_llm:
        decisions = _decide_with_llm(tasks, index_text, git_log)
        mode = "llm"
    else:
        decisions = _decide_with_heuristics(tasks, index_text, git_log)
        mode = "heuristic"

    now = _now_iso()
    newly_done: list[str] = []
    already_done = 0
    for task in tasks:
        if task.get("done"):
            already_done += 1
            continue
        task_id = task.get("id", "")
        if decisions.get(task_id, False):
            task["done"] = True
            task["done_at"] = now
            newly_done.append(task_id)

    backlog["tasks"] = tasks
    backlog["updated_at"] = now

    if not dry_run:
        backlog_path.write_text(json.dumps(backlog, indent=2) + "\n")

    return SyncResult(
        tasks_total=len(tasks),
        tasks_marked_done=len(newly_done),
        already_done=already_done,
        task_ids_marked_done=newly_done,
        mode=mode,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------------------
# LLM path
# ---------------------------------------------------------------------------


def _decide_with_llm(
    tasks: list[dict[str, object]],
    index_text: str,
    git_log: str,
) -> dict[str, bool]:
    """One Claude API call. Returns a {task_id: bool} map."""
    if not tasks:
        return {}

    tasks_json = json.dumps(
        [
            {
                "id": t.get("id", ""),
                "title": t.get("title", ""),
                "description": t.get("description", ""),
            }
            for t in tasks
            if not t.get("done")
        ],
        indent=2,
    )

    prompt = SYNC_PROMPT.format(
        tasks=tasks_json,
        index=index_text[:_MAX_INDEX_CHARS] or "(empty)",
        git_log=git_log or "(not a git repo or no commits)",
    )

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as e:
        raise HandoverAPIError(
            "ANTHROPIC_API_KEY is not set or invalid. Use --no-llm for heuristic-only sync."
        ) from e
    except anthropic.APIError as e:
        raise HandoverAPIError(
            f"Anthropic API error during sync: {e}. Use --no-llm as fallback."
        ) from e

    raw_text = getattr(response.content[0], "text", None)
    if not isinstance(raw_text, str):
        raise HandoverAPIError("Unexpected response block type from API.")

    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise HandoverAPIError(
            f"Sync model returned invalid JSON: {e}. Raw: {raw_text[:200]}"
        ) from e

    if not isinstance(raw, dict):
        raise HandoverAPIError("Sync model returned non-object JSON.")

    return {str(k): bool(v) for k, v in raw.items()}


# ---------------------------------------------------------------------------
# Heuristic path
# ---------------------------------------------------------------------------


def _decide_with_heuristics(
    tasks: list[dict[str, object]],
    index_text: str,
    git_log: str,
) -> dict[str, bool]:
    """
    Mark a task done when ≥2 distinct non-stopword tokens from its
    title appear in the codebase index or git log. Conservative by design.
    """
    haystack = (index_text + "\n" + git_log).lower()
    decisions: dict[str, bool] = {}
    for task in tasks:
        if task.get("done"):
            continue
        task_id = str(task.get("id", ""))
        title = str(task.get("title", ""))
        tokens = _tokenize(title)
        if len(tokens) < 2:
            decisions[task_id] = False
            continue
        hits = sum(1 for tok in tokens if tok in haystack)
        decisions[task_id] = hits >= 2
    return decisions


def _tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower())
    return [w for w in words if w not in _STOPWORDS]


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


def _read_index(project_dir: Path) -> str:
    index_path = project_dir / ".handover" / "codebase" / "index.md"
    if not index_path.exists():
        return ""
    return index_path.read_text()


def _read_git_log(project_dir: Path) -> str:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(project_dir),
                "log",
                f"-n{_MAX_GIT_LOG_ENTRIES}",
                "--oneline",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
