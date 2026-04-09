"""
handover/scaffold_extractor.py

v1.1.0 — Two-Layer Scaffold extraction.

Produces a `ScaffoldContext` from a populated `HandoverContext` and the
underlying conversation messages. The result is the single object passed to
`universal_generator.write_handover_dir()` and
`scaffold_generator.generate_claude_workspace()`.

Three sources of data:

1. **LLM body extraction** — one Claude API call returns 13 markdown bodies
   (overview, architecture, decisions, ...). Falls back to
   `scaffold_heuristics.extract_scaffold_no_llm()` when `use_llm=False`.
2. **Manifest + backlog assembly** — built from `HandoverContext` fields and
   metadata. No API call.
3. **Domain detection** — keyword-driven registry (`DOMAIN_RULES`) that maps
   chat signals to `.claude/agents/`, `.claude/skills/`, `.claude/commands/`,
   and `.claude/hooks/` content.

Loose-coupling rules:

- Both `DOMAIN_RULES` and `UNIVERSAL_SCAFFOLD_PROMPT` are module-level so
  tests can patch them and new contributors can extend them in one place.
- This module knows nothing about Jinja2, the filesystem, or click.
"""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field

import anthropic

from handover import __version__
from handover.models import (
    AgentSpec,
    Backlog,
    BacklogTask,
    CommandSpec,
    ConversationMessage,
    HandoverAPIError,
    HandoverContext,
    HandoverManifest,
    HookSpec,
    ScaffoldContext,
    SkillSpec,
)
from handover.scaffold_heuristics import extract_scaffold_no_llm

_MODEL = "claude-sonnet-4-6"
_MAX_CONV_CHARS = 60_000

# The 13 string fields the LLM is asked to produce. Order matches
# `ScaffoldContext` for clarity.
_BODY_FIELDS: tuple[str, ...] = (
    "overview",
    "architecture",
    "decisions",
    "constraints",
    "risks",
    "acceptance_criteria",
    "work_spec",
    "work_tasks",
    "work_milestones",
    "standards_coding",
    "standards_testing",
    "standards_security",
    "standards_release",
)

UNIVERSAL_SCAFFOLD_PROMPT = """\
You are generating a vendor-neutral project knowledge base from an AI chat.

Read the conversation below and produce ONE JSON object with these 13 keys.
Each value is a markdown body (no H1 headings — those are added by the
template). Return ONLY valid JSON, no markdown fences, no explanation.

Schema:
{{
  "overview": "<2-4 paragraph project overview, including goal and vision>",
  "architecture": "<tech stack summary + system design notes>",
  "decisions": "<ADR-style entries, one per major decision, numbered ADR-001, ADR-002, ...>",
  "constraints": "<bullet list of hard constraints and non-goals>",
  "risks": "<bullet list of open questions and known risks>",
  "acceptance_criteria": "<bullet list defining done for the current scope>",
  "work_spec": "<full feature spec — goal, scope, requirements, edge cases>",
  "work_tasks": "<markdown checklist of tasks, in implementation order>",
  "work_milestones": "<phase breakdown grouping the tasks>",
  "standards_coding": "<coding standards specific to this project's stack>",
  "standards_testing": "<testing standards, including coverage expectations>",
  "standards_security": "<security guardrails relevant to this project>",
  "standards_release": "<release checklist relevant to this project>"
}}

Rules:
- Be specific to THIS chat. Do not produce generic boilerplate.
- Use the project's actual tech stack and terminology.
- If a section has no content in the chat, write a 1-2 sentence stub that
  explains what should go there. Do not leave any value empty.
- Markdown only. No HTML.

Conversation:
{conversation}
"""


# ---------------------------------------------------------------------------
# Domain detection registry
# ---------------------------------------------------------------------------


@dataclass
class DomainRule:
    """
    Maps a set of chat signals to a `.claude/` agent specification.

    Add a new entry to `DOMAIN_RULES` to support a new domain — no other
    file changes are needed.
    """

    name: str
    description: str
    keywords: tuple[str, ...]
    system_prompt: str
    skills: tuple[SkillSpec, ...] = field(default_factory=tuple)
    commands: tuple[CommandSpec, ...] = field(default_factory=tuple)


