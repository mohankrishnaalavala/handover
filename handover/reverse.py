"""
handover/reverse.py

Reverse handover orchestrator — reads a Claude Code session log and produces
a HANDOVER.md summarising what was accomplished, files changed, tasks completed,
decisions made, and recommended next steps.

This is the Phase 4 mirror of summarizer.py, but operating on session JSONL
rather than chat exports.

Public API:
    reverse(session_file, project_dir, use_llm) -> SessionContext
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from handover.models import FileChange, SessionContext, Task
from handover.parsers.claude_code import ClaudeCodeSessionParser

# Tool names that produce file-system changes
_CREATE_TOOLS = frozenset({"Write", "NotebookEdit"})
_MODIFY_TOOLS = frozenset({"Edit", "MultiEdit"})
_DELETE_TOOLS: frozenset[str] = frozenset()  # no dedicated delete tool in Claude Code

# Claude Code context window capacity for usage estimation
_CONTEXT_WINDOW_TOKENS = 200_000

# Minimum token count to bother estimating context usage
_MIN_TOKENS_FOR_ESTIMATE = 1_000

# Patterns that signal a decision in assistant text
_DECISION_PATTERNS = [
    r"I (?:chose|decided|opted|selected|went with|used|picked)\b.{10,120}",
    r"(?:chose|using|chose to use|we (?:use|chose))\b.{10,100}",
    r"instead of\b.{5,80}",
    r"rather than\b.{5,80}",
    r"(?:approach|strategy|pattern|design)[:—]\s*.{10,120}",
]
_DECISION_RE = re.compile(
    "|".join(f"(?:{p})" for p in _DECISION_PATTERNS),
    re.IGNORECASE,
)


def reverse(
    session_file: Path,
    project_dir: Path | None = None,
    use_llm: bool = True,
) -> SessionContext:
    """
    Build a SessionContext from a Claude Code session JSONL file.

    Steps:
      1. Parse session entries via ClaudeCodeSessionParser
      2. Extract file changes, commands, last action, context usage
      3. Match tasks against PLAN.md if present in project_dir
      4. Use LLM (or heuristics) to extract decisions and next steps
      5. Return populated SessionContext

    Args:
        session_file: Path to the Claude Code session .jsonl file.
        project_dir: Root of the project (for PLAN.md lookup). Defaults to cwd.
        use_llm: If True, call the Claude API to extract decisions and next steps.
                 If False, use regex heuristics.

    Returns:
        Populated SessionContext.
    """
    parser = ClaudeCodeSessionParser()
    entries = parser.parse_session_entries(session_file)

    if not entries:
        raise ValueError(f"No session entries found in {session_file}")

    project_root = Path(project_dir).resolve() if project_dir else Path.cwd().resolve()

    # --- Basic metadata ---
    session_id = _read_session_id(entries, session_file)
    project_name = project_root.name
    started_at = _read_started_at(entries)
    git_branch = _read_git_branch(entries)
    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Structural extraction (no LLM) ---
    files_changed = _extract_file_changes(entries)
    commands_run = _extract_commands(entries)
    last_action = _extract_last_action(entries)
    context_usage_pct = _estimate_context_usage(entries)

    # --- Task matching from PLAN.md ---
    tasks_completed, tasks_remaining = _match_tasks(project_root, files_changed)

    # --- Decisions + next steps (LLM or heuristics) ---
    if use_llm:
        try:
            messages = parser.parse(session_file)
            llm_result = _extract_with_llm(messages)
            decisions = llm_result.get("decisions", [])
            next_steps = llm_result.get("next_steps", [])
        except Exception:
            decisions = _extract_decisions_heuristic(entries)
            next_steps = _build_next_steps(tasks_remaining, files_changed)
    else:
        decisions = _extract_decisions_heuristic(entries)
        next_steps = _build_next_steps(tasks_remaining, files_changed)

    return SessionContext(
        session_id=session_id,
        project_name=project_name,
        generated_at=generated_at,
        started_at=started_at,
        git_branch=git_branch,
        files_changed=files_changed,
        commands_run=commands_run,
        decisions=decisions,
        tasks_completed=tasks_completed,
        tasks_remaining=tasks_remaining,
        last_action=last_action,
        context_usage_pct=context_usage_pct,
        next_steps=next_steps,
    )


# ---------------------------------------------------------------------------
# Structural extraction helpers (no LLM)
# ---------------------------------------------------------------------------


def _read_session_id(entries: list[dict[str, Any]], fallback: Path) -> str:
    for entry in entries:
        sid = entry.get("sessionId", "")
        if sid:
            return str(sid)
    return fallback.stem


def _read_started_at(entries: list[dict[str, Any]]) -> str:
    for entry in entries:
        if entry.get("type") == "user":
            ts = entry.get("timestamp", "")
            if ts:
                return str(ts)
    return ""


def _read_git_branch(entries: list[dict[str, Any]]) -> str:
    for entry in entries:
        branch = entry.get("gitBranch", "")
        if branch:
            return str(branch)
    return ""


def _extract_file_changes(entries: list[dict[str, Any]]) -> list[FileChange]:
    """
    Scan assistant messages for tool_use blocks that touch files.
    Tracks unique paths; later tool use overwrites earlier classification.
    """
    seen: dict[str, str] = {}  # path -> action

    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name", "")
            inp = block.get("input", {})
            if not isinstance(inp, dict):
                continue

            file_path = inp.get("file_path") or inp.get("path", "")
            if not file_path:
                continue

            if name in _CREATE_TOOLS:
                # Write always means created; if we've seen it before, it's modified
                action = "modified" if file_path in seen else "created"
            elif name in _MODIFY_TOOLS:
                action = "modified"
            else:
                continue

            seen[file_path] = action

    return [FileChange(path=p, action=a) for p, a in seen.items()]


def _extract_commands(entries: list[dict[str, Any]]) -> list[str]:
    """Collect Bash commands run during the session (deduplicated, max 20)."""
    seen: list[str] = []
    seen_set: set[str] = set()

    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "tool_use"
                and block.get("name") == "Bash"
            ):
                cmd = (block.get("input") or {}).get("command", "").strip()
                if cmd and cmd not in seen_set:
                    seen.append(cmd)
                    seen_set.add(cmd)
                    if len(seen) >= 20:
                        return seen

    return seen


def _extract_last_action(entries: list[dict[str, Any]]) -> str:
    """Return a human-readable description of the last tool use in the session."""
    for entry in reversed(entries):
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for block in reversed(content):
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name: str = str(block.get("name", ""))
            inp = block.get("input") or {}
            if not isinstance(inp, dict):
                continue
            file_path = inp.get("file_path") or inp.get("path", "")
            cmd = inp.get("command", "")
            if file_path:
                return f"{name} {file_path}"
            if cmd:
                short_cmd = cmd[:80].replace("\n", " ")
                return f"Bash: {short_cmd}"
            return name
    return ""


def _estimate_context_usage(entries: list[dict[str, Any]]) -> int | None:
    """
    Estimate context usage % from the last assistant message's token usage.
    Returns None if usage data is not present or total is below threshold.
    """
    for entry in reversed(entries):
        if entry.get("type") != "assistant":
            continue
        usage = entry.get("message", {}).get("usage")
        if not isinstance(usage, dict):
            continue
        total = (
            usage.get("input_tokens", 0)
            + usage.get("cache_creation_input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0)
        )
        if total < _MIN_TOKENS_FOR_ESTIMATE:
            return None
        pct: int = int(min(100, round(total / _CONTEXT_WINDOW_TOKENS * 100)))
        return pct
    return None


def _match_tasks(
    project_root: Path, files_changed: list[FileChange]
) -> tuple[list[Task], list[Task]]:
    """
    Read PLAN.md from the project root and classify tasks as completed/remaining.

    A task is considered completed if the session edited a file whose path
    contains a significant word from the task title.  This is a heuristic —
    LLM-based matching would be more accurate.

    Returns (completed, remaining) task lists.
    """
    plan_path = project_root / "PLAN.md"
    if not plan_path.exists():
        return [], []

    text = plan_path.read_text(encoding="utf-8")
    completed: list[Task] = []
    remaining: list[Task] = []

    changed_paths_lower = " ".join(fc.path.lower() for fc in files_changed)

    for line in text.splitlines():
        # Match checkbox lines: - [x] or - [ ]
        m = re.match(r"^\s*-\s*\[([xX ])\]\s+(.+)$", line)
        if not m:
            continue
        already_done = m.group(1).lower() == "x"
        title = m.group(2).strip()

        task = Task(title=title, done=already_done)
        if already_done:
            completed.append(task)
        else:
            # Check if any significant word from this task appears in changed files
            words = [w for w in re.split(r"\W+", title.lower()) if len(w) > 4]
            touched = any(w in changed_paths_lower for w in words)
            if touched:
                task.done = True
                completed.append(task)
            else:
                remaining.append(task)

    return completed, remaining


# ---------------------------------------------------------------------------
# Heuristic extraction
# ---------------------------------------------------------------------------


def _extract_decisions_heuristic(entries: list[dict[str, Any]]) -> list[str]:
    """
    Extract decision sentences from assistant text using regex patterns.
    Returns up to 10 unique decisions.
    """
    decisions: list[str] = []
    seen: set[str] = set()

    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        if isinstance(content, list):
            text = " ".join(
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
        else:
            text = str(content)

        for match in _DECISION_RE.finditer(text):
            decision = match.group(0).strip().rstrip(".,;")
            if decision and decision not in seen:
                seen.add(decision)
                decisions.append(decision)
                if len(decisions) >= 10:
                    return decisions

    return decisions


def _build_next_steps(tasks_remaining: list[Task], files_changed: list[FileChange]) -> list[str]:
    """Build suggested next steps from remaining tasks and session context."""
    steps: list[str] = []

    # High-priority remaining tasks first
    for task in tasks_remaining:
        if task.priority == "high":
            steps.append(f"Complete: {task.title}")
    for task in tasks_remaining:
        if task.priority != "high":
            steps.append(f"Complete: {task.title}")

    if not steps and files_changed:
        steps.append("Review changed files and run tests")

    if not steps:
        steps.append("Review session output and continue implementation")

    return steps[:5]  # cap at 5


# ---------------------------------------------------------------------------
# LLM-based extraction
# ---------------------------------------------------------------------------

_REVERSE_PROMPT = """\
You are analysing a Claude Code implementation session.
Your job is to extract two things:

