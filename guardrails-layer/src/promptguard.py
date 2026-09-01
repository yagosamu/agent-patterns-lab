"""Layer 2: score text with Meta Prompt Guard 2, in windows it can fit."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from src.config import GUARD_WINDOW_CHARS, GUARD_WINDOW_OVERLAP
from src.llm import guard_score


@dataclass
class ScanResult:
    """The outcome of scanning one block of text."""

    score: float
    windows: list[float] = field(default_factory=list)
    worst_window: str = ""


def split_windows(text: str) -> list[str]:
    """Cut text into overlapping windows small enough for a 512-token model."""
    if len(text) <= GUARD_WINDOW_CHARS:
        return [text]
    step = GUARD_WINDOW_CHARS - GUARD_WINDOW_OVERLAP
    return [
        text[i : i + GUARD_WINDOW_CHARS]
        for i in range(0, len(text), step)
        if text[i : i + GUARD_WINDOW_CHARS].strip()
    ]


async def scan(text: str) -> ScanResult:
    """Score every window of the text and keep the worst one."""
    text = text.strip()
    if not text:
        return ScanResult(score=0.0)

    windows = split_windows(text)
    scores = await asyncio.gather(*(guard_score(w) for w in windows))
    top = max(range(len(scores)), key=lambda i: scores[i])
    return ScanResult(
        score=scores[top], windows=list(scores), worst_window=windows[top]
    )