DOMAIN_RULES: list[DomainRule] = [
    DomainRule(
        name="backend-agent",
        description="Backend / API engineering agent",
        keywords=(
            "fastapi",
            "django",
            "flask",
            "express",
            "rest",
            "endpoint",
            "api",
            "uvicorn",
            "graphql",
            "node.js",
            "spring",
        ),
        system_prompt=(
            "You implement backend services. Focus on correctness, error "
            "handling, observability, and clear API contracts. Always add "
            "tests for new endpoints."
        ),
        skills=(
            SkillSpec(
                name="rest-conventions",
                description="REST API conventions and status codes",
                body=(
                    "- Use plural resource names. Use HTTP verbs correctly.\n"
                    "- Return 4xx for client errors, 5xx for server errors.\n"
                    "- Validate every input at the boundary."
                ),
            ),
        ),
    ),
    DomainRule(
        name="frontend-agent",
        description="Frontend / UI engineering agent",
        keywords=(
            "react",
            "vue",
            "svelte",
            "angular",
            "frontend",
            "ui",
            "css",
            "tailwind",
            "component",
            "tsx",
            "jsx",
        ),
        system_prompt=(
            "You implement user-facing components. Prioritize accessibility, "
            "responsive layouts, and small reusable components."
        ),
        skills=(
            SkillSpec(
                name="accessibility-checklist",
                description="A11y rules to apply to every component",
                body=(
                    "- Every interactive element has a label.\n"
                    "- Color contrast meets WCAG AA.\n"
                    "- Keyboard navigation works without a mouse."
                ),
            ),
        ),
    ),
    DomainRule(
        name="database-agent",
        description="Database / data-model engineering agent",
        keywords=(
            "postgres",
            "postgresql",
            "mysql",
            "mongodb",
            "sqlite",
            "migration",
            "schema",
            "sql",
            "orm",
            "prisma",
            "alembic",
        ),
        system_prompt=(
            "You design and evolve data models. Always write reversible "
            "migrations. Index based on query patterns, not guesses."
        ),
    ),
    DomainRule(
        name="test-agent",
        description="Testing / QA agent",
        keywords=(
            "pytest",
            "jest",
            "vitest",
            "mocha",
            "junit",
            "unit test",
            "test coverage",
            "tdd",
            "fixture",
            "mock",
        ),
        system_prompt=(
            "You write tests first. Cover the happy path, edge cases, and "
            "error paths. Never mock the unit under test."
        ),
    ),
    DomainRule(
        name="devops-agent",
        description="DevOps / deployment agent",
        keywords=(
            "docker",
            "kubernetes",
            "k8s",
            "ci/cd",
            "github actions",
            "terraform",
            "ansible",
            "deploy",
            "helm",
            "ecs",
            "lambda",
        ),
        system_prompt=(
            "You automate build, test, and deploy. Make every pipeline "
            "reproducible. Treat infrastructure as code."
        ),
    ),
    DomainRule(
        name="docs-agent",
        description="Documentation agent",
        keywords=(
            "readme",
            "documentation",
            "api docs",
            "mkdocs",
            "sphinx",
            "swagger",
            "openapi",
            "docstring",
        ),
        system_prompt=(
            "You write clear, accurate, example-driven documentation. "
            "Verify every command and code sample before committing."
        ),
    ),
]


# A small default set of slash commands that apply to almost any project.
# Kept here so we don't ship `.claude/commands/` empty for projects that
# don't trigger any specific domain.
_DEFAULT_COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        name="run-tests",
        description="Run the project's full test suite",
        body=(
            "Run the project's tests. Choose the right command for the "
            "language: `pytest` for Python, `npm test` for Node, `cargo test` "
            "for Rust, etc. Report failures with file and line numbers."
        ),
    ),
    CommandSpec(
        name="lint",
        description="Run the project's linter and formatter",
        body=(
            "Run the linter and formatter for this project (e.g. ruff, "
            "eslint, gofmt). Auto-fix what you can; report what you can't."
        ),
    ),
)

