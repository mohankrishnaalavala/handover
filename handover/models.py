"""
handover/models.py

Data models for the handover pipeline.
See PRD Section 7 — Data Model.

ConversationMessage: normalized chat message from any source adapter.
HandoverContext: extracted context passed to the generator.
Decision, Task: sub-models within HandoverContext.

Phase 4 additions:
FileChange, SessionMeta, SessionContext: models for the reverse-handover pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class HandoverAPIError(Exception):
    """Raised when the Anthropic API call fails during summarization."""


@dataclass
class ConversationMessage:
    """A single normalized message from a chat conversation."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: str | None = None
    message_id: str | None = None

    def __post_init__(self) -> None:
        if self.role not in ("user", "assistant"):
            raise ValueError(f"role must be 'user' or 'assistant', got {self.role!r}")
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
    priority: str = "medium"  # "high" | "medium" | "low"
    done: bool = False

    def __post_init__(self) -> None:
        if self.priority not in ("high", "medium", "low"):
            raise ValueError(f"priority must be 'high', 'medium', or 'low', got {self.priority!r}")


@dataclass
class HandoverContext:
    """
    Fully extracted context from a chat conversation.
    Passed to the Generator to produce CLAUDE.md and PLAN.md.

    schema_version must be bumped when fields change in a breaking way.
    source_version reflects the detected export format variant.
    """

    schema_version: str = "1.0"
    source: str = ""  # "claude" | "chatgpt" | ...
    source_version: str = ""  # export format version detected
    conversation_title: str = ""
    conversation_id: str | None = None
    extracted_at: str = ""  # ISO timestamp

    goal: str = ""
    tech_stack: dict = field(default_factory=dict)  # type: ignore[type-arg]
    decisions: list[Decision] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Phase 6 — History log
# ---------------------------------------------------------------------------


@dataclass
class HistoryEntry:
    """A record of a successful handover run, written to ~/.handover/history.jsonl."""

    handover_id: str  # "h_" + 8-char hex from uuid4
    timestamp: str  # ISO 8601
    source: str  # "claude" | "chatgpt" | ...
    conversation_title: str
    input_file: str  # absolute path
    output_dir: str  # absolute path
    artifacts: list[str]  # filenames written, e.g. ["CLAUDE.md", "PLAN.md"]
    target: str = "claude-code"
    use_llm: bool = True


# ---------------------------------------------------------------------------
# Phase 4 — Reverse handover (Claude Code session → HANDOVER.md)
# ---------------------------------------------------------------------------


@dataclass
class FileChange:
    """A file that was created or modified during a Claude Code session."""

    path: str
    action: str  # "created" | "modified" | "deleted"


@dataclass
class SessionMeta:
    """Lightweight metadata for a discovered Claude Code session file."""

    session_id: str
    project_path: str  # cwd recorded in the session
    file_path: Path  # absolute path to the .jsonl file
    started_at: str  # ISO timestamp of first user message
    git_branch: str
    message_count: int
    size_bytes: int


@dataclass
class SessionContext:
    """
    Extracted context from a Claude Code session log.
    Passed to the Generator to produce HANDOVER.md.
    """

    session_id: str = ""
    project_name: str = ""
    generated_at: str = ""
    started_at: str = ""
    git_branch: str = ""
    files_changed: list[FileChange] = field(default_factory=list)
    commands_run: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    tasks_completed: list[Task] = field(default_factory=list)
    tasks_remaining: list[Task] = field(default_factory=list)
    last_action: str = ""
    context_usage_pct: int | None = None
    next_steps: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# v1.1.0 — Two-Layer Scaffold (.handover/ + .claude/)
#
# These dataclasses carry the data needed to render the vendor-neutral
# `.handover/` knowledge base and the per-target agent workspace (`.claude/`
# for the claude-code target). The pipeline becomes:
#
#   parse → summarize → scaffold_extractor → universal_generator(.handover/)
#         → target_generator(thin agent files)
#
# Loose-coupling rule: ScaffoldContext holds plain data only — no methods
# that reach into Jinja2 or filesystem. Generators consume it; extractors
# produce it.
# ---------------------------------------------------------------------------


@dataclass
class HandoverManifest:
    """Top-level metadata for a generated `.handover/` directory."""

    version: str = ""  # handover tool version that generated this scaffold
    generated_at: str = ""  # ISO 8601 timestamp
    source: str = ""  # "claude" | "chatgpt" | ...
    target: str = ""  # CLI --target value (or "all")
    project: str = ""  # project / conversation title
    schema_version: str = "1.0"


