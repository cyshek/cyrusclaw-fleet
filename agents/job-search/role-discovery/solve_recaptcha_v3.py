#!/usr/bin/env python3
"""solve_recaptcha_v3.py — CLI bridge so the chain-worker agent can solve a
reCAPTCHA v3 token without writing Python inline.

Designed to be called by the chain worker (an OpenClaw agent driving the
browser tool) between the `detect` browser.act.evaluate step and the
`inject` browser.act.evaluate step. The worker invokes us like:

    .venv/bin/python solve_recaptcha_v3.py \
        --sitekey 6LeFb_YUAA...49Y \
        --page-url https://jobs.ashbyhq.com/openai/.../application \
        --action submit --min-score 0.7 [--enterprise]

Or, equivalently, by piping the detect-JSON to stdin (the same dict
shape that `captcha_presubmit.JS_DETECT_RECAPTCHA_V3` returns) plus a
--fallback-sitekey for tenants where detect missed the loader:

    echo '{"sitekey":"...","page_url":"...","enterprise":false}' | \
        .venv/bin/python solve_recaptcha_v3.py \
            --stdin --fallback-sitekey 6LeFb_... --action submit

Always prints a single JSON line to stdout:
    SUCCESS: {"ok": true, "token": "03A...", "latency_ms": 14823,
              "sitekey": "...", "enterprise": false}
    FAILURE: {"ok": false, "reason": "...", "latency_ms": 187,
              "sitekey": "...", "enterprise": false}

Exit code 0 = solver completed (token returned OR clean disabled).
Exit code 2 = solver attempted but failed.
Exit code 3 = invalid args / no sitekey usable.

The captcha-presubmit driver_exec block uses this script's args.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

# Make sibling modules importable when invoked directly.
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
    ap.add_argument("--sitekey", default=None,
                    help="reCAPTCHA v3 sitekey. If omitted, --stdin or "
                         "--fallback-sitekey must supply one.")
    ap.add_argument("--page-url", default=None,
                    help="The URL the captcha is served on. Required unless "
                         "--stdin provides one.")
    ap.add_argument("--action", default="submit",
                    help="reCAPTCHA action / pageAction param. Default 'submit'.")
    ap.add_argument("--min-score", type=float, default=0.7,
                    help="Minimum acceptable v3 score (passed to CapSolver as hint).")
    ap.add_argument("--enterprise", action="store_true",
                    help="Force the Enterprise endpoint. Default off; auto-detected "
                         "from stdin payload if present.")
    ap.add_argument("--stdin", action="store_true",
                    help="Read a JSON detect-payload from stdin "
                         "(captcha_presubmit.JS_DETECT_RECAPTCHA_V3 shape).")
    ap.add_argument("--fallback-sitekey", default=None,
                    help="Used when neither --sitekey nor stdin sitekey is set "
                         "(e.g. all strict-Ashby tenants share one).")
    args = ap.parse_args()

    detect: dict = {}
    if args.stdin:
        try:
            raw = sys.stdin.read().strip()
            detect = json.loads(raw) if raw else {}
        except Exception as e:  # noqa: BLE001
            _emit({"ok": False, "reason": f"stdin parse failed: {e}",
                   "stage": "stdin"}, 3)

    sitekey = (
        args.sitekey
        or (detect.get("sitekey") if isinstance(detect, dict) else None)
        or args.fallback_sitekey
    )
    page_url = args.page_url or (detect.get("page_url") if isinstance(detect, dict) else None)
    is_enterprise = (
        args.enterprise
        or bool(detect.get("enterprise")) if isinstance(detect, dict) else args.enterprise
    )

    if not sitekey:
        _emit({"ok": False, "reason": "no sitekey provided (args/stdin/fallback all empty)",
               "stage": "input"}, 3)
    if not page_url:
        _emit({"ok": False, "reason": "no page_url provided", "stage": "input",
               "sitekey": sitekey}, 3)

    if not is_enabled():
        _emit({"ok": False, "reason": "ENABLE_CAPSOLVER!=1 or CAPSOLVER_API_KEY unset "
                                       "(after .env fallback). Worker should skip captcha "
                                       "and proceed to Submit.",
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
        if is_enterprise:
            token = client.recaptcha_v3_enterprise(
                sitekey=sitekey,
                page_url=page_url,
                action=args.action,
                min_score=args.min_score,
            )
        else:
            token = client.recaptcha_v3(
                sitekey=sitekey,
                page_url=page_url,
                action=args.action,
                min_score=args.min_score,
            )
    except CapSolverError as e:
        latency_ms = int((time.time() - t0) * 1000)
        _emit({"ok": False, "reason": f"solver error: {type(e).__name__}: {e}",
               "stage": "solve", "latency_ms": latency_ms,
               "sitekey": sitekey, "page_url": page_url,
               "enterprise": is_enterprise}, 2)

    latency_ms = int((time.time() - t0) * 1000)
    _emit({"ok": True, "token": token, "token_len": len(token),
           "latency_ms": latency_ms, "sitekey": sitekey, "page_url": page_url,
           "enterprise": is_enterprise, "action": args.action}, 0)


if __name__ == "__main__":
    main()