# A small default hook so `.claude/hooks/` is non-empty when the user wants
# to start customizing automation. Loose-coupled — adding more is one entry.
_DEFAULT_HOOKS: tuple[HookSpec, ...] = (
    HookSpec(
        name="pre-tool-use.sh",
        event="PreToolUse",
        script=(
            "set -euo pipefail\n"
            "# Example: refuse to run destructive shell commands without\n"
            "# manual confirmation. Customize as needed.\n"
            'echo "[handover hook] PreToolUse fired" >&2\n'
        ),
    ),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_scaffold(
    messages: list[ConversationMessage],
    handover_context: HandoverContext,
    use_llm: bool,
    *,
    target: str = "claude-code",
    tool_version: str = __version__,
) -> ScaffoldContext:
    """
    Build a fully populated `ScaffoldContext`.

    Args:
        messages: Normalized conversation messages (used for both the LLM
            call and domain detection).
        handover_context: The summarizer's output. Provides goal, tasks,
            tech_stack, and metadata.
        use_llm: When True, makes one Claude API call for the 13 markdown
            bodies. When False, delegates to `scaffold_heuristics`.
        target: CLI `--target` value, recorded in the manifest.
        tool_version: handover version string, recorded in the manifest.

    Returns:
        A `ScaffoldContext` with manifest, backlog, 13 markdown bodies, and
        domain-detected agents/skills/commands/hooks all populated.

    Raises:
        HandoverAPIError: If `use_llm=True` and the API call fails.
    """
    scaffold = _extract_with_llm(messages) if use_llm else extract_scaffold_no_llm(handover_context)

    scaffold.manifest = _build_manifest(handover_context, target=target, tool_version=tool_version)
    scaffold.backlog = _build_backlog(handover_context)

    agents, skills, commands, hooks = detect_domains(handover_context, messages)
    scaffold.agents = agents
    scaffold.skills = skills
    scaffold.commands = commands
    scaffold.hooks = hooks

    return scaffold


def detect_domains(
    handover_context: HandoverContext,
    messages: list[ConversationMessage],
) -> tuple[list[AgentSpec], list[SkillSpec], list[CommandSpec], list[HookSpec]]:
    """
    Walk `DOMAIN_RULES` and produce the `.claude/` workspace contents.

    The detection corpus is the lower-cased concatenation of:
      - tech stack values
      - decision topics + decision text
      - task titles + descriptions
      - assistant + user message contents

    Returns four lists ready to drop into `ScaffoldContext`. The lists may
    be empty (no matching domains found), in which case the caller should
    still create empty `.claude/` subdirectories — never error.
    """
    corpus = _build_corpus(handover_context, messages)

    agents: list[AgentSpec] = []
    skills: list[SkillSpec] = []
    seen_agent_names: set[str] = set()
    seen_skill_names: set[str] = set()

    for rule in DOMAIN_RULES:
        if not _rule_matches(rule, corpus):
            continue
        if rule.name in seen_agent_names:
            continue
        seen_agent_names.add(rule.name)
        agents.append(
            AgentSpec(
                name=rule.name,
                description=rule.description,
                keywords=list(rule.keywords),
                system_prompt=rule.system_prompt,
            )
        )
        for skill in rule.skills:
            if skill.name in seen_skill_names:
                continue
            seen_skill_names.add(skill.name)
            skills.append(skill)

    # Default commands and hooks ship regardless of detected domains so the
    # `.claude/` workspace is always immediately usable.
    commands = list(_DEFAULT_COMMANDS)
    hooks = list(_DEFAULT_HOOKS)

    return agents, skills, commands, hooks


# ---------------------------------------------------------------------------
# LLM body extraction
# ---------------------------------------------------------------------------


def _extract_with_llm(messages: list[ConversationMessage]) -> ScaffoldContext:
    """
    Make a single Claude API call to produce the 13 markdown bodies.

    Raises:
        HandoverAPIError: On authentication failure or API error.
    """
    conversation_text = "\n".join(f"{m.role.upper()}: {m.content}" for m in messages)
    if len(conversation_text) > _MAX_CONV_CHARS:
        conversation_text = conversation_text[-_MAX_CONV_CHARS:]
    prompt = UNIVERSAL_SCAFFOLD_PROMPT.format(conversation=conversation_text)

    try:
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
        response = client.messages.create(
            model=_MODEL,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as e:
        raise HandoverAPIError(
            "ANTHROPIC_API_KEY is not set or invalid. Use --no-llm or "
            "--no-handover-dir to skip the scaffold extraction."
        ) from e
    except anthropic.APIError as e:
        raise HandoverAPIError(
            f"Anthropic API error during scaffold extraction: {e}. Use --no-llm as fallback."
        ) from e

    raw_text = getattr(response.content[0], "text", None)
    if not isinstance(raw_text, str):
        raise HandoverAPIError("Unexpected response block type from API.")

    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        raw = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise HandoverAPIError(
            f"Scaffold model returned invalid JSON: {e}. Raw: {raw_text[:200]}"
        ) from e

    if not isinstance(raw, dict):
        raise HandoverAPIError("Scaffold model returned non-object JSON.")

    scaffold = ScaffoldContext()
    for field_name in _BODY_FIELDS:
        value = raw.get(field_name, "")
        if not isinstance(value, str):
            value = str(value)
        setattr(scaffold, field_name, value)
    return scaffold


# ---------------------------------------------------------------------------
# Manifest + backlog assembly (no LLM call)
# ---------------------------------------------------------------------------


def _build_manifest(
    ctx: HandoverContext,
    *,
    target: str,
    tool_version: str,
) -> HandoverManifest:
    return HandoverManifest(
        version=tool_version,
        generated_at=_now_iso(),
        source=ctx.source,
        target=target,
        project=ctx.conversation_title or ctx.goal or "Untitled project",
    )


def _build_backlog(ctx: HandoverContext) -> Backlog:
    now = _now_iso()
    backlog_tasks: list[BacklogTask] = []
    for i, t in enumerate(ctx.tasks, start=1):
        backlog_tasks.append(
            BacklogTask(
                id=f"task-{i:03d}",
                title=t.title,
                description=t.description,
                phase="1",
                priority=t.priority,
                done=t.done,
                tags=[],
                added_at=now,
                done_at=now if t.done else None,
            )
        )
    return Backlog(
        schema_version="1.0",
        updated_at=now,
        project=ctx.conversation_title or ctx.goal or "Untitled project",
        tasks=backlog_tasks,
        milestones=[],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_corpus(ctx: HandoverContext, messages: list[ConversationMessage]) -> str:
    parts: list[str] = []
    parts.extend(str(v) for v in ctx.tech_stack.values() if v)
    for d in ctx.decisions:
        parts.append(d.topic)
        parts.append(d.decision)
    for t in ctx.tasks:
        parts.append(t.title)
        parts.append(t.description)
    for m in messages:
        parts.append(m.content)
    return "\n".join(parts).lower()


def _rule_matches(rule: DomainRule, corpus: str) -> bool:
    return any(keyword.lower() in corpus for keyword in rule.keywords)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
