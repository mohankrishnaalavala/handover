# handover — Universal AI Chat to Local Agent Handover Tool

## Project Goal
CLI tool that parses AI chat exports and generates CLAUDE.md + PLAN.md
artifacts for local terminal agents to ingest.

**Current state:** v1.1.0 — Two-Layer Scaffold (`.handover/` + `.claude/`) shipping on top of Phases 1–6.
**Active branch:** `feature/v1.1.0-two-layer-scaffold`.

## Tech Stack
- Language: Python 3.11+
- CLI: Click (subcommands: main, list, init, serve)
- Templates: Jinja2
- API: Anthropic SDK (claude-sonnet-4-6 for summarization)
- HTTP server: stdlib `http.server` + `socketserver.ThreadingMixIn` (no Flask)
- File watcher: `watchdog>=4.0` (optional, `[watch]` extra)
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
- **Phase 4:** Session logs live at `~/.claude/projects/<hash>/<session-id>.jsonl`. The project hash is the absolute path with all `/` and `_` replaced by `-`.
- **Phase 4:** `reverse.py` orchestrates: parse → extract file changes + commands → match PLAN.md tasks → LLM/heuristic decisions + next steps → `Generator.generate_handover()`.
- **Phase 4:** `watcher.py` uses `watchdog` with a debounce timer (default 60 s). Requires `pip install handover[watch]`. Never import `watchdog` at module level — import lazily inside `start_watching()` so the rest of the package works without the optional dep.
- **Phase 5:** Target adapters live in `handover/targets/`. Each target subclasses `BaseTarget` (in `targets/base.py`) and registers in `TARGET_REGISTRY` in `targets/__init__.py`. Mirrors the source adapter pattern in `parsers/`.
- **Phase 5:** `ClaudeCodeTarget` delegates to `Generator` — do not duplicate Jinja2 rendering logic in targets.
- **Phase 5:** `--target all` iterates `list_targets()` — every registered target generates output into the same `--output` directory.
- **Phase 5:** Non-claude-code targets (codex, aider, goose) use stdlib only — no new core dependencies. Write YAML/JSON via string templates or `json.dumps()`.
- **Phase 6:** `handover/history.py` writes one JSON line per run to `~/.handover/history.jsonl` after every successful non-dry-run `handover` invocation.
- **Phase 6:** `handover/merger.py` combines multiple HandoverContext objects. No-LLM mode uses heuristic deduplication; LLM mode calls `summarizer.merge_contexts_with_llm()`.
- **Phase 6:** `handover/publisher.py` uses `gh gist create` subprocess — requires `gh` CLI authenticated. No new core Python dependency.
- **Phase 6:** `handover/mcp_server.py` uses `FastMCP` from `mcp>=1.0` (optional `[mcp]` extra). Import `mcp` only inside `mcp_server.py`; the CLI subcommand catches ImportError.
- **Phase 6:** New CLI subcommands: `mcp`, `history`, `rerun`, `merge`, `pull`. New flag: `--publish` on main command.
- **v1.1.0:** Two-Layer Scaffold pipeline is `parse → summarize → scaffold_extractor → universal_generator(.handover/) → target_generator(thin agent files)`.
- **v1.1.0:** `handover/scaffold_extractor.py` makes one Claude API call for the 13 markdown bodies in `.handover/` and walks `DOMAIN_RULES` for domain detection. `--no-llm` falls back to `handover/scaffold_heuristics.py` (pure functions, no I/O).
- **v1.1.0:** `handover/universal_generator.py` writes `.handover/` from the `HANDOVER_DIR_FILES` registry — adding a new file is one row plus a `.j2` template under `handover/templates/handover/`.
- **v1.1.0:** `handover/scaffold_generator.py` writes the per-target `.claude/` workspace (only `claude-code` uses it). Hook scripts are chmod'd 0o755 on write.
- **v1.1.0:** `ClaudeCodeTarget` switches between the legacy `claude_md.j2` (single-layer) and the thin `claude_md_v2.j2` index based on whether a `ScaffoldContext` is passed in. Targets never import scaffold logic directly — they consume `ScaffoldContext` via constructor injection.
- **v1.1.0:** `ScaffoldContext` (in `models.py`) is the single carrier object — plain data only, no Jinja2 or filesystem reach. `schema_version` is bumped on breaking field changes.
- **v1.1.0:** New CLI flags on the main command: `--no-handover-dir`, `--handover-dir-only`, `--overwrite-handover-dir`. New `POST /config` field on the server: `no_handover_dir`.

## Coding Standards
- Type hints on all functions and methods
- Docstrings on all public methods
- Tests required for: parser output, heuristics rules, generator file output, server endpoints
- Mocked API calls in `test_summarizer.py` — never hit real API in tests
- Mocked pipeline in `test_server.py` — server tests must not call real parsers or API
- Mocked LLM in `test_reverse.py` — reverse tests must not call real API
- No new **core** runtime dependencies — `click`, `anthropic`, `jinja2` only
- Optional deps go in `pyproject.toml` extras: `watchdog` in `[watch]`

## Key Commands
- Run tests: `pytest tests/ -v --cov=handover --cov-fail-under=80`
- Install locally: `pip install -e .`
- Run CLI: `handover --help`
- Start local bridge: `handover serve`
- Build extension zip: `bash scripts/build-extension.sh`
- Generate HANDOVER.md: `handover reverse --project .`
- List sessions: `handover sessions`
- Watch sessions: `handover watch --project .`  (requires `pip install handover[watch]`)

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

## Directory Guide (v1.1.0 additions)
```
handover/scaffold_extractor.py    — LLM call for .handover/ + DOMAIN_RULES registry
handover/scaffold_heuristics.py   — pure-function --no-llm fallback
handover/universal_generator.py   — writes .handover/ via HANDOVER_DIR_FILES registry
handover/scaffold_generator.py    — writes .claude/ workspace (claude-code target only)
handover/templates/handover/      — 20 Jinja2 templates for .handover/ files
handover/templates/claude_md_v2.j2 — thin CLAUDE.md index (used in two-layer mode)
handover/templates/{agent,skill,command,hook_pre_tool_use,settings_json}.j2
docs/handover-directory.md        — user guide to the two-layer layout
```
