"""Every Groq call the project makes: the assistant, the classifier, the judge."""

from __future__ import annotations

import asyncio
import random

from groq import AsyncGroq, APIStatusError

from src import cache
from src.config import CHAT_MODEL, GROQ_API_KEY, GUARD_MODEL, POLICY_MODEL
from src.config import MAX_RETRY_TOKENS, assistant_tokens

_client: AsyncGroq | None = None
MAX_RETRIES = 8


def client() -> AsyncGroq:
    """Return a lazily created AsyncGroq client."""
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is empty. Copy .env.example to .env.")
        _client = AsyncGroq(api_key=GROQ_API_KEY)
    return _client


def _retry_after(exc: APIStatusError) -> float | None:
    """Seconds Groq asked us to wait, if it said."""
    try:
        value = exc.response.headers.get("retry-after")
        return float(value) + 1 if value else None
    except (AttributeError, TypeError, ValueError):
        return None


async def _complete(model: str, messages: list[dict], **kwargs) -> str:
    """Call chat.completions with caching, backoff, and a truncation retry."""
    payload = {"messages": messages, **kwargs}
    hit = cache.get(model, payload)
    if hit is not None:
        return hit

    for attempt in range(MAX_RETRIES):
        try:
            resp = await client().chat.completions.create(
                model=model, messages=messages, **kwargs
            )
            break
        except APIStatusError as exc:
            if exc.status_code != 429 or attempt == MAX_RETRIES - 1:
                raise
            wait = _retry_after(exc) or 10 * (attempt + 1)
            await asyncio.sleep(wait + random.uniform(0, 4))

    choice = resp.choices[0]
    text = choice.message.content or ""

    if choice.finish_reason == "length" and "max_completion_tokens" in kwargs:
        roomier = dict(kwargs)
        roomier["max_completion_tokens"] = min(
            kwargs["max_completion_tokens"] * 2, MAX_RETRY_TOKENS
        )
        try:
            resp = await client().chat.completions.create(
                model=model, messages=messages, **roomier
            )
            text = resp.choices[0].message.content or text
        except APIStatusError:
            pass  # keep the truncated answer rather than losing the run
    cache.put(model, payload, text)
    return text


async def assistant(system: str, user: str, model: str | None = None) -> str:
    """Run the assistant we are defending."""
    chat_model = model or CHAT_MODEL
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return await _complete(
        chat_model,
        messages,
        temperature=0.0,
        max_completion_tokens=assistant_tokens(chat_model),
    )


async def guard_score(text: str) -> float:
    """Score one chunk of text with Prompt Guard 2."""
    raw = await _complete(GUARD_MODEL, [{"role": "user", "content": text}])
    try:
        return float(raw.strip())
    except ValueError:
        return 1.0


async def policy_verdict(policy: str, text: str) -> tuple[str, str]:
    """Judge text against a written policy. Returns (verdict, reasoning)."""
    messages = [
        {"role": "system", "content": policy},
        {"role": "user", "content": text},
    ]
    raw = await _complete(
        POLICY_MODEL, messages, temperature=0.0, max_completion_tokens=1600
    )
    word = raw.strip().upper()
    if "BLOCK" in word:
        return "BLOCK", raw
    if "ALLOW" in word:
        return "ALLOW", raw
    return "BLOCK", raw or "(empty response)"