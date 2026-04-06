# handover

> *Design in chat. Build in terminal. Zero context lost.*

`handover` is an open-source CLI tool that bridges AI chat interfaces (Claude, ChatGPT, Gemini, and others) to local terminal coding agents (Claude Code, Codex CLI, Aider, Goose, etc.). It extracts decisions, plans, and intent from a chat conversation and generates structured handover artifacts that a local agent can immediately act on — without re-explaining anything.

[![PyPI version](https://img.shields.io/pypi/v/handover.svg)](https://pypi.org/project/handover/)
[![Python versions](https://img.shields.io/pypi/pyversions/handover.svg)](https://pypi.org/project/handover/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/mohankrishnaalavala/handover/actions/workflows/ci.yml/badge.svg)](https://github.com/mohankrishnaalavala/handover/actions/workflows/ci.yml)

---

## Install

```bash
pip install handover
```

Optional extras:

```bash
pip install handover[watch]   # enables: handover watch (session file monitoring)
pip install handover[mcp]     # enables: handover mcp (MCP server for Claude Code)
```

---

## Quickstart

```bash
# Basic usage — single conversation file
handover --input conversation.json --output ./my-project/

# List all conversations in a bulk export
handover list export.jsonl

# Bulk export — select a specific conversation by title
handover --input export.jsonl --title "API Design Discussion" --output ./my-project/
```

---

## `--dry-run` Demo

```
$ handover --input chat.json --output ./my-project/ --no-llm --dry-run

Parsing: 'API Design Discussion'
  Source : claude (single-json v1.0)
  Messages: 34

Extracted:
  Goal       : Build a FastAPI REST API with JWT auth and PostgreSQL
  Tech Stack : Python, FastAPI, PostgreSQL, pytest
  Decisions  : 2
  Tasks      : 6
  Constraints: 2
  Questions  : 1

Target: claude-code  |  Would write to ./my-project/:
  -> CLAUDE.md
  -> PLAN.md

Run without --dry-run to write files.
```

---

## Supported Input Formats

| Source | Format | How to Export |
|--------|--------|---------------|
| Claude.ai bulk export | `.jsonl` | Settings → Privacy → Export Data |
| Claude.ai single chat | `.json` / `.md` | Claude Conversation Exporter browser extension |
| ChatGPT | `.json` | Settings → Data Controls → Export Data |
| Gemini | `.json` | Google Takeout → Gemini Apps Activity |
| Perplexity | `.json` | Settings → Account → Export Data |

---

## Output Targets

| Target | Generated Files | Agent |
|--------|----------------|-------|
| `claude-code` (default) | `CLAUDE.md` + `PLAN.md` | Claude Code |
| `codex` | `AGENTS.md` | Codex CLI |
| `aider` | `.aider.conf.yml` | Aider |
| `goose` | `goose-context.json` | Goose |
| `all` | All of the above | All agents |

```bash
handover --input chat.json --output ./my-project/ --target codex
handover --input chat.json --output ./my-project/ --target all
```

---

## CLI Reference

### Chat export → agent context

```bash
handover --input <file> --output <dir> [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--input, -i` | required | Chat export file (`.json`, `.jsonl`, `.md`) |
| `--output, -o` | required | Directory to write output files |
| `--source` | auto | Force parser: `claude`, `chatgpt`, `gemini`, `perplexity` |
| `--title` | — | Select conversation by title (substring match, for bulk exports) |
| `--id` | — | Select conversation by ID (for bulk exports) |
| `--target` | `claude-code` | Output format: `claude-code`, `codex`, `aider`, `goose`, `all` |
| `--no-llm` | off | Rule-based extraction only — no API key required |
| `--dry-run` | off | Preview what would be written, without writing |
| `--launch` | off | Run `claude` in output directory after writing |
| `--template` | — | Path to custom Jinja2 templates directory (claude-code target only) |
| `--publish` | off | Publish generated artifacts to GitHub Gist after writing (requires `gh` CLI) |

### Explore exports

```bash
handover list <export_file>            # list all conversations in a bulk export
handover list export.jsonl --source claude
```

### Scaffold custom templates

```bash
handover init       # copies default templates to ~/.handover/templates/ for editing
```

### Reverse handover — Claude Code session → `HANDOVER.md`

Generates `HANDOVER.md` from Claude Code session logs: what was accomplished, files changed, decisions made, and recommended next steps.

```bash
handover reverse --project .                          # auto-discover latest session
handover reverse --session ~/.claude/projects/…/abc.jsonl
handover reverse --project . --no-llm --dry-run

handover sessions                                     # list recent Claude Code sessions
handover sessions --project ~/my-app --limit 20

handover watch --project .                            # auto-generate when session goes idle
handover watch --project . --idle 30 --daemon         # background mode
# requires: pip install handover[watch]
```

### Local bridge for browser extension

Starts an HTTP server that the Chrome/Firefox extension uses to send conversations directly from the browser.

```bash
handover serve                                   # port 7437 (H-A-N-D on phone keypad)
handover serve --port 7437 --output ~/my-app/
handover serve --no-llm --daemon                 # background mode
```

Endpoints: `GET /health`, `POST /handover`, `POST /config`  
See [docs/browser-extension.md](docs/browser-extension.md) for extension setup.

### History & re-run

Every successful non-dry-run invocation is logged to `~/.handover/history.jsonl`.

```bash
handover history                          # last 20 runs
handover history --limit 50
handover history --project ~/my-app/     # filter by output directory

handover rerun h_4a2955ab                # re-run a past handover by ID
```

### Merge multiple exports

Combine two or more chat sessions into one unified `CLAUDE.md` + `PLAN.md`. Deduplicates tasks and decisions automatically.

```bash
handover merge --input session1.json --input session2.json --output ./my-project/
handover merge --input s1.json --input s2.json --output . --no-llm --target all
```

### Share via GitHub Gist

```bash
# Publish after generating (requires gh CLI authenticated)
handover --input chat.json --output ./my-project/ --publish

# Pull shared handover artifacts
handover pull https://gist.github.com/user/abc123
handover pull abc123 --output ./my-project/
```

### MCP server for Claude Code

Exposes `handover` as an MCP tool so Claude Code can call it directly.

```bash
handover mcp
# requires: pip install handover[mcp]
```

Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "handover": {
      "command": "handover",
      "args": ["mcp"],
      "env": { "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}" }
    }
  }
}
```

---

## Roadmap

| Version | Phase | What ships | Status |
|---------|-------|-----------|--------|
| v0.2.0 | 1 + 2 | Claude, ChatGPT, Gemini, Perplexity → Claude Code | ✅ Released |
| v0.3.0–v0.4.0 | 3 + 4 | `handover serve` + browser extension; reverse handover (`handover reverse`, `handover sessions`, `handover watch`) | ✅ Released |
| v0.5.0 | 5 | Multi-target: Codex CLI, Aider, Goose; `--target all` | ✅ Released |
| v1.0.0 | 6 | MCP server, `handover history`, `handover merge`, Gist publish/pull | ✅ Released |
| — | — | VS Code extension, GitHub Action | Coming soon |

---

## Contributing

The primary contribution path is adding a new source adapter or output target. Each adapter is an isolated Python class anyone can own end-to-end.

- [docs/adding-an-adapter.md](docs/adding-an-adapter.md) — add a new chat source (e.g. Mistral, Grok)
- [docs/adding-a-target.md](docs/adding-a-target.md) — add a new agent target
- [CONTRIBUTING.md](CONTRIBUTING.md) — general contribution guidelines

---

## License

MIT © 2026 Mohan Krishnaa Alavala
