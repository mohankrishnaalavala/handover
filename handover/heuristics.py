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
  open_questions — sentences ending in "?", lines starting with "TBD" or "open question:"
"""

from __future__ import annotations

import datetime
import re

from handover.models import ConversationMessage, Decision, HandoverContext, Task

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

# Tech stack keyword list (lowercase lookup → canonical display name)
TECH_KEYWORDS: dict[str, list[str]] = {
    "language": ["python", "typescript", "javascript", "go", "rust", "java", "ruby", "kotlin"],
    "framework": [
        "fastapi", "flask", "django", "express", "nextjs", "react", "vue", "angular", "rails"
    ],
    "database": [
        "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis", "dynamodb", "supabase"
    ],
    "testing": ["pytest", "jest", "unittest", "vitest", "mocha", "cypress"],
    "infra": ["docker", "kubernetes", "aws", "gcp", "azure", "vercel", "railway", "fly.io"],
}

# Canonical display names for tech keywords (lowercase → display)
_TECH_CANONICAL: dict[str, str] = {
    "python": "Python",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "go": "Go",
    "rust": "Rust",
    "java": "Java",
    "ruby": "Ruby",
    "kotlin": "Kotlin",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "express": "Express",
    "nextjs": "Next.js",
    "react": "React",
    "vue": "Vue",
    "angular": "Angular",
    "rails": "Rails",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "dynamodb": "DynamoDB",
    "supabase": "Supabase",
    "pytest": "pytest",
    "jest": "Jest",
    "unittest": "unittest",
    "vitest": "Vitest",
    "mocha": "Mocha",
    "cypress": "Cypress",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "vercel": "Vercel",
    "railway": "Railway",
    "fly.io": "Fly.io",
}

# Compiled regex for "must" with a subject — avoids matching casual "must"
# Matches: "it must", "the system must", "we must", "you must", "this must"
_MUST_WITH_SUBJECT_RE = re.compile(
    r"\b(it|the\s+\w+|we|you|this|system|api|service|app)\s+must\b",
    re.IGNORECASE,
)

# List item patterns: "1. item", "- item", "* item"
_LIST_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]\s+|[-*]\s+)(.+)$", re.MULTILINE)

# Open question patterns
_QUESTION_RE = re.compile(r"[^.!?]*\?")
_TBD_RE = re.compile(r"^(?:TBD|tbd|open question:|unclear:)\s*(.+)$", re.MULTILINE)


def _sentences(text: str) -> list[str]:
    """Split text into sentences on . ! ? boundaries."""
    return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]


def extract(messages: list[ConversationMessage]) -> HandoverContext:
    """
    Extract HandoverContext from messages using rule-based heuristics.

    Args:
        messages: Normalized conversation messages.

    Returns:
        Populated HandoverContext (may be incomplete compared to LLM mode).
    """
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
        open_questions=extract_open_questions(messages),
    )


def extract_goal(messages: list[ConversationMessage]) -> str:
    """
    Extract the project goal from conversation messages.

    Rule: First sentence containing an intent keyword in a user message.
    Fallback: first user message content (trimmed to 300 chars).
    See PRD Section 8, field: goal.
    """
    user_messages = [m for m in messages if m.role == "user"]
    if not user_messages:
        return ""

    for msg in user_messages:
        lower = msg.content.lower()
        for kw in INTENT_KEYWORDS:
            if kw in lower:
                # Return the sentence containing the keyword
                for sentence in _sentences(msg.content):
                    if kw in sentence.lower():
                        return sentence[:300]

    # Fallback: first user message
    return user_messages[0].content[:300]


def extract_decisions(messages: list[ConversationMessage]) -> list[Decision]:
    """
    Extract decisions from conversation messages.

    Rule: Sentences containing decision keywords. Last occurrence wins per tech topic.
    Deduplication key: lowercase tech keyword found in the sentence (or full sentence).
    See PRD Section 8, field: decisions.
    """
    # last-occurrence-wins: keyed by tech topic or decision sentence fragment
    seen: dict[str, Decision] = {}

    for msg in messages:
        lower = msg.content.lower()
        for kw in DECISION_KEYWORDS:
            if kw not in lower:
                continue
            for sentence in _sentences(msg.content):
                if kw not in sentence.lower():
                    continue
                # Try to find a tech keyword in the sentence for dedup key
                dedup_key = sentence.lower()
                for category_keywords in TECH_KEYWORDS.values():
                    for tech in category_keywords:
                        if tech in sentence.lower():
                            dedup_key = tech
                            break

                seen[dedup_key] = Decision(topic="", decision=sentence.strip(), rationale="")

    return list(seen.values())


def extract_constraints(messages: list[ConversationMessage]) -> list[str]:
    """
    Extract constraints from conversation messages.

    Rule: Sentences with constraint keywords. "must" is filtered to require a subject.
    See PRD Section 8, field: constraints.
    """
    found: list[str] = []
    seen_lower: set[str] = set()

    for msg in messages:
        lower = msg.content.lower()
        for kw in CONSTRAINT_KEYWORDS:
            if kw not in lower:
                continue
            for sentence in _sentences(msg.content):
                s_lower = sentence.lower()
                if kw not in s_lower:
                    continue
                # Filter noisy "must": require a subject before "must"
                if kw == "must" and not _MUST_WITH_SUBJECT_RE.search(sentence):
                    continue
                dedup = re.sub(r"[^a-z0-9 ]", "", s_lower).strip()
                if dedup and dedup not in seen_lower:
                    seen_lower.add(dedup)
                    found.append(sentence.strip())

    return found


def extract_non_goals(messages: list[ConversationMessage]) -> list[str]:
    """
    Extract non-goals from conversation messages.

    Rule: Sentences containing out-of-scope keywords.
    See PRD Section 8, field: non_goals.
    """
    found: list[str] = []
    seen_lower: set[str] = set()

    for msg in messages:
        lower = msg.content.lower()
        for kw in NON_GOAL_KEYWORDS:
            if kw not in lower:
                continue
            for sentence in _sentences(msg.content):
                if kw not in sentence.lower():
                    continue
                dedup = re.sub(r"[^a-z0-9 ]", "", sentence.lower()).strip()
                if dedup and dedup not in seen_lower:
                    seen_lower.add(dedup)
                    found.append(sentence.strip())

    return found


def extract_tasks(messages: list[ConversationMessage]) -> list[Task]:
    """
    Extract tasks from conversation messages.

    Rule: Numbered lists or bullet points in any message;
    content following "Next steps:", "TODO:", etc.
    Deduplication by lowercase title.
    See PRD Section 8, field: tasks.
    """
    seen_titles: set[str] = set()
    tasks: list[Task] = []

    for msg in messages:
        content = msg.content
        lower = content.lower()

        # Check if any task-pattern header is present
        has_task_section = any(p in lower for p in TASK_PATTERNS)

        # If a task section header is present, only extract the portion after it
        if has_task_section:
            for pattern in TASK_PATTERNS:
                idx = lower.find(pattern)
                if idx != -1:
                    content = content[idx + len(pattern):]
                    break

        # Extract all list items from (possibly trimmed) content
        for match in _LIST_ITEM_RE.finditer(content):
            title = match.group(1).strip()
            if not title:
                continue
            dedup = title.lower()
            if dedup in seen_titles:
                continue
            seen_titles.add(dedup)
            priority = "high" if ("!" in title or "high priority" in title.lower()) else "medium"
            tasks.append(Task(title=title, priority=priority))

    return tasks


def extract_tech_stack(messages: list[ConversationMessage]) -> dict[str, str]:
    """
    Extract tech stack from conversation messages.

    Rule: Match known tech keywords from TECH_KEYWORDS across all messages.
    Returns canonical display names (e.g. "FastAPI" not "fastapi").
    Last keyword found per category wins if multiple match.
    See PRD Section 8, field: tech_stack.
    """
    full_text = " ".join(m.content for m in messages).lower()
    result: dict[str, str] = {}

    for category, keywords in TECH_KEYWORDS.items():
        for tech in keywords:
            if tech in full_text:
                canonical = _TECH_CANONICAL.get(tech, tech)
                result[category] = canonical  # last match per category wins

    return result


def extract_open_questions(messages: list[ConversationMessage]) -> list[str]:
    """
    Extract open questions from conversation messages.

    Rule: Sentences ending in "?" (min 20 chars) and lines starting with
    "TBD", "open question:", or "unclear:".
    See PRD Section 8, field: open_questions.
    """
    found: list[str] = []
    seen_lower: set[str] = set()

    for msg in messages:
        # Sentences ending in "?"
        for match in _QUESTION_RE.finditer(msg.content):
            q = match.group(0).strip()
            if len(q) < 20:
                continue
            dedup = re.sub(r"[^a-z0-9 ]", "", q.lower()).strip()
            if dedup and dedup not in seen_lower:
                seen_lower.add(dedup)
                found.append(q)

        # TBD / open question: / unclear: prefixes
        for match in _TBD_RE.finditer(msg.content):
            q = match.group(0).strip()
            dedup = re.sub(r"[^a-z0-9 ]", "", q.lower()).strip()
            if dedup and dedup not in seen_lower:
                seen_lower.add(dedup)
                found.append(q)

    return found
