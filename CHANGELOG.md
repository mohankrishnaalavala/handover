# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

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
