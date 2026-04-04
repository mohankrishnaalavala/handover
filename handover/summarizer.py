"""
handover/summarizer.py

Summarizer component: converts normalized ConversationMessage list to HandoverContext.
See PRD Section 6 — Architecture (Summarizer component).

Two modes:
  - Default: calls Claude API (claude-sonnet-4-6) with a structured extraction prompt
  - --no-llm: delegates to heuristics.py for rule-based extraction (no API key required)
"""

from __future__ import annotations

from handover.models import ConversationMessage, HandoverContext

# TODO: implement — see PRD Section 6


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
        anthropic.AuthenticationError: If ANTHROPIC_API_KEY is not set (LLM mode).
        anthropic.APIError: On API failures (LLM mode).
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
    """
    # TODO: implement
    # 1. Import anthropic and create client
    # 2. Build conversation_text from messages
    # 3. Call claude-sonnet-4-6 with structured extraction prompt
    # 4. Parse JSON response into HandoverContext
    # 5. Handle API errors gracefully
    raise NotImplementedError("LLM summarization not yet implemented")
