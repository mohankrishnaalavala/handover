# Reverse Handover — Claude Code Session → HANDOVER.md

The reverse handover pipeline reads a Claude Code session log and produces a
`HANDOVER.md` file that captures what was accomplished, what changed, decisions
made, and the recommended next steps — so a future agent or human can resume
immediately without re-reading the session.

---

## The problem it solves

When a Claude Code session ends (context limit, network drop, or just quitting),
the context is gone. The reverse pipeline captures it before it disappears.

```
Claude Code session ends
       │
       ▼
~/.claude/projects/<hash>/<session-id>.jsonl
       │
       ▼
handover reverse --project .
       │
  parse + extract + summarize
       │
       ▼
HANDOVER.md  ←  ready for the next session or a teammate
```

---

## Quick start

```bash
# Generate HANDOVER.md from the most recent session in the current project
handover reverse --project .

# Use a specific session file
handover reverse --session ~/.claude/projects/-Users-alice-myapp/abc123.jsonl

# Offline mode — no API key needed
handover reverse --project . --no-llm

# Preview without writing
handover reverse --project . --dry-run
```

---

## Output: HANDOVER.md

```markdown
# Session Handover — myapp

Generated: 2026-04-05T10:15:00Z | Session: `abc12345`
Branch: `feature/api` | Started: 2026-04-05

## What Was Accomplished
- Created: `src/auth.py`
- Modified: `src/main.py`

## Files Changed
| File | Action |
|------|--------|
| `src/auth.py` | created |
| `src/main.py` | modified |

## Tasks (matched from PLAN.md)
- [x] Implement JWT auth
- [ ] Add PostgreSQL ← high priority

## Decisions Made During Implementation
- Chose PyJWT over python-jose (simpler API, fewer deps)
- Used async handlers rather than sync (high concurrency expected)

## Where the Session Ended
**Last action:** Bash: pytest tests/
**Context used:** ~8%

## Recommended Next Steps
1. Complete: Add PostgreSQL
2. Complete: Write integration tests
```

---

## Commands

### `handover reverse`

```
handover reverse [OPTIONS]

Options:
  --session PATH    Path to a specific .jsonl session file
  --project, -p PATH  Project root (auto-discovers most recent session)
  --output, -o PATH   Where to write HANDOVER.md (default: project dir)
  --no-llm          Use heuristics only (no API key required)
  --dry-run         Preview without writing
```

### `handover sessions`

List all Claude Code sessions for a project.

```bash
handover sessions
handover sessions --project ~/projects/myapp --limit 20
```

Output:
```
Claude Code sessions for myapp/

SESSION ID                              DATE          BRANCH                    MSGS
------------------------------------------------------------------------------------------
3e90bfe7-e9fa-439d-8e0c-71a50cef09a7  2026-04-05    feature/phase-2-adapters  184
559138f9-ace7-424f-8647-006fb0c0ce04  2026-04-05    main                      4

2 of 2 session(s) shown.
```

### `handover watch`

Auto-generate `HANDOVER.md` whenever a session file stops growing.

```bash
# Install optional dependency first
pip install handover[watch]

# Watch in foreground
handover watch --project .

# Watch in background (daemon)
handover watch --project . --daemon
handover watch --project . --no-llm --idle 30 --daemon
```

The watch command monitors `~/.claude/projects/<hash>/` for `.jsonl` files.
When a file has been idle for `--idle` seconds (default: 60), it triggers
the reverse pipeline automatically.

**Daemon mode** writes to `~/.handover/watch.log` and `~/.handover/watch.pid`.

---

## Session format

Claude Code stores sessions at:
```
~/.claude/projects/<project-hash>/<session-id>.jsonl
```

The `<project-hash>` is derived by replacing every `/` in the absolute project
path with `-`:
```
/Users/alice/projects/myapp  →  -Users-alice-projects-myapp
```

Each line in the `.jsonl` file is a JSON record.  The relevant types are:

| type | contents |
|------|----------|
| `user` | Human message or tool result |
| `assistant` | Claude response with optional `tool_use` blocks |
| `queue-operation` | Internal housekeeping — skipped |
| `file-history-snapshot` | File backup — skipped |

---

## How tasks are matched

If a `PLAN.md` exists in the project directory, the reverse pipeline attempts
to match tasks to session activity:

- A task is marked **completed** if a significant word from its title appears in
  the path of a file that was edited during the session.
- This is a heuristic — use `--no-llm` if you only want structural extraction,
  or let the LLM do a more accurate job.

---

## Dependency note

The `handover watch` command requires the optional `watchdog` package:

```bash
pip install handover[watch]
```

All other reverse-handover features (`reverse`, `sessions`) work without it.
