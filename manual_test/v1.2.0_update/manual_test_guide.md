# handover v1.2.0 — Comprehensive Manual Test Guide

End-to-end testing guide covering **all** handover features.
Run from the project root: `/Users/mohankrishnaalavala/Documents/project_handover`

---

## Prerequisites

```bash
# Install handover in editable mode with all extras
pip install -e ".[dev,watch,mcp]"

# Verify installation
handover --version
# Expected: handover, version 1.2.0

# Ensure ANTHROPIC_API_KEY is set (needed for LLM-mode tests)
source ~/.zshrc
echo $ANTHROPIC_API_KEY
```

---

## A. Core Pipeline (chat export -> agent files)

### A1. Single JSON — no-llm mode

```bash
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-core \
  --no-llm
```

**Verify:**
- [ ] Exit code 0
- [ ] `manual_test/v1.2.0_update/out-core/CLAUDE.md` exists and has project goal
- [ ] `manual_test/v1.2.0_update/out-core/PLAN.md` exists with tasks
- [ ] `.handover/manifest.yaml` exists with `version: 1.2.0`
- [ ] `.handover/context/overview.md` has the goal
- [ ] `.handover/work/backlog.json` has tasks array
- [ ] `.handover/work/tasks.md` has task checkboxes
- [ ] `.handover/codebase/` directory exists (may be empty if no source files)
- [ ] `.claude/` directory exists with agents/, commands/, settings.json

### A2. Dry-run mode

```bash
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-dry \
  --no-llm --dry-run
```

**Verify:**
- [ ] Exit code 0
- [ ] Output mentions `CLAUDE.md`, `.handover/manifest.yaml`
- [ ] `manual_test/v1.2.0_update/out-dry/` directory does NOT exist (nothing written)

### A3. Bulk JSONL — title filter

```bash
handover list tests/fixtures/claude_bulk.jsonl
```

**Verify:**
- [ ] Shows table with ID, TITLE columns
- [ ] Lists 3 conversations
- [ ] Shows "3 conversation(s)"

```bash
handover \
  --input tests/fixtures/claude_bulk.jsonl \
  --title "Auth Strategy" \
  --output manual_test/v1.2.0_update/out-bulk \
  --no-llm
```

**Verify:**
- [ ] Exit code 0
- [ ] `CLAUDE.md` generated with auth-related content

### A4. LLM mode (requires ANTHROPIC_API_KEY)

```bash
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-llm
```

**Verify:**
- [ ] Exit code 0
- [ ] `CLAUDE.md` has richer, more structured content than no-llm
- [ ] `.handover/` has complete content in all files

### A5. Markdown input

```bash
handover \
  --input tests/fixtures/claude_single.md \
  --output manual_test/v1.2.0_update/out-md \
  --no-llm
```

**Verify:**
- [ ] Exit code 0
- [ ] `CLAUDE.md` generated

---

## B. Two-Layer Scaffold Flags

### B1. --no-handover-dir (legacy output only)

```bash
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-nodir \
  --no-llm --no-handover-dir
```

**Verify:**
- [ ] `CLAUDE.md` + `PLAN.md` exist
- [ ] `.handover/` does NOT exist
- [ ] `.claude/` does NOT exist

### B2. --handover-dir-only (no target files)

```bash
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-dironly \
  --no-llm --handover-dir-only
```

**Verify:**
- [ ] `.handover/manifest.yaml` exists
- [ ] `CLAUDE.md` does NOT exist
- [ ] `PLAN.md` does NOT exist

### B3. --overwrite-handover-dir (re-run)

```bash
# First run
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-overwrite \
  --no-llm

# Second run without --overwrite should fail
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-overwrite \
  --no-llm
# Expected: error mentioning .handover already exists

# Third run with --overwrite should succeed
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-overwrite \
  --no-llm --overwrite-handover-dir
```

**Verify:**
- [ ] Second run fails with `.handover` error
- [ ] Third run succeeds (exit code 0)

---

## C. Incremental Update (v1.2.0 NEW)

### C1. Basic update

```bash
# First: create initial .handover/
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-update \
  --no-llm

# Mark a task as done manually
# Edit manual_test/v1.2.0_update/out-update/.handover/work/tasks.md
# Change one "- [ ]" to "- [x]"

# Run update with same input (should detect no new changes but preserve ticks)
handover update \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-update \
  --no-llm
```

