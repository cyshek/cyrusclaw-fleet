#!/usr/bin/env python3
"""Regression test for gmail_imap._extract_code.

Covers the 2026-06-10 fix: Workday (and most non-Greenhouse ATS) email-verify
codes are 4-8 digit NUMERIC, but the original extractor only matched 8-char
alnum tokens -> it mis-extracted garbage (e.g. "2FSenior") on Gates Foundation
Workday verify mails. This test pins:
  - Workday 6-digit numeric codes extract (body + <h1>)
  - Greenhouse 8-char alnum codes still extract (no regression)
  - The garbage-token case yields the real numeric code

Run: .venv/bin/python -m pytest test_gmail_imap_extract_code.py  (or plain python).
"""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("gmail_imap", os.path.join(_HERE, "gmail_imap.py"))
_gi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_gi)
_extract_code = _gi._extract_code

CASES = [
    ("Your verification code is 483920. It expires in 10 minutes.", "Verify your account", "483920"),
    ("<h1>K7X9QM4P</h1>", "Greenhouse verification", "K7X9QM4P"),
    ("Your security code: A1B2C3D4 - enter to continue", "Verify your application", "A1B2C3D4"),
    ("<h1>602847</h1>", "Workday verify", "602847"),
    ("Use code 600308 to verify your email at Sager.", "Sager Electronics - verify", "600308"),
    ("Please verify. Senior TPM role 2F. code is 712044.", "Gates Foundation verify your email", "712044"),
]


def test_extract_code_variants():
    for body, subject, expected in CASES:
        got = _extract_code(body, subject)
        assert got == expected, f"body={body!r} subject={subject!r}: got {got!r}, expected {expected!r}"


if __name__ == "__main__":
    failures = 0
    for body, subject, expected in CASES:
        got = _extract_code(body, subject)
        ok = got == expected
        failures += 0 if ok else 1
        print(f"[{'PASS' if ok else 'FAIL'}] {subject!r}: got={got!r} exp={expected!r}")
    print("ALL PASS" if not failures else f"{failures} FAILED")
    sys.exit(1 if failures else 0)
