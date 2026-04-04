# Product Requirements Document
## `handover-cli` — Universal AI Chat to Local Agent Handover Tool

**Version:** 0.2  
**Status:** Approved for Implementation  
**Author:** Mohan  
**Date:** 2026-04-04  
**PyPI name:** `handover-cli` (check if `handover` is available first — prefer shorter name)  
**CLI command:** `handover` (regardless of PyPI name)  
**GitHub repo:** `handover`  
**Local path:** `/Users/mohankrishnaalavala/Documents/project_handover`

---

## 1. Vision

> *"Design in chat. Build in terminal. Zero context lost."*

`handover` is an open-source CLI tool that bridges AI chat interfaces (Claude, ChatGPT, Gemini, and others) to local terminal coding agents (Claude Code, Codex CLI, etc.). It extracts decisions, plans, and intent from a chat conversation and generates structured handover artifacts that a local agent can immediately act on — without the user having to re-explain anything.

---

## 2. Problem Statement

Developers increasingly use AI chat interfaces for ideation, system design, and planning — then switch to terminal agents like Claude Code to implement. This context switch is painful:

- The terminal agent starts with zero knowledge of decisions made in chat
- Users manually re-paste requirements, tech stack choices, and constraints
- Context is lost, duplicated, or summarized incorrectly
- There is no standard, machine-readable format for "what was decided in this chat"

No open-source tool exists that formalizes this handover workflow.

---

## 3. Goals

### Must Have (Phase 1)
- Parse a Claude chat export (JSONL or JSON) for a single conversation
- Extract: goal, tech stack decisions, open tasks, constraints, non-goals
- Generate a `CLAUDE.md` and `PLAN.md` that Claude Code auto-ingests
- Single CLI command: `handover --input chat.json --output ./my-project/`
- `handover list` subcommand to enumerate conversations in a bulk export
- Open source, MIT licensed, Python-based CLI

### Should Have (Phase 1)
- Summarization via Anthropic API (Claude Sonnet) to handle noisy conversations
- Conflict resolution: when a decision was revised mid-chat, take the latest
- Support both full bulk JSONL export and single-conversation JSON (browser extension)
- `--no-llm` mode with documented rule-based heuristics (no API key required)
- `handover init` subcommand to scaffold customizable templates
- `schema_version` and `source_version` fields in HandoverContext for forward compatibility
- Clean, readable output a human can also understand and edit

### Won't Have (Phase 1)
- GUI or web interface
- ChatGPT / Gemini support (Phase 2)
- Reverse handover (terminal → chat) — Phase 3, but spec'd here
- Real-time / live sync between chat and terminal

---

## 4. User Personas

**Primary: Mohan (Developer using Claude for design + Claude Code for implementation)**
- Uses Claude chat to think through architecture, APIs, data models
- Switches to `claude` CLI to implement
- Loses all chat context every time
- Wants one command to bridge the gap

**Secondary: Any developer using AI chat + AI terminal agent**
- May use ChatGPT for design, Claude Code for implementation (Phase 2)
- May work in teams where one person designs in chat, another implements

---

## 5. Phases

### Phase 1 — Claude Chat → Claude Terminal Agent *(this document)*
Input: Claude chat export. Output: `CLAUDE.md` + `PLAN.md`.

### Phase 2 — Universal Chat Sources
Add adapters for: ChatGPT export, Gemini export, Perplexity, and others.
Same output format — adapters are pluggable. Each adapter is an isolated PR a contributor can own end-to-end. This is the primary open-source contribution path.

### Phase 3 — Reverse Handover (Terminal → Chat) *(elevated — high value)*
Pull Claude Code session logs from `~/.claude/projects/*.jsonl` back into a
readable handover document — for chat review, session retrospectives, onboarding
a teammate, or resuming a dead session that hit the context wall.
This solves a pain point as real as the forward direction:
*"My Claude Code session died at 90% complete. How do I continue it in a new session?"*
Output: `HANDOVER.md` — a human-readable summary of what was done, what's left,
and what decisions were made during implementation.

