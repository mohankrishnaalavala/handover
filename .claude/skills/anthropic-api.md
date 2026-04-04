# Skill: Calling the Anthropic API Correctly

This skill documents how to call the Anthropic API within the `handover` project.

## Setup

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
```

## Correct Model Name

Use `claude-sonnet-4-6` for summarization tasks. This is specified in the tech stack.

```python
MODEL = "claude-sonnet-4-6"
```

## Structured Extraction Pattern

When calling the API to extract `HandoverContext` from conversation messages:

```python
def extract_context(messages: list[ConversationMessage]) -> HandoverContext:
    conversation_text = "\n".join(
        f"{m.role.upper()}: {m.content}" for m in messages
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": f"""Extract structured information from this AI chat conversation.
Return ONLY valid JSON matching this schema:
{{
  "goal": "<single sentence>",
  "tech_stack": {{"language": "...", "framework": "..."}},
  "decisions": [{{"topic": "...", "decision": "...", "rationale": "..."}}],
  "tasks": [{{"title": "...", "description": "...", "priority": "high|medium|low", "done": false}}],
  "constraints": ["..."],
  "non_goals": ["..."],
  "open_questions": ["..."]
}}

Conversation:
{conversation_text}"""
            }
        ]
    )

    import json
    return json.loads(response.content[0].text)
```

## In Tests: Always Mock the API

```python
from unittest.mock import patch, MagicMock

def test_summarizer_extracts_goal(mock_messages):
    mock_response = MagicMock()
    mock_response.content[0].text = '{"goal": "Build a FastAPI app", ...}'

    with patch("handover.summarizer.anthropic.Anthropic") as mock_client:
        mock_client.return_value.messages.create.return_value = mock_response
        result = summarize(mock_messages)
        assert result.goal == "Build a FastAPI app"
```

## Error Handling

- Wrap API calls in try/except for `anthropic.APIError`
- Fall back to `--no-llm` mode if the API key is missing (`anthropic.AuthenticationError`)
- Never let API errors crash the CLI without a user-friendly message