@dataclass
class BacklogTask:
    """A single task entry inside `.handover/work/backlog.json`."""

    id: str  # e.g. "task-001"
    title: str
    description: str = ""
    phase: str = "1"
    priority: str = "medium"  # "high" | "medium" | "low"
    done: bool = False
    tags: list[str] = field(default_factory=list)
    added_at: str = ""  # ISO 8601 timestamp
    done_at: str | None = None


@dataclass
class Milestone:
    """A grouping of backlog tasks under a named phase / milestone."""

    id: str
    title: str
    task_ids: list[str] = field(default_factory=list)


@dataclass
class Backlog:
    """Machine-readable task store written as `.handover/work/backlog.json`."""

    schema_version: str = "1.0"
    updated_at: str = ""  # ISO 8601 timestamp
    project: str = ""
    tasks: list[BacklogTask] = field(default_factory=list)
    milestones: list[Milestone] = field(default_factory=list)


@dataclass
class AgentSpec:
    """Specification for a `.claude/agents/<name>.md` agent file."""

    name: str  # e.g. "backend-agent"
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    system_prompt: str = ""


@dataclass
class SkillSpec:
    """Specification for a `.claude/skills/<name>.md` skill file."""

    name: str
    description: str = ""
    body: str = ""


@dataclass
class CommandSpec:
    """Specification for a `.claude/commands/<name>.md` slash command."""

    name: str
    description: str = ""
    body: str = ""


@dataclass
class HookSpec:
    """Specification for a `.claude/hooks/<name>` hook script."""

    name: str  # filename, e.g. "pre-tool-use.sh"
    event: str = ""  # e.g. "pre-tool-use"
    script: str = ""  # full script body (will be written and chmod +x'd)


@dataclass
class ScaffoldContext:
    """
    Carrier for everything needed to render `.handover/` and `.claude/`.

    The 13 markdown body fields hold rendered prose (LLM-extracted or
    heuristic). Templates wrap them with H1s / front matter and write to
    the appropriate paths in `.handover/`. The `agents`/`skills`/etc. lists
    drive the per-target `.claude/` workspace generator.

    schema_version is bumped on breaking field changes.
    """

    schema_version: str = "1.0"
    manifest: HandoverManifest = field(default_factory=HandoverManifest)
    backlog: Backlog = field(default_factory=Backlog)

    # 13 markdown bodies — produced by scaffold_extractor (LLM) or
    # scaffold_heuristics (no-LLM). Each is plain markdown without an H1.
    overview: str = ""
    architecture: str = ""
    decisions: str = ""
    constraints: str = ""
    risks: str = ""
    acceptance_criteria: str = ""
    work_spec: str = ""
    work_tasks: str = ""
    work_milestones: str = ""
    standards_coding: str = ""
    standards_testing: str = ""
    standards_security: str = ""
    standards_release: str = ""

    # Domain-detected agent workspace contents
    agents: list[AgentSpec] = field(default_factory=list)
    skills: list[SkillSpec] = field(default_factory=list)
    commands: list[CommandSpec] = field(default_factory=list)
    hooks: list[HookSpec] = field(default_factory=list)


# ---------------------------------------------------------------------------
# v1.1.2 — Codebase Index
# ---------------------------------------------------------------------------


@dataclass
class FileIndex:
    """Metadata about a single source file in the indexed project."""

    path: str
    purpose: str  # first line of module docstring, or ""
    exports: list[str] = field(default_factory=list)
    imports_internal: list[str] = field(default_factory=list)
    imports_external: list[str] = field(default_factory=list)
    line_count: int = 0
    has_tests: bool = False
    test_file: str | None = None


@dataclass
class Symbol:
    """A public function, class, or constant extracted from a source file."""

    name: str
    type: str  # "function" | "class" | "method" | "constant"
    file: str
    line: int = 0
    signature: str = ""
    docstring: str = ""


@dataclass
class DependencyNode:
    """Import-graph node for a single file."""

    depends_on: list[str] = field(default_factory=list)
    depended_on_by: list[str] = field(default_factory=list)


@dataclass
class ChangeImpact:
    """Risk assessment for a single file based on its dependency graph."""

    direct_dependents: list[str] = field(default_factory=list)
    affected_tests: list[str] = field(default_factory=list)
    risk: str = "low"  # "high" | "medium" | "low"


@dataclass
class CodebaseIndex:
    """Full codebase index — carrier for structure, symbols, and dependency data."""

    schema_version: str = "1.0"
    indexed_at: str = ""
    root: str = ""
    files: dict[str, FileIndex] = field(default_factory=dict)
    symbols: list[Symbol] = field(default_factory=list)
    dependency_graph: dict[str, DependencyNode] = field(default_factory=dict)
    change_impact: dict[str, ChangeImpact] = field(default_factory=dict)
    stats: dict[str, int] = field(default_factory=dict)