### Phase 4 — Target Agent Adapters
Beyond Claude Code: Codex CLI, Aider, Goose, and other terminal agents.
Each may need a slightly different context format.

---

## 6. Architecture

```
┌──────────────────────────────────────────────────────────┐
│                      handover CLI                         │
│                                                           │
│  ┌──────────┐    ┌────────────┐    ┌───────────────────┐  │
│  │  Parser  │───▶│ Summarizer │───▶│     Generator     │  │
│  │(adapter) │    │(Claude API)│    │  (artifact out)   │  │
│  └──────────┘    └────────────┘    └───────────────────┘  │
│       │                                      │             │
│  [chat.json]                         [CLAUDE.md]           │
│  [chat.jsonl]                        [PLAN.md]             │
└──────────────────────────────────────────────────────────┘
```

### Components

**Parser (adapter pattern)**
- Input: raw export file (JSONL, JSON, Markdown)
- Output: normalized `ConversationMessage[]`
- One adapter per source (claude, chatgpt, gemini, ...)
- Phase 1: Claude adapter only
- Auto-detects format; can be overridden with `--source claude`

**Summarizer**
- Input: normalized messages
- Calls Claude Sonnet API with a structured extraction prompt
- Output: `HandoverContext` (JSON)
- Falls back to rule-based extraction when `--no-llm` is set

**Generator**
- Input: `HandoverContext`
- Output: `CLAUDE.md`, `PLAN.md`
- Jinja2 templates, customizable via `handover init`

---

## 7. Data Model

### ConversationMessage
```python
@dataclass
class ConversationMessage:
    role: str           # "user" | "assistant"
    content: str
    timestamp: str | None
    message_id: str | None
```

### HandoverContext
```python
@dataclass
class HandoverContext:
    schema_version: str          # e.g. "1.0" — bump when schema changes
    source: str                  # "claude" | "chatgpt" | ...
    source_version: str          # export format version detected
    conversation_title: str
    conversation_id: str | None
    extracted_at: str            # ISO timestamp
    goal: str
    tech_stack: dict             # {"language": "Python", "framework": "FastAPI", ...}
    decisions: list[Decision]    # [{topic, decision, rationale}]
    tasks: list[Task]            # [{title, description, priority, done}]
    constraints: list[str]
    non_goals: list[str]
    open_questions: list[str]
```

> **Why `schema_version` + `source_version`?**
> Claude's export format has already changed once. These fields let future parser
> versions detect the format variant and route accordingly without user-visible breakage.

---

## 8. `--no-llm` Rule-Based Extraction Heuristics

When `--no-llm` is set, the summarizer uses these rules instead of calling the API:

| Field | Rule |
|-------|------|
| `goal` | First user message, or message containing "I want to build", "build a", "create a", "we need to" |
| `decisions` | Messages containing "let's use", "we'll go with", "decided to", "we should use", "I think we should" |
| `constraints` | Messages containing "must", "cannot", "should not", "requirement:", "constraint:" |
| `non_goals` | Messages containing "not in scope", "out of scope", "won't", "we don't need", "skip" |
| `tasks` | Numbered lists or bullet points in assistant messages; messages starting with "Next steps:" or "TODO:" |
| `tech_stack` | Known tech keywords: language names, framework names, database names — matched via a bundled keyword list |
| Conflict resolution | When the same topic appears multiple times, the **last** occurrence wins |

These heuristics are intentionally simple and transparent. They are documented so
contributors can improve them via PRs without touching the API summarizer.

---

## 9. Input Formats Supported (Phase 1)

| Source | Format | How to Get |
|--------|--------|------------|
| Claude.ai bulk export | `.jsonl` (one JSON object per line) | Settings → Privacy → Export Data |
| Claude.ai single chat | `.json` | Claude Conversation Exporter browser extension |
| Claude.ai single chat | `.md` | Browser extension (Markdown export) |

---

## 10. Output Artifacts

