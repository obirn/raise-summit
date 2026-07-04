# Me LLM Tracker

`Me` is a small Python wrapper for an LLM chat API. It records chats, messages,
API calls, token usage, responses, elapsed time, and errors in a local SQLite
database.

## Basic Usage

```python
from openai import OpenAI
from me import Me

client = OpenAI()
me = Me(
    client.chat.completions,
    db_path="llm_usage.sqlite3",
    default_model="gpt-4.1-mini",
)

result = me.chat([
    {"role": "system", "content": "You are concise."},
    {"role": "user", "content": "Write a haiku about databases."},
])

print(result.content)
print(result.usage.total_tokens)
print(me.usage_summary())
```

## Reusing A Chat

```python
chat_id = me.create_chat(title="Support bot test", metadata={"customer": "acme"})

first = me.chat(
    [{"role": "user", "content": "What can you help with?"}],
    chat_id=chat_id,
)

second = me.chat(
    [{"role": "user", "content": "Summarize the previous answer."}],
    chat_id=chat_id,
)

saved_chat = me.get_chat(chat_id)
```

## Custom Clients

Any callable or OpenAI-compatible object with `.create(**kwargs)` works:

```python
def my_llm(**kwargs):
    return {
        "choices": [{"message": {"content": "hello"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }

me = Me(my_llm, default_model="local-model")
```

Run tests with:

```bash
python -m unittest
```

## Google Gemini Computer Use Demo

This repo also includes a small educational Computer Use example:

- `computer_use_task.html` is a safe local web page with a simple form.
- `google_computer_use_demo.py` asks Gemini Computer Use to fill the form.
- The script uses Playwright as the local browser/action executor.

Install the demo dependencies:

```bash
pip install -r requirements-google-computer-use.txt
playwright install chromium
```

Set your Gemini API key:

```bash
export GEMINI_API_KEY="your-api-key"
```

Run the demo:

```bash
python google_computer_use_demo.py
```

Every client-side tool call requested by Gemini is saved to:

```text
computer_use_toolcalls.json
```

Every raw Gemini interaction response is saved to:

```text
computer_use_responses.json
```

Every per-turn screenshot description is saved to:

```text
computer_use_screen_descriptions.json
```

## FastAPI + SQLAlchemy Skeleton

The `app/` package contains a small layered FastAPI skeleton for issues and fixes:

```text
app/
  api/                  HTTP routes
  service/              business logic and domain models
    models/             pure service/domain models
  infrastructure/       database, SQLAlchemy tables, repositories
    repositories/
      models/           request and response models
    tables/
```

Install the API dependencies:

```bash
pip install -r requirements-api.txt
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```
