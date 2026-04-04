# Contributing to handover

Thank you for your interest in contributing! `handover` is an open-source project and contributions are very welcome.

## Setup

```bash
git clone https://github.com/mohankrishnaalavala/handover.git
cd handover
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v --cov=handover --cov-report=term-missing
```

All tests must pass before submitting a PR. Never commit code that breaks existing tests.

## Primary Contribution Path: Adding a New Source Adapter

Adding a new source (ChatGPT, Gemini, Perplexity, etc.) is the primary way to contribute. Each adapter is one self-contained class in `handover/parsers/`. A contributor can own an adapter end-to-end as an isolated PR.

See **[docs/adding-an-adapter.md](docs/adding-an-adapter.md)** for the complete step-by-step guide.

In brief, adding a new adapter means:
1. Create `handover/parsers/{source_name}.py` — subclass `BaseParser`
2. Register the adapter in `parsers/__init__.py`
3. Add a test fixture in `tests/fixtures/`
4. Add tests in `tests/test_parser.py`
5. Update the supported formats table in `README.md`
6. Add the source name to the `--source` flag in `cli.py`

## Code Standards

The following standards are taken directly from `CLAUDE.md` and apply to all contributions:

- **Type hints** on all functions and methods
- **Docstrings** on all public methods
- **Tests required** for: parser output, heuristics rules, generator file output
- Mocked API calls in `test_summarizer.py` — never hit the real Anthropic API in tests
- No additional dependencies beyond: `click`, `anthropic`, `jinja2`, `pytest`, `pytest-cov`

## Submitting a Pull Request

1. Fork the repo and create a feature branch
2. Make your changes, add tests, update docs
3. Run `pytest tests/ -v` — all tests must pass
4. Update `PLAN.md` if your PR completes any listed tasks
5. Open a PR against `main` using the PR template

## Project Phases

Before contributing, it helps to understand the roadmap:

- **Phase 1** (current): Claude chat → Claude Code. This is what we're building now.
- **Phase 2**: Universal chat sources — ChatGPT, Gemini, Perplexity adapters. **This is the main open contribution path.**
- **Phase 3**: Reverse handover — Claude Code session logs → readable handover doc.
- **Phase 4**: Additional target agents (Aider, Goose, Codex CLI).

Please check open issues and the `PLAN.md` before starting work to avoid duplicating effort.