### `CLAUDE.md`
Auto-ingested by Claude Code at session start. Example:
```markdown
# Project: <goal>
<!-- Generated by handover v0.1.0 from Claude chat on 2026-04-04 -->

## Tech Stack
- Language: Python
- Framework: FastAPI
- Database: PostgreSQL

## Key Decisions
- Use async handlers throughout (rationale: expected high concurrency)
- JWT for auth, not sessions (rationale: stateless API)

## Constraints
- Must run offline
- No external analytics

## Non-Goals
- Mobile app (v1)

## Open Questions
- [ ] Which ORM: SQLAlchemy vs Tortoise?

## Handover Source
- Chat title: "API Design Discussion"
- Exported: 2026-04-04T10:30:00Z
```

### `PLAN.md`
Task checklist for Claude Code:
```markdown
# Implementation Plan
<!-- Generated by handover v0.1.0 -->

## Tasks
- [ ] Set up FastAPI project scaffold
- [ ] Implement JWT auth middleware
- [ ] Define PostgreSQL schema
- [ ] Write unit tests for auth

## Open Questions to Resolve First
- [ ] Choose ORM (SQLAlchemy vs Tortoise)
```

---

## 11. CLI Interface

```bash
# ── Core commands ──────────────────────────────────────────

# Basic usage — single conversation file
handover --input conversation.json --output ./my-project/

# Bulk JSONL — must use --title or --id to select conversation
handover --input export.jsonl --title "API Design Discussion" --output ./my-project/
handover --input export.jsonl --id "abc123" --output ./my-project/

# ── List subcommand — enumerate conversations in bulk export ──
handover list export.jsonl
# Output:
#   ID        DATE        TITLE
#   abc123    2026-04-01  API Design Discussion
#   def456    2026-03-28  Database Schema Planning
#   ghi789    2026-03-25  Auth Strategy

# ── Init subcommand — scaffold custom templates ────────────
handover init
# Creates: ~/.handover/templates/claude_md.j2
#          ~/.handover/templates/plan_md.j2
# User can edit these to customize output format

# ── Flags ─────────────────────────────────────────────────
handover --input chat.json --output ./my-project/ --source claude   # explicit adapter
handover --input chat.json --output ./my-project/ --dry-run         # print, don't write
handover --input chat.json --output ./my-project/ --no-llm          # rule-based only
handover --input chat.json --output ./my-project/ --launch          # run `claude` after
handover --input chat.json --output ./my-project/ --template ~/.handover/templates/
```

### `--dry-run` Output (shown in README)
```
$ handover --input chat.json --dry-run

🔍 Parsing conversation: "API Design Discussion"
   Source: claude | Messages: 34 | Format: single-json v1.0

📋 Extracted HandoverContext:
   Goal: Build a FastAPI REST API with JWT auth and PostgreSQL
   Tech Stack: Python, FastAPI, PostgreSQL, pytest
   Decisions:
     • async handlers — high concurrency expected
     • JWT auth — stateless API requirement
   Tasks: 6 items
   Constraints: 2
   Open Questions: 1

📄 Would write:
   → ./my-project/CLAUDE.md  (1.2 KB)
   → ./my-project/PLAN.md    (0.4 KB)

Run without --dry-run to write files.
```

---

## 12. Project Structure

