"""The ablation ladder: five configurations, one new mechanism per rung."""

from __future__ import annotations

from src.guard import GuardConfig

CONFIGS: list[GuardConfig] = [
    GuardConfig("off"),
    GuardConfig("prompt-only", hardened_prompt=True),
    GuardConfig(
        "classifier",
        hardened_prompt=True, normalize_text=True,
        scan_user=True, scan_docs=True,
    ),
    GuardConfig(
        "classifier+judge",
        hardened_prompt=True, normalize_text=True, scan_user=True,
        escalate_to_judge=True, scan_docs=True,
    ),
    GuardConfig(
        "full stack",
        hardened_prompt=True, normalize_text=True, scan_user=True,
        escalate_to_judge=True, scan_docs=True,
        pii_firewall=True, canary_check=True,
    ),
]
CONFIGS_BY_NAME = {c.name: c for c in CONFIGS}