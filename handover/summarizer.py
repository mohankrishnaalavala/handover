"""
handover/summarizer.py

Summarizer component: converts normalized ConversationMessage list to HandoverContext.
See PRD Section 6 — Architecture (Summarizer component).

Two modes:
  - Default: calls Claude API (claude-sonnet-4-6) with a structured extraction prompt
  - --no-llm: delegates to heuristics.py for rule-based extraction (no API key required)
"""

from __future__ import annotations

import datetime
import json

import anthropic

from handover.models import (
    ConversationMessage,
    Decision,
    HandoverAPIError,
    HandoverContext,
    Task,
)

_MODEL = "claude-sonnet-4-6"

# Extraction prompt — module-level so tests can inspect and assert against it
EXTRACTION_PROMPT = """\
Extract structured information from this AI chat conversation.
Return ONLY valid JSON matching this schema — no markdown fences, no explanation:
{{
  "goal": "<single sentence describing the project goal>",
  "tech_stack": {{"language": "...", "framework": "...", "database": "..."}},
  "decisions": [{{"topic": "...", "decision": "...", "rationale": "..."}}],
  "tasks": [{{"title": "...", "description": "...", "priority": "high|medium|low", "done": false}}],
  "constraints": ["..."],
  "non_goals": ["..."],
  "open_questions": ["..."]
}}

Conflict resolution: when the same topic is discussed multiple times, \
the LATEST decision wins.
Only include non-empty fields. Use empty lists [] for missing sections.

Field-specific rules:
- goal: write a clean, concise one-sentence project goal in plain English. Do NOT copy \
the user's raw question verbatim — rephrase it as a goal statement starting with a verb \
(e.g. "Build a webapp that...").
- open_questions: only include genuine unresolved design or architecture questions that \
the team still needs to decide. Skip the assistant's closing rhetorical offers \
(e.g. "Want me to generate X?", "Should I create the files now?", \
"Would you like me to...?") — these are not open questions.

Conversation:
{conversation}"""


def merge_contexts_with_llm(
    contexts: list[HandoverContext],
) -> HandoverContext:
    """
    Use Claude to intelligently merge multiple HandoverContext objects.

    Sends all contexts as serialized JSON summaries and asks the model to
    produce a single unified context following the merge rules in the prompt.

    Args:
        contexts: Two or more HandoverContext objects to merge.

    Returns:
        A single merged HandoverContext.

    Raises:
        HandoverAPIError: If the API call fails.
    """
    from handover.merger import MERGE_PROMPT, _context_to_summary

    summaries_text = "\n\n".join(
        f"Session {i + 1}:\n{_context_to_summary(ctx)}" for i, ctx in enumerate(contexts)
    )
    prompt = MERGE_PROMPT.format(n=len(contexts), summaries=summaries_text)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as e:
        raise HandoverAPIError(
            "ANTHROPIC_API_KEY is not set or invalid. Use --no-llm for the merge."
        ) from e
    except anthropic.APIError as e:
        raise HandoverAPIError(f"Anthropic API error during merge: {e}.") from e

    raw_text = getattr(response.content[0], "text", None)
    if not isinstance(raw_text, str):
        raise HandoverAPIError("Unexpected response block type from API during merge.")

    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise HandoverAPIError(f"Model returned invalid JSON during merge: {e}.") from e

    return HandoverContext(
        schema_version="1.0",
        source="merged",
        extracted_at=datetime.datetime.utcnow().isoformat() + "Z",
        goal=raw.get("goal", ""),
        tech_stack=raw.get("tech_stack", {}),
        decisions=[
            Decision(
                topic=d.get("topic", ""),
                decision=d.get("decision", ""),
                rationale=d.get("rationale", ""),
            )
            for d in raw.get("decisions", [])
        ],
        tasks=[
            Task(
                title=t.get("title", ""),
                description=t.get("description", ""),
                priority=t.get("priority", "medium"),
                done=t.get("done", False),
            )
            for t in raw.get("tasks", [])
        ],
        constraints=raw.get("constraints", []),
        non_goals=raw.get("non_goals", []),
        open_questions=raw.get("open_questions", []),
    )


def summarize(
    messages: list[ConversationMessage],
    use_llm: bool = True,
) -> HandoverContext:
    """
    Extract HandoverContext from a list of ConversationMessage objects.

    Args:
        messages: Normalized conversation messages from a parser adapter.
        use_llm: If True, use the Anthropic API. If False, use heuristics.

    Returns:
        Populated HandoverContext ready for the Generator.

    Raises:
        HandoverAPIError: If the Anthropic API call fails (LLM mode only).
    """
    if not use_llm:
        from handover import heuristics

        return heuristics.extract(messages)

    return _summarize_with_llm(messages)


def _summarize_with_llm(messages: list[ConversationMessage]) -> HandoverContext:
    """
    Call Claude API with a structured extraction prompt.

    The prompt instructs the model to return valid JSON matching the
    HandoverContext schema. Conflict resolution (latest decision wins)
    is handled by instruction in the prompt.

    See .claude/skills/anthropic-api.md for API usage patterns.

    Raises:
        HandoverAPIError: On authentication failure or API error.
    """
    conversation_text = "\n".join(f"{m.role.upper()}: {m.content}" for m in messages)
    # Truncate very long conversations to stay within context limits while preserving
    # the most recent messages (which contain the final decisions and tasks).
    _MAX_CONV_CHARS = 60_000
    if len(conversation_text) > _MAX_CONV_CHARS:
        conversation_text = conversation_text[-_MAX_CONV_CHARS:]
    prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)

    try:
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
        response = client.messages.create(
            model=_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as e:
        raise HandoverAPIError(
            "ANTHROPIC_API_KEY is not set or invalid. "
            "Use --no-llm for rule-based extraction, or set the key in your .env file."
        ) from e
    except anthropic.APIError as e:
        raise HandoverAPIError(f"Anthropic API error: {e}. Use --no-llm as fallback.") from e

    raw_text = getattr(response.content[0], "text", None)
    if not isinstance(raw_text, str):
        raise HandoverAPIError("Unexpected response block type from API.")

    # Strip markdown code fences if the model wrapped the JSON in ```json ... ```
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise HandoverAPIError(
            f"Model returned invalid JSON: {e}. Raw response: {raw_text[:200]}"
        ) from e

    return HandoverContext(
        schema_version="1.0",
        source="claude",
        extracted_at=datetime.datetime.utcnow().isoformat() + "Z",
        goal=raw.get("goal", ""),
        tech_stack=raw.get("tech_stack", {}),
        decisions=[
            Decision(
                topic=d.get("topic", ""),
                decision=d.get("decision", ""),
                rationale=d.get("rationale", ""),
            )
            for d in raw.get("decisions", [])
        ],
        tasks=[
            Task(
                title=t.get("title", ""),
                description=t.get("description", ""),
                priority=t.get("priority", "medium"),
                done=t.get("done", False),
            )
            for t in raw.get("tasks", [])
        ],
        constraints=raw.get("constraints", []),
        non_goals=raw.get("non_goals", []),
        open_questions=raw.get("open_questions", []),
    )
