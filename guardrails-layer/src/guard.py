"""The guardrails layer itself: which checks run, in what order, and why."""

from __future__ import annotations

from dataclasses import dataclass, field

from src import canary, pii, sanitize
from src.config import DOC_QUARANTINE_AT, USER_ESCALATE_AT
from src.corpus import Doc
from src.normalize import normalize
from src.policy import judge
from src.promptguard import scan


@dataclass(frozen=True)
class GuardConfig:
    """One rung of the ablation ladder."""
    name: str
    hardened_prompt: bool = False
    normalize_text: bool = False
    scan_user: bool = False
    escalate_to_judge: bool = False
    scan_docs: bool = False
    pii_firewall: bool = False
    canary_check: bool = False

REFUSAL = (
 "I can't help with that request. If you need account changes, raise a "
 "ticket from the app and a support agent will take it forward."
)
TRUNCATED = "no answer (truncated reasoning)"

@dataclass
class InputDecision:
    """What the input side of the layer concluded."""
    allowed: bool
    user_text: str
    docs: list[Doc]
    quarantined: list[str] = field(default_factory=list)
    blocked_by: str = ""
    reason: str = ""
    notes: list[str] = field(default_factory=list)


@dataclass
class OutputDecision:
    """What the output side of the layer concluded."""
    text: str
    blocked_by: str = ""
    pii_found: list[tuple[str, str]] = field(default_factory=list)
    canary_leaked: bool = False
    reasoning_stripped: bool = False


async def check_input(
    user_text: str, docs: list[Doc], cfg: GuardConfig) -> InputDecision:
    """Run the input-side layers in order, cheapest first."""
    notes: list[str] = []
    text = user_text

    if cfg.normalize_text:
        text, findings = normalize(text)
        notes.extend(findings)

    if cfg.scan_user:
        result = await scan(text)
        notes.append(f"prompt-guard user score {result.score:.3f}")
        if result.score >= USER_ESCALATE_AT:
            if cfg.escalate_to_judge:
                blocked, _ = await judge(text)
                notes.append(f"policy judge: {'BLOCK' if blocked else 'ALLOW'}")
                if blocked:
                    return InputDecision(
                        False, text, [], blocked_by="policy judge",
                        reason="policy violation", notes=notes,
                    )
            return InputDecision(
                False, text, [], blocked_by="prompt-guard",
                reason=f"score {result.score:.3f}", notes=notes,
             )
    return await _filter_docs(text, docs, cfg, notes)


async def _filter_docs(
 text: str, docs: list[Doc], cfg: GuardConfig, notes: list[str]) -> InputDecision:
    """Normalize and scan each retrieved document, dropping poisoned ones."""
    kept: list[Doc] = []
    quarantined: list[str] = []

    for doc in docs:
        body = doc.body
        if cfg.normalize_text:
            body, findings = normalize(body)
            notes.extend(f"{doc.doc_id}: {f}" for f in findings)
        if cfg.scan_docs:
            result = await scan(body)
            if result.score >= DOC_QUARANTINE_AT:
                quarantined.append(doc.doc_id)
                notes.append(f"{doc.doc_id}: quarantined at {result.score:.3f}")
                continue
            kept.append(Doc(doc.doc_id, doc.title, body, doc.poisoned))

        return InputDecision(True, text, kept, quarantined=quarantined, notes=notes)


def check_output(
    answer: str,
    cfg: GuardConfig,
    known_values: set[str],
    protected: dict[str, str] | None = None,) -> OutputDecision:
    """Run the output-side layers. None of them consults a model."""
    if not (cfg.pii_firewall or cfg.canary_check):
        return OutputDecision(text=answer)

    text, had_reasoning = sanitize.strip_reasoning(answer)

    if had_reasoning and not text.strip():
        return OutputDecision(
            text=REFUSAL, blocked_by=TRUNCATED, reasoning_stripped=True,
        )
    if cfg.canary_check and canary.leaked(text):
        return OutputDecision(
            text=REFUSAL, blocked_by="canary", canary_leaked=True,
            reasoning_stripped=had_reasoning,
        )
    found: list[tuple[str, str]] = []
    if cfg.pii_firewall:
        text, denied = pii.deny_list(text, protected or {})
        found.extend(denied)
        result = pii.firewall(text, known_values=known_values)
        text = result.text
        found.extend(result.found)
    return OutputDecision(
        text=text, pii_found=found, reasoning_stripped=had_reasoning
    )

