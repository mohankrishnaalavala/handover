# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [1.1.1] - 2026-04-09

### Added — MCP server now exposes four tools

The MCP server (`handover mcp`) used to expose only `run_handover`. With the
v1.1.0 two-layer scaffold landed, `backlog.json` is now a stable
machine-readable surface — three additional tools wrap existing logic so a
developer can stay entirely in chat.

- **`run_handover`** *(updated)* — generates the workspace, and now lists the
  `.handover/` subdirectories and `.claude/` workspace counts in the response.
- **`handover_status`** *(new)* — reads `.handover/work/backlog.json` and
  returns total/done/remaining counts, high-priority items, next task, and
  last completed task. Perfect for "where are we?" from chat.
- **`handover_reverse`** *(new)* — auto-discovers the most recent Claude Code
  session for `project_dir`, runs the existing `reverse()` orchestrator, and
  writes `HANDOVER.md`. Returns a short text summary.
- **`handover_list`** *(new)* — lists conversations inside a chat export file
  (id / date / title), capped at 20 with a "+ N more" tail.

Each `@mcp.tool()` wrapper delegates to a plain `*_impl` function so the core
logic is unit-testable without the MCP SDK. See [docs/mcp-server.md](docs/mcp-server.md).

### Changed
- `run_handover_impl` return string now includes `.handover/` and `.claude/`
  summary lines when the two-layer scaffold is produced.

### Migration
- No breaking changes. The new tools are additive; existing `run_handover`
  callers see only an enriched return string.

---

## [1.1.0] - 2026-04-09

### Added — Two-Layer Scaffold (`.handover/` + `.claude/`)

The biggest output change since v1.0: every run now produces a vendor-neutral
project knowledge base in `.handover/` plus a thin per-target workspace
(`.claude/` for `claude-code`). Costs exactly one extra Claude API call per
run (or zero with `--no-llm`).

- **`.handover/` (Layer 1 — universal)**: 21 files across 4 subdirectories
  - `manifest.yaml` — version, source, target, project, generated_at
  - `context/` — `overview.md`, `architecture.md`, `decisions.md` (ADR format),
    `constraints.md`, `risks.md`, `acceptance-criteria.md`
  - `work/` — `spec.md`, `tasks.md`, `milestones.md`, `backlog.json`
  - `standards/` — `coding-standards.md`, `testing-standards.md`,
    `security-guardrails.md`, `release-checklist.md`
  - `prompts/` — `implement.md`, `review.md`, `debug.md`, `test.md`,
    `onboard.md`, `continue.md`
- **`.claude/` (Layer 2 — claude-code target)**: domain-detected workspace
  - `agents/<name>.md` — backend, frontend, database, test, devops, docs
    agents triggered by chat keywords (registry-driven)
  - `skills/<name>.md` — attached to detected domains
  - `commands/<name>.md` — default `run-tests`, `lint`
  - `hooks/pre-tool-use.sh` — chmod +x'd on write
  - `settings.json`
- New CLI flags on `handover` main command:
  - `--no-handover-dir` — skip Layer 1 (legacy v1.0.x output only)
  - `--handover-dir-only` — write Layer 1, skip target files
  - `--overwrite-handover-dir` — replace existing `.handover/` and `.claude/`
- New modules (loosely coupled — each adds via a registry, not an `if/elif`):
  - `handover/scaffold_extractor.py` — one LLM call → 13 markdown bodies +
    `DOMAIN_RULES` registry for domain detection
  - `handover/scaffold_heuristics.py` — pure-function `--no-llm` fallback
  - `handover/universal_generator.py` — writes `.handover/` from
    `HANDOVER_DIR_FILES` registry
  - `handover/scaffold_generator.py` — writes `.claude/` workspace
- New dataclasses in `handover/models.py`: `HandoverManifest`, `BacklogTask`,
  `Milestone`, `Backlog`, `AgentSpec`, `SkillSpec`, `CommandSpec`, `HookSpec`,
  `ScaffoldContext`. All carry `schema_version` for forward compatibility.
- 26 new Jinja2 templates under `handover/templates/handover/` and
  `handover/templates/{agent,skill,command,hook_pre_tool_use,settings_json}.j2`,
  plus `claude_md_v2.j2` (a thin <50-line CLAUDE.md that indexes into
  `.handover/`).
- `handover serve`: `POST /config` accepts `no_handover_dir`; `POST /handover`
  generates the two-layer output.
- `docs/handover-directory.md` — user guide to the new layout.

### Notes
- Default behavior changes: `handover --input chat.json --output dir/` now
  writes `.handover/` and `.claude/` in addition to `CLAUDE.md` + `PLAN.md`.
  Use `--no-handover-dir` for the v1.0.x layout.
- Adding a new agent domain is one entry in `DOMAIN_RULES`.
  Adding a new `.handover/` file is one entry in `HANDOVER_DIR_FILES` plus a
  `.j2` template.

## [1.0.1] - 2026-04-06

