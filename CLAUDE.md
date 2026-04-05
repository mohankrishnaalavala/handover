# handover — Universal AI Chat to Local Agent Handover Tool

## Project Goal
CLI tool that parses AI chat exports and generates CLAUDE.md + PLAN.md
artifacts for local terminal agents to ingest.

**Current state:** v0.2.0 released — Phase 1 (Claude) + Phase 2 (ChatGPT, Gemini, Perplexity) complete.  
**Active branch:** Phase 3 — `handover serve` HTTP bridge + Chrome/Firefox extension.

## Tech Stack
- Language: Python 3.11+
- CLI: Click (subcommands: main, list, init, serve)
- Templates: Jinja2
- API: Anthropic SDK (claude-sonnet-4-6 for summarization)
- HTTP server: stdlib `http.server` + `socketserver.ThreadingMixIn` (no Flask)
- Testing: pytest + pytest-cov
- Packaging: pyproject.toml / hatchling

## Architecture Rules
- Parser uses adapter pattern: one class per source in `parsers/`
- `BaseParser` in `parsers/base.py` defines the interface all adapters must implement
- Summarizer calls Claude API unless `--no-llm`; then delegates to `heuristics.py`
- Heuristics are keyword-rule-based — keep them simple and documented
- Generator uses Jinja2 templates only — never hardcode output format in Python
- All data models are dataclasses in `models.py` with full type hints
- `schema_version` must be bumped in `models.py` when `HandoverContext` fields change
- **Phase 3:** `handover/server.py` is the HTTP bridge. All responses must include CORS headers (`Access-Control-Allow-Origin: *`). Port 7437 (H-A-N-D) is the default.
- **Phase 3:** The browser extension lives in `extension/` (MV3). Content scripts extract DOM messages; `background.js` POSTs to the local server. Keep extension JS dependency-free (no bundler required).
- **Phase 3:** Daemon mode in `handover serve --daemon` spawns a subprocess via `python -m handover serve` and writes PID to `~/.handover/server.pid`.

## Coding Standards
- Type hints on all functions and methods
- Docstrings on all public methods
- Tests required for: parser output, heuristics rules, generator file output, server endpoints
- Mocked API calls in `test_summarizer.py` — never hit real API in tests
- Mocked pipeline in `test_server.py` — server tests must not call real parsers or API
- No new **core** runtime dependencies — `click`, `anthropic`, `jinja2` only

## Key Commands
- Run tests: `pytest tests/ -v --cov=handover --cov-fail-under=80`
- Install locally: `pip install -e .`
- Run CLI: `handover --help`
- Start local bridge: `handover serve`
- Build extension zip: `bash scripts/build-extension.sh`

## Directory Guide (Phase 3 additions)
```
handover/server.py          — HTTP bridge (GET /health, POST /handover, POST /config)
handover/__main__.py        — enables python -m handover for daemon subprocess
extension/
  manifest.json             — Chrome/Firefox MV3 manifest
  background.js             — service worker, POSTs to localhost:7437
  content/claude.js         — DOM extractor for claude.ai
  content/chatgpt.js        — DOM extractor for chat.openai.com
  popup/                    — extension popup UI (HTML + JS + CSS)
scripts/build-extension.sh  — packages extension/ into dist/handover-extension.zip
docs/browser-extension.md   — user guide for installing and using the extension
```