**Verify:**
- [ ] Exit code 0
- [ ] `tasks.md` still has the `[x]` mark you added
- [ ] No duplicate tasks appended (same input = no delta)

### C2. Update with new content

```bash
# Use a different fixture to add new tasks/decisions
handover update \
  --input tests/fixtures/claude_bulk.jsonl \
  --title "Auth Strategy" \
  --output manual_test/v1.2.0_update/out-update \
  --no-llm
```

**Verify:**
- [ ] New tasks appended under `## New (added YYYY-MM-DD)` heading
- [ ] Original `[x]` marks preserved
- [ ] New decisions appear as ADR entries continuing existing numbering

### C3. Update dry-run

```bash
handover update \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-update \
  --no-llm --dry-run
```

**Verify:**
- [ ] Shows delta summary (new tasks, decisions, etc.)
- [ ] No files modified

### C4. Update without .handover/ (should fail)

```bash
handover update \
  --input tests/fixtures/claude_single.json \
  --output /tmp/nonexistent-handover-dir \
  --no-llm
```

**Verify:**
- [ ] Non-zero exit code
- [ ] Error mentions missing `.handover/`

---

## D. Multi-Chat Project Grouping (v1.2.0 NEW)

### D1. List with --by-project

```bash
handover list tests/fixtures/claude_bulk.jsonl --by-project
```

**Verify:**
- [ ] Output groups conversations under project headings
- [ ] Each conversation listed with ID and title

### D2. Merge with --project filter

```bash
handover merge \
  --input tests/fixtures/claude_bulk.jsonl \
  --project "API Design" \
  --output manual_test/v1.2.0_update/out-project \
  --no-llm --dry-run
```

**Verify:**
- [ ] Exit code 0
- [ ] Only conversations matching "API Design" are included

---

## E. Multi-Target Output

### E1. Codex target

```bash
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-codex \
  --target codex --no-llm
```

**Verify:**
- [ ] `AGENTS.md` exists
- [ ] `TASKS.md` exists

### E2. All targets

```bash
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-all \
  --target all --no-llm
```

**Verify:**
- [ ] `CLAUDE.md` + `PLAN.md` (claude-code)
- [ ] `AGENTS.md` + `TASKS.md` (codex)
- [ ] `.github/copilot-instructions.md` (copilot)
- [ ] `.aider.conf.yml` (aider)
- [ ] `goose-context.json` (goose)

---

## F. Multi-Source Parsers

### F1. ChatGPT

```bash
handover \
  --input tests/fixtures/chatgpt_single.json \
  --output manual_test/v1.2.0_update/out-chatgpt \
  --no-llm --dry-run
```

**Verify:**
- [ ] Output mentions `chatgpt` as detected source

### F2. Gemini

```bash
handover \
  --input tests/fixtures/gemini_single.json \
  --output manual_test/v1.2.0_update/out-gemini \
  --no-llm --dry-run
```

**Verify:**
- [ ] Output mentions `gemini` as detected source

### F3. Perplexity

```bash
handover list tests/fixtures/perplexity_bulk.json
```

**Verify:**
- [ ] Lists conversations including "FastAPI vs Flask"

---

## G. Codebase Indexer

### G1. Index current project

```bash
handover index --project . --dry-run
```

**Verify:**
- [ ] Shows files that would be indexed
- [ ] Lists Python files found

```bash
handover index --project . --output manual_test/v1.2.0_update/out-index
```

**Verify:**
- [ ] `out-index/.handover/codebase/structure.json` — has file tree
- [ ] `out-index/.handover/codebase/symbols.json` — has functions/classes
- [ ] `out-index/.handover/codebase/dependencies.json` — has import graph
- [ ] `out-index/.handover/codebase/index.md` — human-readable summary

### G2. --no-index flag

```bash
handover \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-noindex \
  --no-llm --no-index
```

**Verify:**
- [ ] `.handover/` exists but `.handover/codebase/` does NOT exist

---

## H. Reverse Handover

### H1. List sessions

```bash
handover sessions
```

**Verify:**
- [ ] Shows recent Claude Code session files (if any exist)

### H2. Reverse (requires existing session)

```bash
handover reverse --project . --no-llm --dry-run
```

**Verify:**
- [ ] Shows what would be written to `HANDOVER.md`
- [ ] Or reports "no session found" if none exist