### Fixed
- `handover mcp`: `FastMCP.__init__()` no longer accepts `version` or `description`
  kwargs in mcp>=1.27. Updated to use `instructions` — fixes MCP server crash on startup
  in Claude Desktop and Claude Code.
- `handover reverse --no-llm`: tightened decision-extraction heuristics to require
  ≥20 trailing chars and ≥35 total chars per match, eliminating false positives
  like short fragments ("using a distinct name:") that were not real decisions.

## [1.0.0] - 2026-04-06

### Added
- `handover serve` — local HTTP bridge for the browser extension (port 7437 = H-A-N-D)
  - `GET /health` — liveness check
  - `POST /handover` — run full pipeline from raw conversation JSON
  - `POST /config` — update output dir / no-llm at runtime
  - CORS headers on all responses for browser extension compatibility
  - `--daemon` flag spawns a background process, writes PID to `~/.handover/server.pid`
- Chrome / Firefox extension (Manifest V3) in `extension/`
  - Content scripts for claude.ai and chat.openai.com — DOM message extraction
  - Background service worker — routes extraction results to `handover serve`
  - Popup UI — output directory, port config, one-click "Send to Claude Code" button
- `scripts/build-extension.sh` — packages `extension/` into `dist/handover-extension.zip`
- `docs/browser-extension.md` — install and usage guide for the extension
- `handover/__main__.py` — enables `python -m handover` (used by daemon subprocess)

### Phase 4 additions (reverse handover)
- `handover reverse` — generate `HANDOVER.md` from a Claude Code session log
  - Extracts files changed, commands run, decisions, task completion (matched against PLAN.md)
  - LLM-based decisions + next steps via `claude-sonnet-4-6`; `--no-llm` for offline mode
  - `--dry-run` to preview without writing
- `handover sessions` — list recent Claude Code sessions for a project
- `handover watch` — auto-generate `HANDOVER.md` when a session stops growing  
  (requires `pip install handover[watch]`; `--daemon` for background mode)
- `handover/parsers/claude_code.py` — `ClaudeCodeSessionParser` reading `~/.claude/projects/` JSONL
- `handover/reverse.py` — reverse pipeline orchestrator
- `handover/watcher.py` — `watchdog`-based session file monitor with debounce
- `handover/templates/handover_md.j2` — HANDOVER.md Jinja2 template
- `Generator.generate_handover()` — renders HANDOVER.md from `SessionContext`
- New models: `FileChange`, `SessionMeta`, `SessionContext` in `models.py`
- `watchdog>=4.0` optional dependency in `[watch]` extra
- `docs/reverse-handover.md` — user guide

### Phase 5 additions (multi-target)
- `--target` flag: `claude-code` (default), `codex`, `aider`, `goose`, `all`
- Target adapter pattern in `handover/targets/` — mirrors parser adapter pattern
- Codex CLI target (`AGENTS.md`)
- Aider target (`.aider.conf.yml`)
- Goose agent target (`goose-context.json`)
- `--target all` writes every registered target in one pass
- `docs/adding-a-target.md` — developer guide for new targets

### Phase 6 additions (ecosystem & developer experience)
- `handover mcp` — FastMCP server so Claude Code can call handover as a tool
  (requires `pip install handover[mcp]`)
- `handover history` — list past runs from `~/.handover/history.jsonl`
- `handover rerun <id>` — re-run any past handover by history ID
- `handover merge` — merge multiple chat exports into one unified context
- `handover pull <gist_url>` — pull shared handover artifacts from a GitHub Gist
- `--publish` flag — publish generated artifacts to GitHub Gist after writing
  (requires `gh` CLI authenticated)
- History recorded automatically after every successful non-dry-run invocation
- `[mcp]` optional extra: `pip install handover[mcp]`

## [0.2.0] - 2026-04-05

### Added
- Claude adapter (`parsers/claude.py`) supporting both `.jsonl` (bulk export) and `.json` (single chat / browser extension) input formats
- Support for Claude bulk JSON array export format (`conversations.json`)
- Adapter pattern with `BaseParser` in `parsers/base.py` — extensible to future sources (ChatGPT, Gemini, etc.)
- Heuristic summarizer (`heuristics.py`) for keyword-based context extraction when `--no-llm` is passed
- LLM summarizer using Anthropic SDK (`claude-sonnet-4-6`) for AI-generated `CLAUDE.md` and `PLAN.md` artifacts
- Jinja2-based generator with templates for `CLAUDE.md` and `PLAN.md`
- CLI (`handover`) with subcommands: `run`, `list`, `init`
- `--no-llm` flag for offline/heuristic-only mode
- Full test suite with 80% coverage gate
- GitHub Actions CI (lint + test matrix on Python 3.11 + 3.12)
- GitHub Actions release pipeline to TestPyPI and PyPI via Trusted Publisher

[1.0.0]: https://github.com/mohankrishnaalavala/handover/compare/v0.2.0...v1.0.0
[0.2.0]: https://github.com/mohankrishnaalavala/handover/releases/tag/v0.2.0
