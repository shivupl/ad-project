"""Single home for API clients, model choices, and LLM call helpers.

Every module used to initialize its own Anthropic/Firecrawl client and carry
its own copy of the fence-strip + JSON-parse + retry logic. It all lives here
now — change a model in one place, fix parsing in one place.
"""

import json
import os
import re

import anthropic
from dotenv import load_dotenv
from firecrawl import FirecrawlApp

load_dotenv()

# The two models the project uses. Swap here, nowhere else.
MODEL_HEAVY = "claude-sonnet-5"             # extraction, strategy, design, review
MODEL_LIGHT = "claude-haiku-4-5-20251001"   # ranking and selection

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
firecrawl = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))


def strip_fences(text: str) -> str:
    """Remove markdown code fences models sometimes wrap output in."""
    text = text.strip()
    text = re.sub(r'^```(?:json|html)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def complete(content, *, model: str = MODEL_HEAVY, max_tokens: int = 8000, system: str = None) -> str:
    """One model call → fence-stripped text. `content` is a string or a list of
    content blocks (for image/document input). Thinking is explicitly disabled
    on the heavy model (it defaults on for Sonnet 5 and would eat max_tokens)."""
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if system:
        kwargs["system"] = system
    if model == MODEL_HEAVY:
        kwargs["thinking"] = {"type": "disabled"}

    response = client.messages.create(**kwargs)

    if response.stop_reason == "max_tokens":
        print(f"Warning: response hit max_tokens ({max_tokens}) — output may be truncated")

    return strip_fences(response.content[0].text)


def complete_json(content, *, model: str = MODEL_HEAVY, max_tokens: int = 8000,
                  system: str = None, retries: int = 2):
    """complete() + json.loads with retry. Returns the parsed object, or None
    after all attempts fail — callers decide their own fallback."""
    for attempt in range(1, retries + 1):
        raw = complete(content, model=model, max_tokens=max_tokens, system=system)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"JSON parse error (attempt {attempt}): {e}")
            print(f"Raw: {raw[:200]}")
    return None