```
handover/
├── handover/
│   ├── __init__.py
│   ├── cli.py                   # Click CLI entry point (main + list + init subcommands)
│   ├── models.py                # ConversationMessage, HandoverContext, Decision, Task
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseParser abstract class
│   │   └── claude.py            # Claude JSONL + single-JSON adapter
│   ├── summarizer.py            # Anthropic API extraction + --no-llm fallback
│   ├── heuristics.py            # Rule-based extraction logic (--no-llm mode)
│   ├── generator.py             # CLAUDE.md + PLAN.md writer via Jinja2
│   └── templates/
│       ├── claude_md.j2         # Default CLAUDE.md template
│       └── plan_md.j2           # Default PLAN.md template
├── tests/
│   ├── fixtures/
│   │   ├── claude_single.json   # Anonymized single-chat export
│   │   └── claude_bulk.jsonl    # Anonymized bulk export (3 conversations)
│   ├── test_parser.py
│   ├── test_heuristics.py
│   ├── test_summarizer.py       # Mocked API calls
│   └── test_generator.py        # File output assertions
├── docs/
│   ├── getting-started.md
│   ├── adding-an-adapter.md     # Guide for Phase 2 contributors
│   └── output-format.md
├── .claude/
│   ├── agents/
│   │   ├── parser-agent.md      # Specialized agent for parsing work
│   │   ├── test-agent.md        # Specialized agent for writing tests
│   │   └── docs-agent.md        # Specialized agent for documentation
│   ├── commands/
│   │   ├── add-adapter.md       # /add-adapter: scaffold new source adapter
│   │   ├── run-tests.md         # /run-tests
│   │   └── update-prd.md        # /update-prd
│   └── skills/
│       └── anthropic-api.md     # Skill: how to call Anthropic API correctly
├── CLAUDE.md                    # Claude Code instructions for THIS repo
├── PLAN.md                      # Current implementation tasks
├── CONTRIBUTING.md              # How to add a new source adapter
├── README.md
├── LICENSE                      # MIT
├── pyproject.toml
├── .gitignore
└── .github/
    ├── workflows/
    │   ├── ci.yml               # pytest on push/PR (Python 3.11, 3.12)
    │   └── release.yml          # PyPI publish on version tag
    ├── ISSUE_TEMPLATE/
    │   ├── bug_report.md
    │   └── feature_request.md
    └── PULL_REQUEST_TEMPLATE.md
```

---

## 13. CLAUDE.md (for this repo)

```markdown
# handover — Universal AI Chat to Local Agent Handover Tool

## Project Goal
CLI tool that parses AI chat exports and generates CLAUDE.md + PLAN.md
artifacts for local terminal agents to ingest. Phase 1: Claude chat only.

## Tech Stack
- Language: Python 3.11+
- CLI: Click (with subcommands: main, list, init)
- Templates: Jinja2
- API: Anthropic SDK (claude-sonnet-4-6 for summarization)
- Testing: pytest + pytest-cov
- Packaging: pyproject.toml / hatchling

## Architecture Rules
- Parser uses adapter pattern: one class per source in parsers/
- BaseParser in parsers/base.py defines the interface all adapters must implement
- Summarizer calls Claude API unless --no-llm; then delegates to heuristics.py
- Heuristics are keyword-rule-based — keep them simple and documented
- Generator uses Jinja2 templates only — never hardcode output format in Python
- All data models are dataclasses in models.py with full type hints
- schema_version must be bumped in models.py when HandoverContext fields change

## Coding Standards
- Type hints on all functions and methods
- Docstrings on all public methods
- Tests required for: parser output, heuristics rules, generator file output
- Mocked API calls in test_summarizer.py — never hit real API in tests
- No dependencies beyond: click, anthropic, jinja2, pytest, pytest-cov

## Key Commands
- Run tests: pytest tests/ -v --cov=handover
- Install locally: pip install -e .
- Run CLI: handover --help

## Phase 1 Focus
- Claude adapter only (parsers/claude.py)
- Do NOT build ChatGPT adapter yet — that is Phase 2
- Both input formats: .jsonl (bulk) and .json (single chat via browser extension)
```

---

## 14. Open Source Setup Checklist

- [ ] **PyPI name:** Check `pip install handover` first. Use `handover-cli` if taken.
- [ ] **License:** MIT, copyright: Mohan Krishnaa Alavala, year: 2026
- [ ] **README.md:** Vision tagline, install, `--dry-run` terminal demo block, contributing link
- [ ] **pyproject.toml:** Entry point `handover = handover.cli:main`, hatchling backend
- [ ] **GitHub Actions CI:** pytest on push + PRs, Python 3.11 + 3.12
- [ ] **GitHub Actions Release:** PyPI publish on version tag via Trusted Publisher
- [ ] **Issue templates:** Bug report + feature request
- [ ] **PR template:** Checklist (tests added, docs updated, adapter guide followed for Phase 2+)
- [ ] **CONTRIBUTING.md:** Adapter contribution path as primary contribution type
- [ ] **GitHub Topics:** `claude`, `claude-code`, `cli`, `handover`, `agent`, `open-source`, `python`

