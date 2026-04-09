"""
handover/scaffold_heuristics.py

Rule-based fallback for the v1.1.0 two-layer scaffold.

When `--no-llm` is passed (or the user has no Anthropic API key) the universal
generator still needs the 13 markdown bodies that make up `.handover/`. This
module produces them deterministically from a populated `HandoverContext`,
without making any network calls.

Pure functions only — no I/O, no Jinja2, no Anthropic. Fully unit-testable.
"""

from __future__ import annotations

from handover.models import HandoverContext, ScaffoldContext


def extract_scaffold_no_llm(handover_context: HandoverContext) -> ScaffoldContext:
    """
    Build a `ScaffoldContext` from a `HandoverContext` using simple rules.

    Every markdown body is produced from existing `HandoverContext` fields.
    The caller is responsible for attaching `manifest`, `backlog`, and
    domain-detected agents/skills/commands/hooks (those concerns live in
    `scaffold_extractor.py`).

    Args:
        handover_context: Populated context from the summarizer.

    Returns:
        A `ScaffoldContext` with all 13 markdown body fields populated.
    """
    return ScaffoldContext(
        overview=_overview(handover_context),
        architecture=_architecture(handover_context),
        decisions=_decisions(handover_context),
        constraints=_constraints(handover_context),
        risks=_risks(handover_context),
        acceptance_criteria=_acceptance_criteria(handover_context),
        work_spec=_work_spec(handover_context),
        work_tasks=_work_tasks(handover_context),
        work_milestones=_work_milestones(handover_context),
        standards_coding=_standards_coding(handover_context),
        standards_testing=_standards_testing(handover_context),
        standards_security=_standards_security(handover_context),
        standards_release=_standards_release(handover_context),
    )


# ---------------------------------------------------------------------------
# Per-section builders
# ---------------------------------------------------------------------------


def _overview(ctx: HandoverContext) -> str:
    goal = ctx.goal or "(goal not detected — fill in manually)"
    lines = [
        "## Goal",
        "",
        goal,
        "",
        "## Vision",
        "",
        f"Build the system described above using {_stack_summary(ctx) or 'the chosen tech stack'}.",
        "",
        "## Success criteria",
        "",
        "See `acceptance-criteria.md` for the explicit definition of done.",
    ]
    return "\n".join(lines)


def _architecture(ctx: HandoverContext) -> str:
    if not ctx.tech_stack:
        return (
            "## Tech stack\n\n_No tech stack detected — fill in manually._\n\n"
            "## System design\n\n_Document the major components here._"
        )
    rows = ["## Tech stack", ""]
    for key, value in ctx.tech_stack.items():
        rows.append(f"- **{key.capitalize()}**: {value}")
    rows.extend(
        [
            "",
            "## System design",
            "",
            "_Add a high-level component diagram and data-flow description here._",
        ]
    )
    return "\n".join(rows)


def _decisions(ctx: HandoverContext) -> str:
    if not ctx.decisions:
        return "_No decisions extracted yet._"
    blocks: list[str] = []
    for i, d in enumerate(ctx.decisions, start=1):
        blocks.append(
            "\n".join(
                [
                    f"## ADR-{i:03d} — {d.topic or 'Untitled decision'}",
                    "",
                    "**Status:** Accepted",
                    "",
                    "**Context:**",
                    "",
                    d.rationale or "_No rationale recorded._",
                    "",
                    "**Decision:**",
                    "",
                    d.decision or "_No decision recorded._",
                    "",
                    "**Consequences:**",
                    "",
                    "_Document the trade-offs here._",
                ]
            )
        )
    return "\n\n".join(blocks)


def _constraints(ctx: HandoverContext) -> str:
    parts: list[str] = []
    if ctx.constraints:
        parts.append("## Constraints")
        parts.append("")
        parts.extend(f"- {c}" for c in ctx.constraints)
    if ctx.non_goals:
        if parts:
            parts.append("")
        parts.append("## Non-goals")
        parts.append("")
        parts.extend(f"- {n}" for n in ctx.non_goals)
    if not parts:
        return "_No constraints or non-goals recorded._"
    return "\n".join(parts)


