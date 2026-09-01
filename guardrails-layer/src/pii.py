"""Layer 4: the output firewall. Detect and redact PII before the user sees it."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

# Presidio pulls in spaCy, which loads native extensions. It is imported lazily
# inside the functions that need it so the deterministic layers of this module
# (deny_list, the dataclasses) stay usable without that dependency.
from src.config import PII_MIN_SCORE

WATCHED = [
 "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD",
 "IN_PAN", "IN_AADHAAR", "PAYSETU_ACCOUNT",
]


def _keep_last_four(value: str) -> str:
    """Redact a number but keep its last four digits."""
    digits = [ch for ch in value if ch.isdigit()]
    tail = "".join(digits[-4:])
    return f"[****{tail}]" if tail else "[REDACTED]"


@lru_cache(maxsize=1)
def _operators() -> dict:
    """Redaction rules. Built lazily so importing this module stays cheap."""
    from presidio_anonymizer.entities import OperatorConfig

    return {
        "DEFAULT": OperatorConfig("replace", {"new_value": "[REDACTED]"}),
        "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "[EMAIL]"}),
        "PHONE_NUMBER": OperatorConfig("custom", {"lambda": _keep_last_four}),
        "CREDIT_CARD": OperatorConfig("custom", {"lambda": _keep_last_four}),
        "IN_PAN": OperatorConfig("replace", {"new_value": "[PAN]"}),
        "IN_AADHAAR": OperatorConfig("replace", {"new_value": "[AADHAAR]"}),
        "PAYSETU_ACCOUNT": OperatorConfig("replace", {"new_value": "[ACCOUNT]"}),
    }


def _account_recognizer() -> PatternRecognizer:
    """Recognise this product's own account numbers, e.g. PS-40028113."""
    from presidio_analyzer import Pattern, PatternRecognizer

    pattern = Pattern(name="paysetu_account", regex=r"\bPS-\d{8}\b", score=0.9)
    return PatternRecognizer(
        supported_entity="PAYSETU_ACCOUNT",
        patterns=[pattern],
        context=["account", "acct", "wallet"],
    )


@lru_cache(maxsize=1)
def _engines() -> tuple[AnalyzerEngine, AnonymizerEngine]:
    """Build the analyzer once. Loading spaCy on every call is seconds wasted."""
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_analyzer.predefined_recognizers import (
        InAadhaarRecognizer, InPanRecognizer,
    )
    from presidio_anonymizer import AnonymizerEngine

    config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }
    nlp = NlpEngineProvider(nlp_configuration=config).create_engine()

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp)
    registry.add_recognizer(InPanRecognizer())
    registry.add_recognizer(InAadhaarRecognizer())
    registry.add_recognizer(_account_recognizer())

    analyzer = AnalyzerEngine(
    nlp_engine=nlp, registry=registry, supported_languages=["en"]
    )
    return analyzer, AnonymizerEngine()


def _spaced_pattern(value: str) -> re.Pattern:
    """Match a value even if it is written with different separators."""
    chars = [ch for ch in value if ch.isalnum()]
    body = r"\W{0,3}".join(re.escape(ch) for ch in chars)
    return re.compile(body, re.IGNORECASE)


def deny_list(
    text: str, protected: dict[str, str]) -> tuple[str, list[tuple[str, str]]]:
    """Redact values we know must never appear, by exact skeleton match."""
    found: list[tuple[str, str]] = []
    ordered = sorted(protected.items(), key=lambda kv: -len(kv[1]))
    for label, value in ordered:
        if len(value.strip()) < 4:
            continue
        pattern = _spaced_pattern(value)
        if pattern.search(text):
            found.append((f"DENY_{label.upper()}", value))
            text = pattern.sub(f"[{label.upper()} WITHHELD]", text)
    return text, found


@dataclass
class PiiResult:
    """What the firewall found and what it did about it."""

    text: str
    found: list[tuple[str, str]]


def _is_known(value: str, known: set[str]) -> bool:
    """True if the customer supplied this value themselves."""
    squashed = "".join(ch for ch in value.lower() if ch.isalnum())
    return any(squashed and squashed in k for k in known)


def firewall(text: str, known_values: set[str] | None = None) -> PiiResult:
    """Redact third-party PII from an answer, leaving the customer's own alone."""
    analyzer, anonymizer = _engines()
    known = {
        "".join(ch for ch in v.lower() if ch.isalnum())
        for v in (known_values or set())
    }
    known.discard("")
    results = [
        r
        for r in analyzer.analyze(text=text, language="en", entities=WATCHED)
        if r.score >= PII_MIN_SCORE and not _is_known(text[r.start : r.end], known)
    ]
    if not results:
        return PiiResult(text=text, found=[])
    found = [(r.entity_type, text[r.start : r.end]) for r in results]
    redacted = anonymizer.anonymize(
        text=text, analyzer_results=results, operators=_operators()
    )
    return PiiResult(text=redacted.text, found=found)