---

## I. History & Rerun

### I1. View history

```bash
handover history
```

**Verify:**
- [ ] Lists recent runs (may be empty if first time)
- [ ] After running tests above, should show entries

### I2. Rerun (if history entries exist)

```bash
# Get an ID from history output
handover history
# Then:
handover rerun <id> --dry-run
```

---

## J. Merge Multiple Exports

```bash
handover merge \
  --input tests/fixtures/claude_single.json \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-merge \
  --no-llm --dry-run
```

**Verify:**
- [ ] Exit code 0
- [ ] Shows merged output summary

```bash
handover merge \
  --input tests/fixtures/claude_single.json \
  --input tests/fixtures/claude_single.json \
  --output manual_test/v1.2.0_update/out-merge \
  --target copilot --no-llm --dry-run
```

**Verify:**
- [ ] Exit code 0
- [ ] Mentions copilot target

---

## K. Browser Extension

### K1. Build the extension

```bash
cd /Users/mohankrishnaalavala/Documents/project_handover
bash scripts/build-extension.sh
```

**Verify:**
- [ ] `dist/handover-extension.zip` created
- [ ] Zip contains `manifest.json`, `background.js`, `content/`, `popup/`
- [ ] `manifest.json` inside zip shows version `1.2.0`

### K2. Load in Chrome

1. Open `chrome://extensions`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select the `extension/` directory
5. Verify the extension loads without errors

### K3. Test with handover serve

```bash
# Terminal 1: start the server
handover serve --no-llm --output manual_test/v1.2.0_update/out-serve

# Terminal 2: test health endpoint
curl http://localhost:7437/health
```

**Verify:**
- [ ] Server starts on port 7437
- [ ] Health endpoint returns JSON with status "ok"
- [ ] Extension popup shows connection status when server is running

### K4. End-to-end browser test

1. Start `handover serve --no-llm --output manual_test/v1.2.0_update/out-serve`
2. Open Claude.ai in Chrome with the extension loaded
3. Open a conversation
4. Click the handover extension popup
5. Click "Send to Claude Code"
6. Check `manual_test/v1.2.0_update/out-serve/` for generated files

---

## L. MCP Tools

### L1. Verify MCP config

The project `.mcp.json` should have:

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

### L2. Test MCP tools in Claude Code

Open Claude Code in this project directory. The MCP server should auto-start.

**Tool 1: run_handover**
```
Ask Claude Code: "Use the run_handover MCP tool to parse tests/fixtures/claude_single.json and write output to manual_test/v1.2.0_update/out-mcp with --no-llm"
```
- [ ] Tool executes successfully
- [ ] `manual_test/v1.2.0_update/out-mcp/CLAUDE.md` created
- [ ] Response mentions `.handover/` and `.claude/` directories

**Tool 2: handover_status**
```
Ask Claude Code: "Use handover_status to check the status of manual_test/v1.2.0_update/out-mcp"
```
- [ ] Shows total/done/remaining task counts
- [ ] Shows high-priority items
- [ ] Shows next task

**Tool 3: handover_reverse**
```
Ask Claude Code: "Use handover_reverse to summarize the latest session for this project"
```
- [ ] Returns session summary or "no session found" message

**Tool 4: handover_list**
```
Ask Claude Code: "Use handover_list to list conversations in tests/fixtures/claude_bulk.jsonl"
```
- [ ] Shows conversation IDs and titles
- [ ] Shows 3 conversations

### L3. Start MCP server standalone (optional)

```bash
handover mcp
# Should start and wait for MCP protocol messages on stdin/stdout
# Ctrl+C to stop
```

---

## M. Init (template scaffolding)

```bash
handover init
```

**Verify:**
- [ ] Output mentions "Templates scaffolded"
- [ ] Output mentions `.j2` template files

---

## N. Automated Test Suite

```bash
pytest tests/ -v --cov=handover --cov-fail-under=80
```

**Verify:**
- [ ] All tests pass
- [ ] Coverage >= 80%

```bash
ruff check handover/ tests/
ruff format --check handover/ tests/
mypy handover/
```

**Verify:**
- [ ] No lint errors
- [ ] No format issues
- [ ] No type errors

---

## Cleanup

```bash
# Remove all test output directories
rm -rf manual_test/v1.2.0_update/out-*
```
