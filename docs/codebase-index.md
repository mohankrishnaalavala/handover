# Codebase Index — `.handover/codebase/`

The codebase indexer (v1.1.2) scans a project directory and writes a
pre-computed map that agents read at session start to skip the discovery phase.

## Files produced

| File | Format | Purpose |
|------|--------|---------|
| `structure.json` | JSON | File tree with purpose, exports, imports, line count, test-file mapping |
| `symbols.json` | JSON | All public functions/classes with signatures, docstrings, line numbers |
| `dependencies.json` | JSON | Internal import graph + change-impact risk analysis per file |
| `index.md` | Markdown | Human-readable "where to find things" summary |

## When it runs

The indexer runs as the **last step** in the main pipeline:

```
parse → summarize → scaffold_extractor → universal_generator → target_generator → indexer
```

It inspects the output project directory. If source files exist, it writes
`.handover/codebase/`. If no source files are found (fresh project from chat
only), it skips silently.

## Usage

### Automatic (during handover)

```bash
handover --input chat.json --output ./my-project/
# Indexer runs automatically after target generation
```

Skip with `--no-index`:
```bash
handover --input chat.json --output ./my-project/ --no-index
```

### Standalone

```bash
# Index an existing project
handover index --project ./my-existing-project/

# Dry run — show what would be indexed
handover index --project ./my-project/ --dry-run

# Exclude patterns
handover index --project . --exclude 'legacy/**' --exclude '*.generated.py'

# Re-index (refresh)
handover index --project . --refresh
```

## Language support

| Language | Extensions | Method | Extracts |
|----------|-----------|--------|---------|
| Python | `.py` | `ast.walk()` | functions, classes, imports (precise) |
| TypeScript/JS | `.ts`, `.tsx`, `.js`, `.jsx`, `.mjs`, `.cjs` | regex | exports, imports (approximate) |
| Other | any | none | file listed, no symbols |

**Python extraction is precise** — `ast.walk()` gives exact signatures, line
numbers, and docstrings. Other language support is best-effort regex.

## Files excluded from indexing

- `node_modules/`, `__pycache__/`, `.venv/`, `venv/`, `dist/`, `build/`, `.git/`
- `.handover/`, `.claude/` (avoid indexing our own output)
- Any file > 500 lines (listed but not symbolised)
- Binary files (detected by null byte in first 1 KB)
- Files matching `--exclude` patterns

## How agents use it

When Claude Code (or another agent) starts a session on a project with
`.handover/codebase/`, it can read `structure.json` once and instantly know:

- What every file does (`purpose` field)
- What each file exports (`exports` field)
- What depends on what (`dependencies.json`)
- Which files are high-risk to change (`change_impact`)

This replaces the 5,000–10,000 token discovery phase that agents typically
spend on `ls`, `cat`, and `grep` at session start.

## MCP integration

- **`run_handover`** now triggers the indexer and includes codebase stats
  in its response string.
- **`handover_status`** reads `dependencies.json` to show "At risk" files
  when a completed task includes a `changed_files` field. (Future backlog
  schema versions will populate `changed_files` per task.)

## Schema versions

All JSON files include a `schema_version` field (currently `"1.0"`). If the
schema changes in a breaking way, this version will be bumped.
