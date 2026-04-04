# Adding a New Source Adapter

This guide walks you through adding support for a new chat export source (e.g. ChatGPT, Gemini, Perplexity) to `handover`. Each adapter is a single Python class and can be contributed as a standalone PR.

---

## Overview

The adapter pattern means every source lives in its own file under `handover/parsers/`. Your adapter receives a raw export file and returns a normalized list of `ConversationMessage` objects. Everything downstream (summarizer, generator) is source-agnostic.

---

## Step-by-Step

### 1. Create `handover/parsers/{source_name}.py`

Replace `{source_name}` with the lowercase name of the source (e.g. `chatgpt`, `gemini`, `perplexity`).

```python
"""
handover/parsers/chatgpt.py

Adapter for ChatGPT conversation exports (conversations.json).
See PRD Section 5 — Phase 2.
"""
from pathlib import Path
from handover.parsers.base import BaseParser
from handover.models import ConversationMessage


class ChatGPTParser(BaseParser):
    """Parse ChatGPT conversation exports into ConversationMessage objects."""

    source_name = "chatgpt"

    def parse(self, file_path: Path) -> list[ConversationMessage]:
        """
        Parse a ChatGPT export file and return normalized messages.

        Args:
            file_path: Path to the ChatGPT export file.

        Returns:
            List of ConversationMessage objects in chronological order.
        """
        # TODO: implement parsing logic
        raise NotImplementedError
```

### 2. Subclass `BaseParser` from `parsers/base.py`

Your class must:
- Set `source_name: str` as a class attribute (used for `--source` flag matching)
- Implement `parse(file_path: Path) -> list[ConversationMessage]`
- Raise `ValueError` for unrecognized file formats with a helpful message

### 3. Implement `parse(file_path) -> list[ConversationMessage]`

- Return messages in chronological order
- Set `role` to `"user"` or `"assistant"` (normalize source-specific roles)
- Set `timestamp` to ISO format string if available, otherwise `None`
- Set `message_id` if the export includes one, otherwise `None`
- Strip empty messages or system prompts not relevant to extraction

### 4. Register the adapter in `parsers/__init__.py`

```python
from handover.parsers.chatgpt import ChatGPTParser

ADAPTER_REGISTRY: dict[str, type[BaseParser]] = {
    "claude": ClaudeParser,
    "chatgpt": ChatGPTParser,  # add your adapter here
}
```

### 5. Add a test fixture in `tests/fixtures/`

Create an **anonymized** sample export file:
- `tests/fixtures/{source_name}_single.json` — single conversation
- `tests/fixtures/{source_name}_bulk.jsonl` — bulk export (if the source supports it)

Anonymize all personal information: replace names, emails, project names, and any identifying content with generic placeholders.

### 6. Add tests to `tests/test_parser.py`

```python
def test_chatgpt_parser_single():
    parser = ChatGPTParser()
    messages = parser.parse(Path("tests/fixtures/chatgpt_single.json"))
    assert len(messages) > 0
    assert all(m.role in ("user", "assistant") for m in messages)
    assert messages[0].role == "user"


def test_chatgpt_parser_returns_chronological_order():
    parser = ChatGPTParser()
    messages = parser.parse(Path("tests/fixtures/chatgpt_single.json"))
    # Verify order is stable across calls
    assert messages == parser.parse(Path("tests/fixtures/chatgpt_single.json"))
```

### 7. Update the README supported formats table

Add a row to the table in `README.md`:

```markdown
| ChatGPT | `.json` | Settings → Data Controls → Export Data |
```

### 8. Add the source to the `--source` flag in `cli.py`

In the `--source` Click option, add `"chatgpt"` to the list of valid choices:

```python
@click.option("--source", type=click.Choice(["claude", "chatgpt"]), default=None)
```

---

## Tips

- Look at `handover/parsers/claude.py` as a reference implementation
- Keep the adapter focused — no summarization logic belongs here
- If the export format has multiple versions, detect the version and handle each case explicitly
- Add a `source_version` string to help the summarizer and generator track format variants

---

## Checklist Before Opening a PR

- [ ] Adapter class created in `handover/parsers/{source_name}.py`
- [ ] Registered in `parsers/__init__.py`
- [ ] Anonymized test fixture added in `tests/fixtures/`
- [ ] Tests pass: `pytest tests/ -v`
- [ ] README supported formats table updated
- [ ] `--source` flag choices updated in `cli.py`
- [ ] PR template checklist filled in
