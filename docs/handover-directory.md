# The `.handover/` directory (v1.1.0)

Starting with v1.1.0, every `handover` run writes a vendor-neutral project
knowledge base to `<output>/.handover/` in addition to whatever the chosen
`--target` produces. The two layers are independent:

| Layer | Path | Owner | Purpose |
|---|---|---|---|
| 1 | `.handover/` | always generated | Vendor-neutral context, work plan, standards, prompts |
| 2 | per-target | `--target` flag | Thin agent workspace pointing into Layer 1 |

The Layer 1 directory is portable: copy it into any project and any agent
(Claude Code, Codex, Aider, Cursor, your own scripts) can read the same
markdown.

## Layout

```
.handover/
├── manifest.yaml                      # version, source, target, project, generated_at
├── context/
│   ├── overview.md                    # Goal + vision + success criteria
│   ├── architecture.md                # Tech stack + system design
│   ├── decisions.md                   # ADR-format decision log
│   ├── constraints.md                 # Hard constraints + non-goals
│   ├── risks.md                       # Open questions and risks
│   └── acceptance-criteria.md         # Definition of done
├── work/
│   ├── spec.md                        # Full feature spec
│   ├── tasks.md                       # Markdown checklist of tasks
│   ├── milestones.md                  # Phase grouping for tasks
│   └── backlog.json                   # Machine-readable task store
├── standards/
│   ├── coding-standards.md
│   ├── testing-standards.md
│   ├── security-guardrails.md
│   └── release-checklist.md
└── prompts/
    ├── implement.md                   # Drop-in prompt for implementation
    ├── review.md                      # Drop-in prompt for code review
    ├── debug.md                       # Drop-in prompt for debugging
    ├── test.md                        # Drop-in prompt for test writing
    ├── onboard.md                     # Drop-in prompt for onboarding
    └── continue.md                    # Drop-in prompt for resuming work
```

For the `claude-code` target, an additional Layer 2 workspace is generated at
`.claude/`:

```
.claude/
├── agents/<name>.md                   # one per detected domain
├── skills/<name>.md                   # attached to detected domains
├── commands/<name>.md                 # default: run-tests, lint
├── hooks/pre-tool-use.sh              # chmod +x on write
└── settings.json
```

The agent files are produced by walking `DOMAIN_RULES` in
`handover/scaffold_extractor.py` against the chat content. For example, a
chat that mentions "FastAPI" and "PostgreSQL" yields a `backend-agent.md` and
a `database-agent.md` automatically.

## Generating only one layer

```bash
# Default — both layers
handover --input chat.json --output ./project/

# Skip Layer 1 (legacy v1.0.x output only)
handover --input chat.json --output ./project/ --no-handover-dir

# Skip Layer 2 (only the universal knowledge base)
handover --input chat.json --output ./project/ --handover-dir-only

# Replace an existing .handover/ and .claude/ on re-run
handover --input chat.json --output ./project/ --overwrite-handover-dir
```

By default a re-run against an existing `.handover/` aborts to avoid
overwriting hand-edited content. Pass `--overwrite-handover-dir` if you want
to regenerate both layers from a fresh chat.

## Cost

The Layer 1 extraction adds **exactly one** Claude API call to a normal run.
Use `--no-llm` to fall back to the rule-based extractor in
`handover/scaffold_heuristics.py` — every section is still populated, just
from `HandoverContext` data instead of an LLM summary.

## Extending

The implementation is registry-driven so adding new content is one line:

- **A new file under `.handover/`**: add a row to `HANDOVER_DIR_FILES` in
  `handover/universal_generator.py` and create the matching `.j2` template.
- **A new domain agent**: add a `DomainRule(...)` entry to `DOMAIN_RULES` in
  `handover/scaffold_extractor.py`.
- **A new section in the LLM extractor**: add the field name to
  `_BODY_FIELDS` (and to `ScaffoldContext` in `handover/models.py`), then
  reference it in your template.

No `if/elif` chains, no per-section helpers — every component reads or writes
the single `ScaffoldContext` carrier and otherwise stays out of the others'
internals.
