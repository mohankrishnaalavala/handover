# Manual Test Report — Phase 6 Ecosystem & Developer Experience

**Date:** 2026-04-06  
**handover version:** 1.0.0  
**Input file:** `handover-chat-271350a4-7ef0-4c23-8cd2-940b8454898e.json`  
**Conversation:** "Water intake tracking webapp plan"  

---

## Results Summary

**10 / 10 passed**

| # | Command | Exit | Files Created | Status | Notes |
|---|---------|------|---------------|--------|-------|
| a | `handover --input … --output out/ --no-llm` | 0 | CLAUDE.md, PLAN.md | ✅ PASS | |
| b | `handover --input … --output dry/ --no-llm --dry-run` | 0 | (none) | ✅ PASS | Prints "Would write" lines, no files written |
| c | `handover --input … --output out-all/ --no-llm --target all` | 0 | CLAUDE.md, PLAN.md, AGENTS.md, .aider.conf.yml, goose-context.json | ✅ PASS | |
| d | `handover --input … --output out-codex/ --no-llm --target codex` | 0 | AGENTS.md | ✅ PASS | |
| e | `handover --input … --output out-aider/ --no-llm --target aider` | 0 | .aider.conf.yml (hidden) | ✅ PASS | Hidden file not shown by ls |
| f | `handover --input … --output out-goose/ --no-llm --target goose` | 0 | goose-context.json | ✅ PASS | |
| g | `handover history` | 0 | — | ✅ PASS | Shows 20 entries including all test runs |
| h | `handover merge --input … --input … --output merged/ --no-llm` | 0 | CLAUDE.md, PLAN.md | ✅ PASS | Deduplicates 6 tasks → 6 (same file twice) |
| i | `handover mcp --help` | 0 | — | ✅ PASS | Shows install hint + MCP config snippet |
| j | `handover pull --help` | 0 | — | ✅ PASS | Shows usage with URL and --output option |

---

## Command Outputs

### a. Basic claude-code target

```
$ handover --input manual_test/handover-chat-271350a4-7ef0-4c23-8cd2-940b8454898e.json \
    --output manual_test/out/ --no-llm
Wrote CLAUDE.md, PLAN.md to manual_test/out/
History: h_4a2955ab
```

### b. Dry run

```
$ handover --input … --output manual_test/dry/ --no-llm --dry-run

Parsing: 'Water intake tracking webapp plan'
  Source : claude (single-json v1.0)
  Messages: 2

Extracted:
  Goal       : One a webapp to remind the water intake and track my water consumption, can you give me plan for this
  Tech Stack : Python, React, SQLite, Claude
  Decisions  : 3
  Tasks      : 6
  Constraints: 1
  Questions  : 1

Target: claude-code  |  Would write to manual_test/dry/:
  -> CLAUDE.md
  -> PLAN.md

Run without --dry-run to write files.
```

### c. All targets

```
$ handover --input … --output manual_test/out-all/ --no-llm --target all
Wrote CLAUDE.md, PLAN.md, AGENTS.md, .aider.conf.yml, goose-context.json to manual_test/out-all/
History: h_b7dbecfe
```

### d. Codex target

```
$ handover --input … --output manual_test/out-codex/ --no-llm --target codex
Wrote AGENTS.md to manual_test/out-codex/
History: h_4809094d
```

### e. Aider target

```
$ handover --input … --output manual_test/out-aider/ --no-llm --target aider
Wrote .aider.conf.yml to manual_test/out-aider/
History: h_7c178e23
```

### f. Goose target

```
$ handover --input … --output manual_test/out-goose/ --no-llm --target goose
Wrote goose-context.json to manual_test/out-goose/
History: h_af4be6b8
```

### g. History list

```
$ handover history

ID            DATE          SOURCE        TARGET          TITLE
------------------------------------------------------------------------------------------
h_af4be6b8    2026-04-06    claude        goose           Water intake tracking webapp plan
h_7c178e23    2026-04-06    claude        aider           Water intake tracking webapp plan
h_4809094d    2026-04-06    claude        codex           Water intake tracking webapp plan
h_b7dbecfe    2026-04-06    claude        all             Water intake tracking webapp plan
h_4a2955ab    2026-04-06    claude        claude-code     Water intake tracking webapp plan
...
20 entry(s) shown.
```

### h. Merge (two inputs, no-llm)

```
$ handover merge --input … --input … --output manual_test/merged/ --no-llm
Merging 2 conversations…
Wrote CLAUDE.md, PLAN.md to manual_test/merged/
Merged goal: One a webapp to remind the water intake and track my water consumption, can you give me plan for this
```

### i. MCP help

```
$ handover mcp --help
Usage: handover mcp [OPTIONS]

  Start the MCP server so Claude Code can call handover as a tool.

  Requires the optional [mcp] dependency:   pip install handover[mcp]
  ...

Options:
  --help  Show this message and exit.
```

### j. Pull help

```
$ handover pull --help
Usage: handover pull [OPTIONS] GIST_URL

  Pull a shared handover from a GitHub Gist URL.
  ...

Options:
  -o, --output PATH  Directory to write downloaded files (default: cwd)
  --help             Show this message and exit.
```

---

## Notes

- `--publish` flag requires `gh` CLI authenticated — not tested here (would make real network calls)
- `handover rerun <id>` not tested directly (re-runs the pipeline, covered by test suite)
- LLM mode (`--no-llm` not set) would call Claude API — skipped to avoid API cost in manual run
- All 349 automated tests pass with 83% coverage
