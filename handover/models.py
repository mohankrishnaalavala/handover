"""
handover/models.py

Data models for the handover pipeline.
See PRD Section 7 — Data Model.

ConversationMessage: normalized chat message from any source adapter.
HandoverContext: extracted context passed to the generator.
Decision, Task: sub-models within HandoverContext.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class HandoverAPIError(Exception):
    """Raised when the Anthropic API call fails during summarization."""


@dataclass
class ConversationMessage:
    """A single normalized message from a chat conversation."""

    role: str           # "user" | "assistant"
    content: str
    timestamp: str | None = None
    message_id: str | None = None

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant"):
            raise ValueError(
                f"role must be 'user' or 'assistant', got {self.role!r}"
            )
        if not self.content:
            raise ValueError("content must not be empty")


@dataclass
class Decision:
    """A decision extracted from the conversation."""

    topic: str
    decision: str
    rationale: str = ""


@dataclass
class Task:
    """A task extracted from the conversation."""

    title: str
    description: str = ""
    priority: str = "medium"    # "high" | "medium" | "low"
    done: bool = False

    def __post_init__(self) -> None:
        if self.priority not in ("high", "medium", "low"):
            raise ValueError(
                f"priority must be 'high', 'medium', or 'low', got {self.priority!r}"
            )


@dataclass
class HandoverContext:
    """
    Fully extracted context from a chat conversation.
    Passed to the Generator to produce CLAUDE.md and PLAN.md.

    schema_version must be bumped when fields change in a breaking way.
    source_version reflects the detected export format variant.
    """

    schema_version: str = "1.0"
    source: str = ""                    # "claude" | "chatgpt" | ...
    source_version: str = ""            # export format version detected
    conversation_title: str = ""
    conversation_id: str | None = None
    extracted_at: str = ""              # ISO timestamp

    goal: str = ""
    tech_stack: dict = field(default_factory=dict)  # type: ignore[type-arg]
    decisions: list[Decision] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