def _risks(ctx: HandoverContext) -> str:
    if not ctx.open_questions:
        return "_No open questions or risks recorded._"
    lines = ["## Open questions", ""]
    lines.extend(f"- [ ] {q}" for q in ctx.open_questions)
    return "\n".join(lines)


def _acceptance_criteria(ctx: HandoverContext) -> str:
    high = [t for t in ctx.tasks if t.priority == "high"]
    if not high:
        return "_No high-priority tasks recorded — define acceptance criteria manually._"
    lines = ["## Must-have (high-priority tasks)", ""]
    lines.extend(f"- [ ] {t.title}" for t in high)
    return "\n".join(lines)


def _work_spec(ctx: HandoverContext) -> str:
    parts = [
        "## Goal",
        "",
        ctx.goal or "_(see overview.md)_",
        "",
        "## Tech stack",
        "",
    ]
    if ctx.tech_stack:
        parts.extend(f"- **{k.capitalize()}**: {v}" for k, v in ctx.tech_stack.items())
    else:
        parts.append("_TBD_")
    parts.append("")
    parts.append("## Tasks")
    parts.append("")
    if ctx.tasks:
        parts.extend(f"- {t.title}" for t in ctx.tasks)
    else:
        parts.append("_TBD_")
    return "\n".join(parts)


def _work_tasks(ctx: HandoverContext) -> str:
    if not ctx.tasks:
        return "- [ ] _No tasks extracted — add them manually._"
    lines: list[str] = []
    for t in ctx.tasks:
        check = "x" if t.done else " "
        suffix = " *(high priority)*" if t.priority == "high" else ""
        lines.append(f"- [{check}] {t.title}{suffix}")
        if t.description:
            lines.append(f"  - {t.description}")
    return "\n".join(lines)


def _work_milestones(ctx: HandoverContext) -> str:
    return (
        "_No milestones detected automatically. Group tasks into phases here, "
        "for example:_\n\n"
        "## Phase 1 — Foundation\n\n- (tasks)\n\n"
        "## Phase 2 — Features\n\n- (tasks)"
    )


def _standards_coding(ctx: HandoverContext) -> str:
    stack = _stack_summary(ctx)
    intro = f"Apply standard {stack} conventions." if stack else "Apply standard conventions."
    return (
        f"{intro}\n\n"
        "- Use type hints / type annotations where the language supports them.\n"
        "- Keep functions small and focused. Prefer composition over inheritance.\n"
        "- Document public interfaces with docstrings or equivalent.\n"
        "- Run the project's linter and formatter before committing.\n"
        "- Avoid speculative abstractions — only add complexity the task needs."
    )


def _standards_testing(ctx: HandoverContext) -> str:
    return (
        "- Write tests for every new behavior. Reproduce bugs with a failing "
        "test before fixing them.\n"
        "- Cover the happy path **and** the most likely error paths.\n"
        "- Mock at the system boundary (network, filesystem, time, randomness) "
        "— never mock internal modules.\n"
        "- Tests must be deterministic. No real network calls. No reliance on "
        "wall-clock time.\n"
        "- Coverage should not regress."
    )


def _standards_security(ctx: HandoverContext) -> str:
    return (
        "- Validate all input crossing a trust boundary (HTTP, CLI, file).\n"
        "- Never log secrets, tokens, or PII.\n"
        "- Use parameterized queries for any data store.\n"
        "- Pin dependencies and review them before upgrading.\n"
        "- Follow the OWASP Top 10 for web-facing surfaces."
    )


def _standards_release(ctx: HandoverContext) -> str:
    return (
        "- All tests pass on CI.\n"
        "- Linter and type checker are clean.\n"
        "- CHANGELOG entry added under the upcoming version.\n"
        "- Version bumped following semantic versioning.\n"
        "- Tag the release and push the tag to trigger the publish workflow."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stack_summary(ctx: HandoverContext) -> str:
    """Return a short ', '-separated summary of the tech stack values."""
    return ", ".join(str(v) for v in ctx.tech_stack.values() if v)
