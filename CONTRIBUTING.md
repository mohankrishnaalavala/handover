# Contributing to handover

Thank you for your interest in contributing! `handover` is a v1.0.0 open-source project and contributions are welcome across all layers.

## Setup

```bash
git clone https://github.com/mohankrishnaalavala/handover.git
cd handover
pip install -e ".[dev,watch]"
```

Optional extras for full feature coverage:

```bash
pip install -e ".[dev,watch,mcp]"
```

## Running Tests

```bash
pytest tests/ -v --cov=handover --cov-report=term-missing --cov-fail-under=80
```

All tests must pass and coverage must stay above 80% before a PR can merge.

## Linting

```bash
ruff check handover/ tests/
ruff format --check handover/ tests/
mypy handover/
```

---

## Contribution Paths

### 1. New source adapter (parser)

Adding a new chat source is the most isolated, self-contained contribution. Each adapter is one file in `handover/parsers/`.

See **[docs/adding-an-adapter.md](docs/adding-an-adapter.md)** for the complete guide.

In brief:
1. Create `handover/parsers/{source}.py` — subclass `BaseParser`
2. Register in `handover/parsers/__init__.py`
3. Add a test fixture in `tests/fixtures/`
4. Add tests in `tests/test_parser.py`
5. Update the supported formats table in `README.md`
6. Add the source name to the `--source` flag help text in `handover/cli.py`

### 2. New output target

Adding a new agent target (e.g., a new coding agent format) mirrors the parser adapter pattern.

See **[docs/adding-a-target.md](docs/adding-a-target.md)** for the complete guide.

In brief:
1. Create `handover/targets/{name}.py` — subclass `BaseTarget`
2. Register in `handover/targets/__init__.py`
3. Add tests in `tests/test_targets.py`
4. Update the targets table in `README.md`

### 3. Browser extension

The extension lives in `extension/`. It is a Chrome/Firefox MV3 extension with:
- `background.js` — service worker (fetch, download, server POST)
- `content/claude.js` — DOM/API extraction for claude.ai
- `content/chatgpt.js` — DOM extraction for chat.openai.com and chatgpt.com
- `popup/` — extension UI

Good contribution areas:
- New content scripts for additional sites (e.g., Gemini, Perplexity)
- UX improvements in the popup
- Bug fixes in the extraction logic

Build the distributable zip: `bash scripts/build-extension.sh`

### 4. MCP server

The MCP server lives in `handover/mcp_server.py`. It exposes a single `run_handover` tool via FastMCP.

Contributions:
- Additional MCP tools (e.g., `list_history`, `run_merge`)
- Schema improvements for better Claude Code integration

Requires `pip install handover[mcp]`.

### 5. Docs and DX

Improving guides, fixing inaccuracies, and adding examples are high-value contributions:
- `docs/` — guides for users and contributors
- `README.md` — primary user-facing doc
- `CHANGELOG.md` — keep entries accurate and linked

### 6. Bug fixes

Check open issues on GitHub. Good labels to look for: `bug`, `good first issue`.

---

## Code Standards

- **Type hints** on all functions and methods
- **Docstrings** on all public methods
- **Tests required** for any changed behavior
- Mocked API calls in tests — never hit the real Anthropic API in tests
- No new **core** runtime dependencies (`click`, `anthropic`, `jinja2` only)
- Optional deps go in `pyproject.toml` extras

## Submitting a Pull Request

1. Fork the repo and create a feature branch from `main`
2. Make your changes with tests
3. Run the full test suite and lint — everything must pass
4. Open a PR against `main` with a clear description of what changed and why

---

## Current State (v1.0.1)

All planned phases are shipped:
- Phases 1–2: Claude, ChatGPT, Gemini, Perplexity → CLAUDE.md + PLAN.md
- Phase 3: `handover serve` HTTP bridge + browser extension (claude.ai, chatgpt.com)
- Phase 4: `handover reverse` — Claude Code session → HANDOVER.md
- Phase 5: Multi-target output (Codex CLI, Aider, Goose)
- Phase 6: MCP server, `handover history`, `handover merge`, Gist publish/pull

The primary open contribution opportunities are new source adapters, new target adapters, new browser extension content scripts, and MCP tool additions.
