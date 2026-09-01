"""Layer 5: has the system prompt leaked?"""

from __future__ import annotations

from src.config import CANARY

def _squash(text: str) -> str:
    """Reduce text to lowercase alphanumerics."""
    return "".join(ch for ch in text.lower() if ch.isalnum())

def leaked(text: str) -> bool:
    """True if the canary, or a recognisable chunk of it, is in the text."""
    haystack = _squash(text)
    if _squash(CANARY) in haystack:
        return True
    # The distinctive middle is enough. A model that emits "7Q4X-ESCALATE"
    # has leaked the secret even without the prefix.
    return _squash("7Q4X-ESCALATE") in haystack