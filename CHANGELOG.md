# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased] — Phase 3 (v0.3.0)

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

[Unreleased]: https://github.com/mohankrishnaalavala/handover/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/mohankrishnaalavala/handover/releases/tag/v0.2.0
