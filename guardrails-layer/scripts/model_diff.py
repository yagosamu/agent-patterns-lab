"""Confirm that the --model override actually changes what the assistant says."""

import asyncio
import sys

from src import llm

sys.stdout.reconfigure(encoding="utf-8")

SYSTEM = "You are a concise support assistant."
USER = "In one sentence, what should a customer do if a refund is delayed?"


async def main() -> None:
    for model in (None, "openai/gpt-oss-20b"):
        text = await llm.assistant(SYSTEM, USER, model=model)
        label = model or "default (CHAT_MODEL)"
        print(f"[{label}]")
        print(f"  {text.strip()[:160]}")
        print()


asyncio.run(main())
