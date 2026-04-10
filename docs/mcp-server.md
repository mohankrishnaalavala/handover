# MCP server — four tools

The `handover mcp` subcommand starts an MCP (Model Context Protocol) server
that exposes `handover` to any MCP-compatible client (Claude Code, MCP
inspector, etc.). Since v1.1.1 the server exposes **four** tools.

## Setup

```bash
pip install handover[mcp]
```

`~/.claude/mcp.json`:

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

Restart Claude Code. The four tools below appear under the "handover" server.

## Tools at a glance

| Tool | Purpose | When you'd use it from chat |
|---|---|---|
| `run_handover` | Parse a chat export, write `.handover/` + `.claude/` | "Bootstrap a project from this export" |
| `handover_status` | Read `backlog.json`, report progress | "Where are we on this project?" |
| `handover_reverse` | Summarise the latest Claude Code session | "What did the agent just do?" |
| `handover_list` | List conversations in an export file | "What's in this Claude export?" |

## Tool reference

### `run_handover`

Parse an AI chat export and generate agent context files.

| Param | Type | Default | Description |
|---|---|---|---|
| `input_file` | string | — | Path to a chat export (`.json`, `.jsonl`, `.md`) |
| `output_dir` | string | `"."` | Where to write the workspace |
| `source` | string | `"auto"` | `claude` / `chatgpt` / `gemini` / `perplexity` / `auto` |
| `target` | string | `"claude-code"` | `claude-code` / `codex` / `aider` / `goose` / `copilot` / `all` |
| `no_llm` | bool | `false` | Skip the Claude API call (heuristic-only) |

**Example response (v1.1.1):**

```
Generated CLAUDE.md, PLAN.md in /Users/me/water-tracker/
  .handover/: context, prompts, standards, work
  .claude/: 3 agents, 2 skills, 3 commands, 1 hook
Goal: Build a water intake tracker webapp
Tasks: 10  Decisions: 7  Tech stack: FastAPI, React, PostgreSQL
```

### `handover_status`

Read `.handover/work/backlog.json` and return a progress summary.

| Param | Type | Default | Description |
|---|---|---|---|
| `project_dir` | string | `"."` | Project root containing `.handover/work/backlog.json` |

**Why `backlog.json` and not `tasks.md`:** the JSON file has machine-readable
task IDs, `done` flags, priorities, and ISO timestamps. Parsing markdown
checkboxes is fragile and loses metadata.

**Example chat prompt:**

> "Use handover_status on my water-tracker project — what's left?"

**Example response:**

```
Project: water-intake-tracker
Progress: 3/10 tasks complete

High priority remaining:
  • Implement JWT middleware
  • Define PostgreSQL schema

Next task: Implement JWT middleware
Last completed: Set up FastAPI scaffold
  at 2026-04-08

Full task list: /Users/me/water-tracker/.handover/work/backlog.json
```

If `.handover/work/backlog.json` does not exist:

```
No backlog.json found in /Users/me/water-tracker/.handover/work/. Run handover first.
```

### `handover_reverse`

Summarise the most recent Claude Code session for a project. Wraps the
existing `handover reverse` orchestrator.

| Param | Type | Default | Description |
|---|---|---|---|
| `project_dir` | string | `"."` | Project root. Used to discover the most recent session |
| `output_dir` | string | `""` | Where to write `HANDOVER.md`. Empty = same as `project_dir` |
| `no_llm` | bool | `false` | Use heuristics only (no API cost) |

Auto-discovers the latest session from
`~/.claude/projects/<project-hash>/*.jsonl`.

**Example chat prompt:**

> "Run handover_reverse on this project and tell me what the agent did."

**Example response:**

```
Session: 7f3e2a91  Branch: feature/auth
Files changed: 4
Commands run: 12

Key decisions made:
  • Chose pyjwt over python-jose for token signing
  • Used Depends() for the middleware injection point

Recommended next steps:
  Add integration test for token expiry
  Document the env vars in README

Full summary written to: /Users/me/water-tracker/HANDOVER.md
```

If no sessions are found for the project:

```
No Claude Code sessions found for /Users/me/water-tracker. Run a Claude Code session first.
```

### `handover_list`

List conversations inside a chat export file. Useful when an export contains
many threads and you want to pick one before calling `run_handover`.

| Param | Type | Default | Description |
|---|---|---|---|
| `input_file` | string | — | Path to a chat export (`.json` or `.jsonl`) |

Output is capped at 20 rows; longer exports show a "... and N more" tail.

**Example chat prompt:**

> "List the conversations in ~/Downloads/conversations.json"

**Example response:**

```
Found 27 conversation(s) in conversations.json:

  bulk-conv-00  2026-04-01  API Design Discussion
  bulk-conv-00  2026-03-28  Database Schema Planning
  bulk-conv-00  2026-03-25  Auth Strategy
  ...
  ... and 7 more

Use run_handover with id= or title= to generate workspace.
```

## Implementation notes

Every `@mcp.tool()` wrapper in `handover/mcp_server.py` delegates to a plain
`*_impl` function (`run_handover_impl`, `handover_status_impl`,
`handover_reverse_impl`, `handover_list_impl`). This is intentional: the impls
have no dependency on the MCP SDK, so they are unit-testable in
[tests/test_mcp_server.py](../tests/test_mcp_server.py) without installing
`handover[mcp]`.

When adding a fifth tool, follow the same pattern:

1. Add `<tool>_impl(...) -> str` to `handover/mcp_server.py`.
2. Add a `@mcp.tool()`-decorated wrapper inside `main()` that calls the impl.
3. Add direct unit tests against the impl in `tests/test_mcp_server.py`.
4. Document it in this file and update the table in [README.md](../README.md).
