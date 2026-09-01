"""Run the PII firewall over sample text."""

import sys

from src.pii import firewall

sys.stdout.reconfigure(encoding="utf-8")

CASES = [
    "Account holder Rohit Verma, phone +91 98765 43210, PAN ABCDE1234F, account PS-40028113.",
    "What is your refund policy for orders over 5000 rupees?",
]

for text in CASES:
    result = firewall(text)
    print(f"in  : {text}")
    print(f"out : {result.text}")
    print(f"raw : {result!r}")
    print()
