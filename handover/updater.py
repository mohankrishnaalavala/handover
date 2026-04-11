"""
handover/updater.py

v1.2.0 — Apply an UpdateDelta to an existing `.handover/` directory.

Writes only the files that changed. Preserves completed task marks and
manual edits. Regenerates prompt files (always safe — they are templates).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from handover.models import Decision, Task, UpdateDelta

# Prompt template names that are always safe to regenerate.
_PROMPT_TEMPLATES: list[tuple[str, str]] = [
    ("prompt_implement.j2", "prompts/implement.md"),
    ("prompt_review.j2", "prompts/review.md"),
    ("prompt_debug.j2", "prompts/debug.md"),
    ("prompt_test.j2", "prompts/test.md"),
    ("prompt_onboard.j2", "prompts/onboard.md"),
    ("prompt_continue.j2", "prompts/continue.md"),
]


def apply_update(
    delta: UpdateDelta,
    handover_dir: Path,
    *,
    dry_run: bool = False,
    no_conflict: bool = False,
    scaffold: object | None = None,
) -> list[Path]:
    """Apply delta to existing `.handover/` directory.

    Args:
        delta: The computed UpdateDelta.
        handover_dir: Path to the `.handover/` directory.
        dry_run: If True, return paths without writing.
        no_conflict: If True, take latest decision — no conflict markers.
        scaffold: Optional ScaffoldContext for regenerating prompt files.

    Returns:
        List of files that were (or would be) written.
    """
    written: list[Path] = []
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    # --- tasks.md ---
    if delta.new_tasks:
        tasks_path = handover_dir / "work" / "tasks.md"
        if tasks_path.exists():
            content = tasks_path.read_text(encoding="utf-8")
            content = _append_tasks(content, delta.new_tasks, today)
            if not dry_run:
                tasks_path.write_text(content, encoding="utf-8")
            written.append(tasks_path)

    # --- decisions.md ---
    if delta.new_decisions or delta.revised_decisions:
        dec_path = handover_dir / "context" / "decisions.md"
        if dec_path.exists():
            content = dec_path.read_text(encoding="utf-8")
            content = _append_decisions(
                content, delta.new_decisions, delta.revised_decisions, no_conflict
            )
            if not dry_run:
                dec_path.write_text(content, encoding="utf-8")
            written.append(dec_path)

    # --- constraints.md ---
    if delta.new_constraints or delta.new_non_goals:
        con_path = handover_dir / "context" / "constraints.md"
        if con_path.exists():
            content = con_path.read_text(encoding="utf-8")
            if delta.new_constraints:
                content = _append_list_items(content, "Constraints", delta.new_constraints)
            if delta.new_non_goals:
                content = _append_list_items(content, "Non-goals", delta.new_non_goals)
            if not dry_run:
                con_path.write_text(content, encoding="utf-8")
            written.append(con_path)

    # --- risks.md ---
    if delta.new_open_questions:
        risks_path = handover_dir / "context" / "risks.md"
        if risks_path.exists():
            content = risks_path.read_text(encoding="utf-8")
            content = _append_open_questions(content, delta.new_open_questions)
            if not dry_run:
                risks_path.write_text(content, encoding="utf-8")
            written.append(risks_path)

    # --- architecture.md (tech stack) ---
    if delta.new_tech_stack:
        arch_path = handover_dir / "context" / "architecture.md"
        if arch_path.exists():
            content = arch_path.read_text(encoding="utf-8")
            content = _append_tech_stack(content, delta.new_tech_stack)
            if not dry_run:
                arch_path.write_text(content, encoding="utf-8")
            written.append(arch_path)

    # --- backlog.json ---
    if delta.new_backlog_tasks:
        backlog_path = handover_dir / "work" / "backlog.json"
        if backlog_path.exists():
            existing_data = json.loads(backlog_path.read_text(encoding="utf-8"))
            merged = _merge_backlog_json(existing_data, delta)
            if not dry_run:
                backlog_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
            written.append(backlog_path)

    # --- Prompt files (always regenerate if scaffold provided) ---
    if scaffold is not None:
        written.extend(_regenerate_prompts(handover_dir, scaffold, dry_run))

    return written


# ---------------------------------------------------------------------------
# Per-file update helpers
# ---------------------------------------------------------------------------


def _append_tasks(existing_content: str, new_tasks: list[Task], date: str) -> str:
    """Append new tasks under a dated heading."""
    lines = [
        "",
        f"## New (added {date})",
        "",
    ]
    for t in new_tasks:
        check = "x" if t.done else " "
        suffix = " *(high priority)*" if t.priority == "high" else ""
        lines.append(f"- [{check}] {t.title}{suffix}")
        if t.description:
            lines.append(f"  - {t.description}")

    return existing_content.rstrip() + "\n" + "\n".join(lines) + "\n"


def _append_decisions(
    existing_content: str,
    new_decisions: list[Decision],
    revised: list[tuple[Decision, Decision]],
    no_conflict: bool,
) -> str:
    """Append new ADRs and mark revised ones with warning marker."""
    # Find the highest existing ADR number
    numbers = [int(m) for m in re.findall(r"## ADR-(\d{3})", existing_content)]
    next_num = max(numbers) + 1 if numbers else 1

    parts: list[str] = [existing_content.rstrip()]

    # Revised decisions (conflict markers)
    if revised and not no_conflict:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        for old_dec, new_dec in revised:
            parts.append("")
            parts.append(f"## REVISED (detected {today})")
            parts.append("")
            parts.append(f"**Previous ({old_dec.topic}):** {old_dec.decision}")
            parts.append(f"**New:** {new_dec.decision}")
            parts.append("**Action:** Resolve manually — update or delete the old ADR entry.")

    # New decisions as ADR entries
    for d in new_decisions:
        parts.append("")
        parts.append(f"## ADR-{next_num:03d} — {d.topic or 'Untitled decision'}")
        parts.append("")
        parts.append("**Status:** Accepted")
        parts.append("")
        parts.append("**Context:**")
        parts.append("")
        parts.append(d.rationale or "_No rationale recorded._")
        parts.append("")
        parts.append("**Decision:**")
        parts.append("")
        parts.append(d.decision or "_No decision recorded._")
        parts.append("")
        parts.append("**Consequences:**")
        parts.append("")
        parts.append("_Document the trade-offs here._")
        next_num += 1

    return "\n".join(parts) + "\n"


def _append_list_items(existing_content: str, section_header: str, new_items: list[str]) -> str:
    """Append new items to a section identified by ## heading."""
    # Find the section and append items after the last list item in it
    pattern = rf"(## {re.escape(section_header)}\b.*?)(\n## |\Z)"
    match = re.search(pattern, existing_content, re.DOTALL)
    if match:
        section = match.group(1).rstrip()
        new_lines = "\n".join(f"- {item}" for item in new_items)
        replacement = section + "\n" + new_lines
        after_start = match.start() + len(match.group(1))
        return existing_content[: match.start()] + replacement + existing_content[after_start:]

    # Section not found — append at end
    new_lines = "\n".join(f"- {item}" for item in new_items)
    return existing_content.rstrip() + f"\n\n## {section_header}\n\n{new_lines}\n"


