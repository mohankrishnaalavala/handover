# Getting Started with handover

## Installation

```bash
pip install handover-cli
```

Verify the install:

```bash
handover --help
```

## Quick Start

### Step 1: Export your Claude chat

**Single conversation (recommended for one project):**
Install the [Claude Conversation Exporter](https://chromewebstore.google.com/detail/claude-conversation-expor) browser extension and export your conversation as `.json`.

**Bulk export (all your conversations):**
Go to Claude Settings → Privacy → Export Data. You'll receive a `.jsonl` file.

### Step 2: Run handover

```bash
# For a single conversation export
handover --input conversation.json --output ./my-project/

# For a bulk export — use --title to pick the right conversation
handover list export.jsonl                                              # see all conversations
handover --input export.jsonl --title "API Design" --output ./my-project/
```

### Step 3: Open the output directory in Claude Code

```bash
cd my-project
claude
```

Claude Code will automatically read `CLAUDE.md` at session start and have full context of your design decisions, tech stack, tasks, and constraints.

## Flags Reference

| Flag | Description |
|------|-------------|
| `--input` | Path to the chat export file (required) |
| `--output` | Directory to write output files (required) |
| `--source` | Force a specific adapter: `claude` (auto-detected by default) |
| `--dry-run` | Preview what would be written without writing files |
| `--no-llm` | Use rule-based extraction only — no Anthropic API key needed |
| `--launch` | Run `claude` in the output directory after writing files |
| `--title` | Select a conversation by title from a bulk JSONL export |
| `--id` | Select a conversation by ID from a bulk JSONL export |
| `--template` | Path to custom Jinja2 templates directory |

## Using `--no-llm` Mode

If you don't have an Anthropic API key or want offline operation:

```bash
handover --input chat.json --output ./my-project/ --no-llm
```

This uses rule-based heuristics (keyword matching) instead of the Claude API. Results are slightly less polished but require no API key and work completely offline. See PRD Section 8 for the full heuristics spec.

## Customizing Output Templates

```bash
handover init
```

This scaffolds editable Jinja2 templates to `~/.handover/templates/`:
- `claude_md.j2` — the `CLAUDE.md` template
- `plan_md.j2` — the `PLAN.md` template

Edit these to match your team's preferred format, then pass `--template ~/.handover/templates/` on each run.
