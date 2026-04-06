# handover

> *Design in chat. Build in terminal. Zero context lost.*

`handover` is an open-source CLI tool that bridges AI chat interfaces (Claude, ChatGPT, Gemini, and others) to local terminal coding agents (Claude Code, Codex CLI, etc.). It extracts decisions, plans, and intent from a chat conversation and generates structured handover artifacts that a local agent can immediately act on — without re-explaining anything.

[![PyPI version](https://img.shields.io/pypi/v/handover.svg)](https://pypi.org/project/handover/)
[![Python versions](https://img.shields.io/pypi/pyversions/handover.svg)](https://pypi.org/project/handover/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/mohankrishnaalavala/handover/actions/workflows/ci.yml/badge.svg)](https://github.com/mohankrishnaalavala/handover/actions/workflows/ci.yml)

---

## Install

```bash
pip install handover
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

## Supported Input Formats

| Source | Format | How to Export |
|--------|--------|---------------|
| Claude.ai bulk export | `.jsonl` | Settings → Privacy → Export Data |
| Claude.ai single chat | `.json` / `.md` | Claude Conversation Exporter browser extension |
| ChatGPT | `.json` | Settings → Data Controls → Export Data |
| Gemini | `.json` | Google Takeout → Gemini Apps Activity |
| Perplexity | `.json` | Settings → Account → Export Data |

---

## All Flags

```bash
handover --input chat.json --output ./my-project/ --source claude   # explicit adapter
handover --input chat.json --output ./my-project/ --dry-run         # print, don't write
handover --input chat.json --output ./my-project/ --no-llm          # rule-based only, no API key needed
handover --input chat.json --output ./my-project/ --launch          # run `claude` after writing
handover --input chat.json --output ./my-project/ --template ~/.handover/templates/

handover list export.jsonl                  # enumerate conversations in bulk export
handover init                               # scaffold customizable templates to ~/.handover/
```

---

## Roadmap

| Version | Phase | What ships |
|---------|-------|------------|
| v0.2.0 | 1 + 2 | Claude, ChatGPT, Gemini, Perplexity → Claude Code | ✅ Released |
| v0.3.0 | 3 | `handover serve` local bridge + Chrome/Firefox extension | In development |
| v0.4.0 | 4 | Reverse handover — Claude Code sessions → `HANDOVER.md` | Planned |
| v0.5.0 | 5 | Multi-target: Codex CLI, Aider, Goose | Planned |
| v1.0.0 | 6 | MCP server, VS Code extension, `handover history`, `handover merge` | Future |

---

## Contributing

The primary contribution path is adding a new source adapter. Each adapter is an isolated Python class anyone can own end-to-end. See [docs/adding-an-adapter.md](docs/adding-an-adapter.md) for the step-by-step guide.

For general contribution guidelines, see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT © 2026 Mohan Krishnaa Alavala
