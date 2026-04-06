"""
handover/merger.py

Multi-context merge: combine multiple HandoverContext objects from separate
chat sessions into one unified HandoverContext.

Merge strategy:
  - goal / tech_stack: last non-empty value wins
  - decisions: concatenate, deduplicate by (topic, decision) pair
  - tasks: concatenate, deduplicate by title (case-insensitive)
  - constraints / non_goals / open_questions: union, deduplicate

Two modes:
  - use_llm=True: sends a merge prompt to Claude for intelligent synthesis
  - use_llm=False: applies the heuristic rules above

Phase 6 — Ecosystem & Developer Experience.
"""

from __future__ import annotations

import datetime
import json

from handover.models import Decision, HandoverContext, Task

# Merge prompt — sent to Claude with all serialized contexts
MERGE_PROMPT = """\
You are merging {n} AI chat summaries into one coherent project context.

Rules:
- goal: write a single unified goal covering all sessions
- tech_stack: merge all; later sessions override earlier for the same key
- decisions: combine all; if the same topic appears multiple times, keep \
the most recent decision
- tasks: combine all, deduplicate by title; mark done=true if ANY session \
marks it done
- constraints, non_goals, open_questions: union and deduplicate

Return ONLY valid JSON matching this schema — no markdown fences, no explanation:
{{
  "goal": "...",
  "tech_stack": {{}},
  "decisions": [{{"topic": "...", "decision": "...", "rationale": "..."}}],
  "tasks": [{{"title": "...", "description": "...", "priority": "high|medium|low", \
"done": false}}],
  "constraints": ["..."],
  "non_goals": ["..."],
  "open_questions": ["..."]
}}

Summaries:
{summaries}"""


def merge_contexts(
    contexts: list[HandoverContext],
    use_llm: bool = True,
) -> HandoverContext:
    """
    Merge multiple HandoverContext objects into one.

    Args:
        contexts: Two or more HandoverContext objects from separate chat sessions.
        use_llm: If True, use Claude for intelligent synthesis. If False, use
                 heuristic deduplication.

    Returns:
        A single merged HandoverContext.

    Raises:
        ValueError: If contexts is empty.
        HandoverAPIError: If LLM mode and the API call fails.
    """
    if not contexts:
        raise ValueError("merge_contexts requires at least one HandoverContext.")
    if len(contexts) == 1:
        return contexts[0]

    if not use_llm:
        return _merge_heuristic(contexts)
    return _merge_with_llm(contexts)


def _merge_heuristic(contexts: list[HandoverContext]) -> HandoverContext:
    """Apply deterministic merge rules without calling the API."""
    # Scalar fields: last non-empty wins
    goal = ""
    tech_stack: dict[str, str] = {}
    for ctx in contexts:
        if ctx.goal:
            goal = ctx.goal
        if ctx.tech_stack:
            tech_stack.update(ctx.tech_stack)

    # Decisions: deduplicate by (topic.lower(), decision.lower())
    seen_decisions: set[tuple[str, str]] = set()
    decisions: list[Decision] = []
    for ctx in contexts:
        for d in ctx.decisions:
            key = (d.topic.lower().strip(), d.decision.lower().strip())
            if key not in seen_decisions:
                seen_decisions.add(key)
                decisions.append(d)

    # Tasks: deduplicate by title.lower(); done=True if any session marks it done
    seen_tasks: dict[str, Task] = {}
    for ctx in contexts:
        for t in ctx.tasks:
            task_key = t.title.lower().strip()
            if task_key in seen_tasks:
                if t.done:
                    seen_tasks[task_key] = t  # promote to done
            else:
                seen_tasks[task_key] = t
    tasks = list(seen_tasks.values())

    # Lists: ordered union, deduplicate by lowercased value
    def _dedup(items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = item.lower().strip()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    constraints = _dedup([c for ctx in contexts for c in ctx.constraints])
    non_goals = _dedup([g for ctx in contexts for g in ctx.non_goals])
    open_questions = _dedup([q for ctx in contexts for q in ctx.open_questions])

    return HandoverContext(
        schema_version="1.0",
        source="merged",
        extracted_at=datetime.datetime.utcnow().isoformat() + "Z",
        goal=goal,
        tech_stack=tech_stack,
        decisions=decisions,
        tasks=tasks,
        constraints=constraints,
        non_goals=non_goals,
        open_questions=open_questions,
    )


def _merge_with_llm(contexts: list[HandoverContext]) -> HandoverContext:
    """Send all contexts to Claude and ask it to produce a merged context."""
    from handover.summarizer import merge_contexts_with_llm

    return merge_contexts_with_llm(contexts)


def _context_to_summary(ctx: HandoverContext) -> str:
    """Serialize a HandoverContext to a compact JSON string for the merge prompt."""
    data = {
        "goal": ctx.goal,
        "tech_stack": ctx.tech_stack,
        "decisions": [
            {"topic": d.topic, "decision": d.decision, "rationale": d.rationale}
            for d in ctx.decisions
        ],
        "tasks": [{"title": t.title, "priority": t.priority, "done": t.done} for t in ctx.tasks],
        "constraints": ctx.constraints,
        "non_goals": ctx.non_goals,
        "open_questions": ctx.open_questions,
    }
    return json.dumps(data, ensure_ascii=False)