def _append_open_questions(existing_content: str, new_questions: list[str]) -> str:
    """Append new open questions to risks.md."""
    new_lines = "\n".join(f"- [ ] {q}" for q in new_questions)
    if "_No open questions or risks recorded._" in existing_content:
        return f"## Open questions\n\n{new_lines}\n"
    return existing_content.rstrip() + "\n" + new_lines + "\n"


def _append_tech_stack(existing_content: str, new_entries: dict[str, str]) -> str:
    """Append new tech stack entries to the ## Tech stack section."""
    new_lines = "\n".join(
        f"- **{key.capitalize()}**: {value}" for key, value in new_entries.items()
    )
    # Find the end of the Tech stack section (before ## System design)
    match = re.search(r"(## System design)", existing_content)
    if match:
        insert_pos = match.start()
        return (
            existing_content[:insert_pos].rstrip()
            + "\n"
            + new_lines
            + "\n\n"
            + existing_content[insert_pos:]
        )
    # No System design section — append after Tech stack
    return existing_content.rstrip() + "\n" + new_lines + "\n"


def _merge_backlog_json(existing_data: dict[str, Any], delta: UpdateDelta) -> dict[str, Any]:
    """Merge new backlog tasks into existing backlog data."""
    # Preserve done status on existing tasks
    for task in existing_data.get("tasks", []):
        if task.get("id") in delta.preserved_done_backlog:
            task["done"] = True

    # Append new tasks
    for bt in delta.new_backlog_tasks:
        existing_data.setdefault("tasks", []).append(asdict(bt))

    existing_data["updated_at"] = delta.updated_at
    return existing_data


def _regenerate_prompts(
    handover_dir: Path,
    scaffold: object,
    dry_run: bool,
) -> list[Path]:
    """Regenerate all prompt files from templates."""
    from handover import __version__
    from handover.universal_generator import _make_env

    env = _make_env()
    written: list[Path] = []
    for template_name, rel_path in _PROMPT_TEMPLATES:
        out_path = handover_dir / rel_path
        if not dry_run:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            template = env.get_template(template_name)
            rendered = template.render(scaffold=scaffold, version=__version__)
            out_path.write_text(rendered, encoding="utf-8")
        written.append(out_path)
    return written