---

## 15. Phase 1 Implementation Tasks (PLAN.md)

```markdown
## Setup
- [ ] Initialize repo, MIT license, pyproject.toml, .gitignore
- [ ] Create full folder structure per Section 12

## Models
- [ ] Implement ConversationMessage dataclass (models.py)
- [ ] Implement Decision and Task dataclasses (models.py)
- [ ] Implement HandoverContext dataclass with schema_version + source_version (models.py)

## Parser
- [ ] Implement BaseParser abstract class (parsers/base.py)
- [ ] Implement ClaudeParser for .jsonl bulk export (parsers/claude.py)
- [ ] Implement ClaudeParser for single-conversation .json (parsers/claude.py)
- [ ] Add format auto-detection (jsonl vs json vs markdown)
- [ ] Add source_version detection for Claude export format variants

## Summarizer
- [ ] Implement Summarizer using Anthropic API (summarizer.py)
- [ ] Write structured extraction prompt → returns valid HandoverContext JSON
- [ ] Add conflict resolution logic (latest decision wins by message order)
- [ ] Implement --no-llm delegation to heuristics.py

## Heuristics (--no-llm mode)
- [ ] Implement goal extraction rule (first user message / intent keywords)
- [ ] Implement decision extraction rule (keyword matching)
- [ ] Implement constraint extraction rule
- [ ] Implement non-goals extraction rule
- [ ] Implement task extraction rule (lists + "next steps" patterns)
- [ ] Implement tech stack extraction (bundled keyword list)
- [ ] Conflict resolution: last occurrence wins

## Generator
- [ ] Implement Generator with Jinja2 (generator.py)
- [ ] Write CLAUDE.md template (templates/claude_md.j2)
- [ ] Write PLAN.md template (templates/plan_md.j2)

## CLI
- [ ] Implement main command with all flags (cli.py)
- [ ] Implement `handover list` subcommand
- [ ] Implement `handover init` subcommand
- [ ] Implement --dry-run mode with formatted console output
- [ ] Implement --launch flag (exec `claude` in output dir after writing)

## Tests
- [ ] test_parser.py — single JSON + bulk JSONL fixtures
- [ ] test_heuristics.py — each rule tested independently
- [ ] test_summarizer.py — mocked API, validate HandoverContext schema
- [ ] test_generator.py — assert file output matches expected structure
- [ ] Add anonymized test fixtures to tests/fixtures/

## Docs + OSS
- [ ] README.md with --dry-run terminal demo block
- [ ] CONTRIBUTING.md with adapter contribution guide
- [ ] docs/adding-an-adapter.md (Phase 2 contributor guide)
- [ ] docs/output-format.md
- [ ] GitHub Actions CI (ci.yml)
- [ ] GitHub Actions Release (release.yml) — PyPI Trusted Publisher
- [ ] GitHub issue + PR templates
- [ ] Publish v0.1.0 to PyPI
```

---

## 16. Success Metrics (Phase 1)

- Developer goes from raw Claude export → `claude` session with full context in under 60 seconds
- Generated `CLAUDE.md` requires minimal manual editing before use
- `--no-llm` mode works offline with no API key
- At least one external contributor opens a PR for a Phase 2 adapter (ChatGPT)
- `pip install handover-cli` works and `handover --help` runs cleanly

---

## 17. Roadmap Summary

| Phase | Source | Target | Status |
|-------|--------|--------|--------|
| 1 | Claude chat | Claude Code | **This document** |
| 2 | ChatGPT, Gemini, Perplexity | Claude Code | Open contribution path |
| 3 | Claude Code sessions (`~/.claude/projects/`) | Claude chat | High value — spec next |
| 4 | Any chat | Codex CLI, Aider, Goose | Future |

---

*This PRD is the source of truth. When in doubt, refer back here.*
*Version history: v0.1 initial draft → v0.2 expert review applied (PyPI name, --no-llm heuristics spec, handover list subcommand, handover init subcommand, schema_version/source_version fields, Phase 3 elevated, README dry-run requirement added)*
