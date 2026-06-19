#!/usr/bin/env python3
"""solve_hcaptcha.py — CLI bridge for hCaptcha (Lever-style) — mirror of solve_recaptcha_v3.py.

The chain worker invokes between detect/inject:

    .venv/bin/python solve_hcaptcha.py --stdin --page-url <url> [--fallback-sitekey <k>]

Prints a single JSON line:
    SUCCESS: {"ok": true, "token": "...", "latency_ms": N, "sitekey": "..."}
    FAILURE: {"ok": false, "reason": "...", "latency_ms": N, ...}

Exit codes match solve_recaptcha_v3.py: 0=clean, 2=solve-failed, 3=bad-input.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from capsolver_client import (  # noqa: E402
    CapSolverClient,
    CapSolverDisabled,
    CapSolverError,
    is_enabled,
)


def _emit(payload: dict, code: int) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()
    sys.exit(code)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sitekey", default=None)
    ap.add_argument("--page-url", default=None)
    ap.add_argument("--stdin", action="store_true",
                    help="Read JSON detect-payload from stdin "
                         "(captcha.handle detect_fn return shape: {sitekey, page_url, ...}).")
    ap.add_argument("--fallback-sitekey", default=None)
    args = ap.parse_args()

    detect: dict = {}
    if args.stdin:
        try:
            raw = sys.stdin.read().strip()
            detect = json.loads(raw) if raw else {}
        except Exception as e:
            _emit({"ok": False, "reason": f"stdin parse failed: {e}",
                   "stage": "stdin"}, 3)

    sitekey = (
        args.sitekey
        or (detect.get("sitekey") if isinstance(detect, dict) else None)
        or args.fallback_sitekey
    )
    page_url = args.page_url or (detect.get("page_url") if isinstance(detect, dict) else None)

    if not sitekey:
        _emit({"ok": False, "reason": "no sitekey provided", "stage": "input"}, 3)
    if not page_url:
        _emit({"ok": False, "reason": "no page_url provided", "stage": "input",
               "sitekey": sitekey}, 3)

    if not is_enabled():
        _emit({"ok": False, "reason": "ENABLE_CAPSOLVER!=1 or CAPSOLVER_API_KEY unset",
               "stage": "gate", "sitekey": sitekey, "page_url": page_url}, 0)

    t0 = time.time()
    try:
        client = CapSolverClient()
    except CapSolverDisabled as e:
        latency_ms = int((time.time() - t0) * 1000)
        _emit({"ok": False, "reason": f"client construction failed: {e}",
               "stage": "client", "latency_ms": latency_ms,
               "sitekey": sitekey, "page_url": page_url}, 2)

    try:
        token = client.hcaptcha(sitekey=sitekey, page_url=page_url)
    except CapSolverError as e:
        latency_ms = int((time.time() - t0) * 1000)
        _emit({"ok": False, "reason": str(e), "stage": "solve",
               "latency_ms": latency_ms, "sitekey": sitekey, "page_url": page_url}, 2)

    latency_ms = int((time.time() - t0) * 1000)
    _emit({"ok": True, "token": token, "latency_ms": latency_ms,
           "sitekey": sitekey, "page_url": page_url, "kind": "hcaptcha"}, 0)


if __name__ == "__main__":
    main()