1. **Decisions**: Technical choices made during the session.
   Look for: library choices, architecture decisions, trade-offs, "I chose X over Y" patterns.

2. **Next steps**: What should be done immediately after this session.
   Base this on: incomplete work visible in the conversation, any TODOs mentioned,
   and natural continuation of the task.

Respond with JSON only — no markdown, no explanation:
{
  "decisions": ["decision 1", "decision 2"],
  "next_steps": ["step 1", "step 2"]
}

Limit: 8 decisions, 5 next steps. Each item should be one concise sentence.
"""


def _extract_with_llm(messages: list) -> dict[str, list[str]]:  # type: ignore[type-arg]
    """
    Use the Claude API to extract decisions and next steps from session messages.

    Args:
        messages: list[ConversationMessage] from ClaudeCodeSessionParser.parse()

    Returns:
        {"decisions": [...], "next_steps": [...]}
    """
    import anthropic

    from handover.models import HandoverAPIError

    if not messages:
        return {"decisions": [], "next_steps": []}

    # Build a compact transcript (last 40K chars to stay well within limits)
    transcript = "\n\n".join(f"[{m.role.upper()}]\n{m.content}" for m in messages)
    if len(transcript) > 40_000:
        transcript = "...(earlier messages truncated)...\n\n" + transcript[-40_000:]

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"{_REVERSE_PROMPT}\n\nSession transcript:\n\n{transcript}",
                }
            ],
        )
    except anthropic.AuthenticationError as exc:
        raise HandoverAPIError("Anthropic API authentication failed.") from exc
    except anthropic.APIError as exc:
        raise HandoverAPIError(f"Anthropic API error: {exc}") from exc

    from anthropic.types import TextBlock as _TextBlock

    first_block = response.content[0]
    raw = first_block.text.strip() if isinstance(first_block, _TextBlock) else ""
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {"decisions": [], "next_steps": []}

    return {
        "decisions": [str(d) for d in result.get("decisions", [])],
        "next_steps": [str(s) for s in result.get("next_steps", [])],
    }
