"""
handover/diff.py

v1.2.0 — Parse an existing `.handover/` directory back into structured data
and compute a delta against a freshly extracted context.

Pure computation — reads files but never writes. The caller (updater.py)
is responsible for applying the delta.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from handover.models import (
    Backlog,
    BacklogTask,
    Decision,
    HandoverContext,
    Milestone,
    Task,
    UpdateDelta,
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_existing_handover(handover_dir: Path) -> tuple[HandoverContext, Backlog]:
    """Read `.handover/` markdown + backlog.json, reconstruct structured data.

    Args:
        handover_dir: Path to the `.handover/` directory.

    Returns:
        A tuple of (HandoverContext, Backlog) reconstructed from files on disk.
    """
    ctx = HandoverContext(source="existing")

    # overview.md -> goal
    overview_path = handover_dir / "context" / "overview.md"
    if overview_path.exists():
        ctx.goal = _parse_goal_md(overview_path.read_text(encoding="utf-8"))

    # architecture.md -> tech_stack
    arch_path = handover_dir / "context" / "architecture.md"
    if arch_path.exists():
        ctx.tech_stack = _parse_tech_stack_md(arch_path.read_text(encoding="utf-8"))

    # decisions.md -> decisions
    dec_path = handover_dir / "context" / "decisions.md"
    if dec_path.exists():
        ctx.decisions = _parse_decisions_md(dec_path.read_text(encoding="utf-8"))

    # constraints.md -> constraints, non_goals
    con_path = handover_dir / "context" / "constraints.md"
    if con_path.exists():
        ctx.constraints, ctx.non_goals = _parse_constraints_md(con_path.read_text(encoding="utf-8"))

    # risks.md -> open_questions
    risks_path = handover_dir / "context" / "risks.md"
    if risks_path.exists():
        ctx.open_questions = _parse_open_questions_md(risks_path.read_text(encoding="utf-8"))

    # work/tasks.md -> tasks
    tasks_path = handover_dir / "work" / "tasks.md"
    if tasks_path.exists():
        ctx.tasks = _parse_tasks_md(tasks_path.read_text(encoding="utf-8"))

    # work/backlog.json -> Backlog
    backlog_path = handover_dir / "work" / "backlog.json"
    backlog = Backlog()
    if backlog_path.exists():
        backlog = _parse_backlog_json(backlog_path.read_text(encoding="utf-8"))

    return ctx, backlog


def compute_delta(
    existing_ctx: HandoverContext,
    existing_backlog: Backlog,
    fresh_ctx: HandoverContext,
    fresh_backlog: Backlog,
) -> UpdateDelta:
    """Compare existing vs fresh context and return the delta.

    Rules:
    - Tasks already done in existing -> preserved (never untick)
    - New tasks not in existing -> new_tasks
    - Decisions: same topic + same conclusion -> skip
    - Decisions: same topic + different conclusion -> revised_decisions
    - Decisions: new topic -> new_decisions
    - Constraints/non_goals/open_questions: set difference
    - Tech stack: new keys -> new_tech_stack
    - Backlog: new tasks appended, done tasks preserved
    """
    now = datetime.now(UTC).isoformat()

    # --- Tasks ---
    existing_titles = {t.title.lower() for t in existing_ctx.tasks}
    done_titles = [t.title for t in existing_ctx.tasks if t.done]
    new_tasks = [t for t in fresh_ctx.tasks if t.title.lower() not in existing_titles]

    # --- Decisions ---
    existing_topics = {d.topic.lower(): d for d in existing_ctx.decisions}
    new_decisions: list[Decision] = []
    revised_decisions: list[tuple[Decision, Decision]] = []
    for d in fresh_ctx.decisions:
        key = d.topic.lower()
        if key not in existing_topics:
            new_decisions.append(d)
        elif d.decision.lower() != existing_topics[key].decision.lower():
            revised_decisions.append((existing_topics[key], d))

    # --- Constraints / non-goals / open questions ---
    existing_constraints_lower = {c.lower() for c in existing_ctx.constraints}
    new_constraints = [
        c for c in fresh_ctx.constraints if c.lower() not in existing_constraints_lower
    ]

    existing_ng_lower = {n.lower() for n in existing_ctx.non_goals}
    new_non_goals = [n for n in fresh_ctx.non_goals if n.lower() not in existing_ng_lower]

    existing_oq_lower = {q.lower() for q in existing_ctx.open_questions}
    new_open_questions = [q for q in fresh_ctx.open_questions if q.lower() not in existing_oq_lower]

    # --- Tech stack ---
    new_tech_stack: dict[str, str] = {}
    for key, value in fresh_ctx.tech_stack.items():
        if key not in existing_ctx.tech_stack:
            new_tech_stack[key] = value

    # --- Backlog ---
    existing_backlog_ids = {t.id for t in existing_backlog.tasks}
    existing_backlog_titles = {t.title.lower() for t in existing_backlog.tasks}
    new_backlog_tasks = [
        t
        for t in fresh_backlog.tasks
        if t.id not in existing_backlog_ids and t.title.lower() not in existing_backlog_titles
    ]
    preserved_done_backlog = [t.id for t in existing_backlog.tasks if t.done]

    return UpdateDelta(
        new_tasks=new_tasks,
        preserved_done_tasks=done_titles,
        new_decisions=new_decisions,
        revised_decisions=revised_decisions,
        new_constraints=new_constraints,
        new_non_goals=new_non_goals,
        new_open_questions=new_open_questions,
        new_tech_stack=new_tech_stack,
        new_backlog_tasks=new_backlog_tasks,
        preserved_done_backlog=preserved_done_backlog,
        updated_at=now,
    )


# ---------------------------------------------------------------------------
# Markdown parsers — target the known output format of scaffold_heuristics.py
# ---------------------------------------------------------------------------

_TASK_RE = re.compile(r"^- \[([ xX])\] (.+?)(\s+\*\(high priority\)\*)?$", re.MULTILINE)

_ADR_HEADER_RE = re.compile(r"^## ADR-\d{3} — (.+)$", re.MULTILINE)

_DECISION_RE = re.compile(r"\*\*Decision:\*\*\s*\n\n(.+?)(?:\n\n|$)", re.DOTALL)
_RATIONALE_RE = re.compile(r"\*\*Context:\*\*\s*\n\n(.+?)(?:\n\n|$)", re.DOTALL)

_TECH_STACK_RE = re.compile(r"^- \*\*(.+?)\*\*: (.+)$", re.MULTILINE)

_LIST_ITEM_RE = re.compile(r"^- (?:\[ \] )?(.+)$", re.MULTILINE)


def _parse_tasks_md(content: str) -> list[Task]:
    """Parse markdown checklist into Task objects."""
    tasks: list[Task] = []
    for match in _TASK_RE.finditer(content):
        done = match.group(1).lower() == "x"
        title_text = match.group(2).strip()
        priority = "high" if match.group(3) else "medium"
        tasks.append(Task(title=title_text, done=done, priority=priority))
    return tasks


def _parse_decisions_md(content: str) -> list[Decision]:
    """Parse ADR-formatted markdown into Decision objects."""
    if "_No decisions extracted" in content:
        return []

    decisions: list[Decision] = []
    # Split on ADR headers
    headers = list(_ADR_HEADER_RE.finditer(content))
    for i, header_match in enumerate(headers):
        topic = header_match.group(1).strip()
        # Get the block between this header and the next (or end)
        start = header_match.end()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(content)
        block = content[start:end]

        decision_match = _DECISION_RE.search(block)
        rationale_match = _RATIONALE_RE.search(block)

        decision_text = decision_match.group(1).strip() if decision_match else ""
        rationale_text = rationale_match.group(1).strip() if rationale_match else ""

        # Skip placeholder text
        if decision_text == "_No decision recorded._":
            decision_text = ""
        if rationale_text == "_No rationale recorded._":
            rationale_text = ""

        decisions.append(Decision(topic=topic, decision=decision_text, rationale=rationale_text))
    return decisions


def _parse_constraints_md(content: str) -> tuple[list[str], list[str]]:
    """Parse constraints.md into (constraints, non_goals) lists."""
    if "_No constraints or non-goals recorded._" in content:
        return [], []

    constraints: list[str] = []
    non_goals: list[str] = []

    # Split on ## headings
    sections = re.split(r"^## ", content, flags=re.MULTILINE)
    for section in sections:
        if section.startswith("Constraints"):
            for m in _LIST_ITEM_RE.finditer(section):
                constraints.append(m.group(1).strip())
        elif section.startswith("Non-goals"):
            for m in _LIST_ITEM_RE.finditer(section):
                non_goals.append(m.group(1).strip())

    return constraints, non_goals


def _parse_open_questions_md(content: str) -> list[str]:
    """Parse risks.md into a list of open questions."""
    if "_No open questions or risks recorded._" in content:
        return []
    questions: list[str] = []
    for m in re.finditer(r"^- \[ \] (.+)$", content, re.MULTILINE):
        questions.append(m.group(1).strip())
    return questions


def _parse_tech_stack_md(content: str) -> dict[str, str]:
    """Parse '- **Key**: value' lines from architecture.md into a dict."""
    result: dict[str, str] = {}
    for m in _TECH_STACK_RE.finditer(content):
        result[m.group(1).strip().lower()] = m.group(2).strip()
    return result


def _parse_goal_md(content: str) -> str:
    """Extract goal text from overview.md (content under ## Goal heading)."""
    sections = re.split(r"^## ", content, flags=re.MULTILINE)
    for section in sections:
        if section.startswith("Goal"):
            lines = section.split("\n", 1)
            if len(lines) > 1:
                return lines[1].strip()
    return ""


def _parse_backlog_json(content: str) -> Backlog:
    """Parse backlog.json into a Backlog dataclass."""
    data = json.loads(content)
    tasks = [
        BacklogTask(
            id=t.get("id", ""),
            title=t.get("title", ""),
            description=t.get("description", ""),
            phase=t.get("phase", "1"),
            priority=t.get("priority", "medium"),
            done=t.get("done", False),
            tags=t.get("tags", []),
            added_at=t.get("added_at", ""),
            done_at=t.get("done_at"),
        )
        for t in data.get("tasks", [])
    ]
    milestones = [
        Milestone(
            id=m.get("id", ""),
            title=m.get("title", ""),
            task_ids=m.get("task_ids", []),
        )
        for m in data.get("milestones", [])
    ]
    return Backlog(
        schema_version=data.get("schema_version", "1.0"),
        updated_at=data.get("updated_at", ""),
        project=data.get("project", ""),
        tasks=tasks,
        milestones=milestones,
    )
