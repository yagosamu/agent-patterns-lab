"""Strip model scaffolding before anything else reads the answer."""

from __future__ import annotations

import re

# Closed blocks first, then an unterminated opener - which is what a
# truncated response leaves behind.
THINK_BLOCK = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.DOTALL | re.I)
THINK_OPEN = re.compile(r"<(think|thinking|reasoning)>.*", re.DOTALL | re.I)


def strip_reasoning(text: str) -> tuple[str, bool]:
    """Remove reasoning blocks. Returns (clean text, whether any were found)."""
    cleaned = THINK_BLOCK.sub("", text)
    cleaned = THINK_OPEN.sub("", cleaned)
    return cleaned.strip(), cleaned != text