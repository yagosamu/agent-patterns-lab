"""Layer 1: fold text into a form the other layers can actually read."""

from __future__ import annotations

import unicodedata

TAG_START, TAG_END = 0xE0000, 0xE007F

# Zero-width space, ZWNJ, ZWJ, byte order mark, soft hyphen. All render as
# nothing, all can be sprinkled through a word to break a pattern match.
ZERO_WIDTH = {"", "", "‍", "", ""}

# Written as escapes on purpose: these characters are invisible, so a literal
# copy-paste silently loses them and the set stops matching anything.
BIDI = {
    "\u061C",  # ARABIC LETTER MARK
    "\u200E",  # LEFT-TO-RIGHT MARK
    "\u200F",  # RIGHT-TO-LEFT MARK
    "\u202A",  # LEFT-TO-RIGHT EMBEDDING
    "\u202B",  # RIGHT-TO-LEFT EMBEDDING
    "\u202C",  # POP DIRECTIONAL FORMATTING
    "\u202D",  # LEFT-TO-RIGHT OVERRIDE
    "\u202E",  # RIGHT-TO-LEFT OVERRIDE
    "\u2066",  # LEFT-TO-RIGHT ISOLATE
    "\u2067",  # RIGHT-TO-LEFT ISOLATE
    "\u2068",  # FIRST STRONG ISOLATE
    "\u2069",  # POP DIRECTIONAL ISOLATE
}


def decode_tag_chars(text: str) -> str:
    """Return the ASCII hidden inside Unicode Tag characters, if any."""
    return "".join(
        chr(ord(ch) - TAG_START) for ch in text if TAG_START <= ord(ch) <= TAG_END
    )


def normalize(text: str) -> tuple[str, list[str]]:
    """Strip invisible characters and fold lookalikes to their ASCII form."""
    findings: list[str] = []

    hidden = decode_tag_chars(text)
    if hidden:
        findings.append(f"unicode tag characters carrying hidden text: {hidden!r}")
    out_chars = []
    stripped_zw = 0
    stripped_bidi = 0
    for ch in text:
        code = ord(ch)
        if TAG_START <= code <= TAG_END:
            continue
        if ch in ZERO_WIDTH:
            stripped_zw += 1
            continue
        if ch in BIDI:
            stripped_bidi += 1
            continue
        out_chars.append(ch)

    if stripped_zw:
        findings.append(f"{stripped_zw} zero-width character(s) stripped")
    if stripped_bidi:
        findings.append(f"{stripped_bidi} bidi override character(s) stripped")

    cleaned = "".join(out_chars)
    folded = unicodedata.normalize("NFKC", cleaned)
    if folded != cleaned:
        findings.append("compatibility characters folded to ASCII by NFKC")
    if hidden:
        folded = f"{folded}\n[recovered hidden text] {hidden}"
    return folded, findings