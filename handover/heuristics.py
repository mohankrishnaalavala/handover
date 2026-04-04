"""
handover/heuristics.py

Rule-based extraction for --no-llm mode. No API key required.
See PRD Section 8 — --no-llm Rule-Based Extraction Heuristics.

Each extraction rule is a standalone function for easy testing and contribution.
Conflict resolution: when the same topic appears multiple times, last occurrence wins.

Heuristic rules (from PRD Section 8):
  goal        — first user message, or message with intent keywords
  decisions   — messages with "let's use", "we'll go with", "decided to", etc.
  constraints — messages with "must", "cannot", "should not", "requirement:", "constraint:"
  non_goals   — messages with "not in scope", "out of scope", "won't", "we don't need", "skip"
  tasks       — numbered lists, bullet points, "Next steps:", "TODO:"
  tech_stack  — known tech keywords matched via bundled keyword list
"""

from __future__ import annotations

from handover.models import ConversationMessage, HandoverContext, Decision, Task

# TODO: implement — see PRD Section 8

# Intent keywords for goal extraction
INTENT_KEYWORDS = [
    "i want to build",
    "build a",
    "create a",
    "we need to",
    "let's build",
    "i'm building",
]

# Decision keywords
DECISION_KEYWORDS = [
    "let's use",
    "we'll go with",
    "decided to",
    "we should use",
    "i think we should",
    "going with",
    "we're using",
]

# Constraint keywords
CONSTRAINT_KEYWORDS = [
    "must",
    "cannot",
    "should not",
    "requirement:",
    "constraint:",
    "needs to",
    "has to",
    "required to",
]

# Non-goal keywords
NON_GOAL_KEYWORDS = [
    "not in scope",
    "out of scope",
    "won't",
    "we don't need",
    "skip",
    "not needed",
    "not for v1",
    "not for phase 1",
]

# Task/next-step patterns
TASK_PATTERNS = [
    "next steps:",
    "todo:",
    "tasks:",
    "action items:",
    "to do:",
]

# Tech stack keyword list (language/framework/db names)
TECH_KEYWORDS = {
    "language": ["python", "typescript", "javascript", "go", "rust", "java", "ruby", "kotlin"],
    "framework": ["fastapi", "flask", "django", "express", "nextjs", "react", "vue", "angular", "rails"],
    "database": ["postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis", "dynamodb", "supabase"],
    "testing": ["pytest", "jest", "unittest", "vitest", "mocha", "cypress"],
    "infra": ["docker", "kubernetes", "aws", "gcp", "azure", "vercel", "railway", "fly.io"],
}


def extract(messages: list[ConversationMessage]) -> HandoverContext:
    """
    Extract HandoverContext from messages using rule-based heuristics.

    Args:
        messages: Normalized conversation messages.

    Returns:
        Populated HandoverContext (may be incomplete compared to LLM mode).
    """
    # TODO: implement — orchestrate all extraction rules
    import datetime
    return HandoverContext(
        schema_version="1.0",
        source="unknown",
        source_version="unknown",
        extracted_at=datetime.datetime.utcnow().isoformat() + "Z",
        goal=extract_goal(messages),
        tech_stack=extract_tech_stack(messages),
        decisions=extract_decisions(messages),
        tasks=extract_tasks(messages),
        constraints=extract_constraints(messages),
        non_goals=extract_non_goals(messages),
        open_questions=[],
    )


def extract_goal(messages: list[ConversationMessage]) -> str:
    """
    Extract the project goal from conversation messages.

    Rule: First user message, or first message containing an intent keyword.
    See PRD Section 8, field: goal.
    """
    # TODO: implement
    raise NotImplementedError


def extract_decisions(messages: list[ConversationMessage]) -> list[Decision]:
    """
    Extract decisions from conversation messages.

    Rule: Messages containing decision keywords. Last occurrence wins for same topic.
    See PRD Section 8, field: decisions.
    """
    # TODO: implement
    raise NotImplementedError


def extract_constraints(messages: list[ConversationMessage]) -> list[str]:
    """
    Extract constraints from conversation messages.

    Rule: Messages containing constraint keywords.
    See PRD Section 8, field: constraints.
    """
    # TODO: implement
    raise NotImplementedError


def extract_non_goals(messages: list[ConversationMessage]) -> list[str]:
    """
    Extract non-goals from conversation messages.

    Rule: Messages containing out-of-scope keywords.
    See PRD Section 8, field: non_goals.
    """
    # TODO: implement
    raise NotImplementedError


def extract_tasks(messages: list[ConversationMessage]) -> list[Task]:
    """
    Extract tasks from conversation messages.

    Rule: Numbered lists or bullet points in assistant messages;
    messages starting with "Next steps:" or "TODO:".
    See PRD Section 8, field: tasks.
    """
    # TODO: implement
    raise NotImplementedError


def extract_tech_stack(messages: list[ConversationMessage]) -> dict:
    """
    Extract tech stack from conversation messages.

    Rule: Match known tech keywords from the bundled TECH_KEYWORDS list.
    See PRD Section 8, field: tech_stack.
    """
    # TODO: implement
    raise NotImplementedError
