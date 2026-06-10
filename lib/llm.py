"""
Thin OpenAI wrapper. Reads OPENAI_API_KEY from the environment (never
hardcoded). Returns None on any failure so callers can fall back to
rule-based logic and keep the demo running fully offline.

IMPORTANT: the model is only ever asked to *reason about* or *phrase* numbers
that were already computed in plain Python. It is never asked to produce the
indicators, prices, confidence, or risk levels themselves.
"""

import json

from config import OPENAI_MODEL, openai_enabled


def chat(system: str, user: str, want_json: bool = False, max_tokens: int = 500):
    """Single-shot chat completion. Returns the text content, or None on failure."""
    if not openai_enabled():
        return None
    try:
        from openai import OpenAI

        client = OpenAI()  # picks up OPENAI_API_KEY from env
        kwargs = {
            "model": OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        if want_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content
    except Exception:
        # Network error, bad key, rate limit, SDK change — silently degrade.
        return None


def chat_json(system: str, user: str, max_tokens: int = 500):
    """chat() but parses the response as JSON. Returns a dict or None."""
    raw = chat(system, user, want_json=True, max_tokens=max_tokens)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None
