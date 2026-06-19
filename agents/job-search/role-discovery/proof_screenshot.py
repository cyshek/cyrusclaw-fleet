#!/usr/bin/env python3
"""
proof_screenshot.py — capture a LIVE pre-submit screenshot for queued roles.

Reads outputs/proof/screenshot_queue.json (written by proof_archiver.py),
re-drives the apply form for each pending role up to (but NOT including) the
final submit, screenshots the filled page, saves it into that role's proof dir,
and marks the queue entry done.

SAFETY (hard rules):
  - NEVER clicks the final submit / verify / confirm button.
  - Only handles ATSes we can re-render read-only from meta.json apply_url.
  - On ANY uncertainty (OTP gate already showing, anti-bot wall, ambiguous
    submit state) it ABORTS that role with status=skipped+reason, never submits.
  - Best-effort: a role we can't screenshot stays resume+fields proof only.

This is intentionally a SEPARATE step from archiving so the (cheap, reliable)
resume+fields archive never depends on the (browser, flaky) screenshot path.

Usage:
    python3 proof_screenshot.py --limit 3      # process up to 3 pending
    python3 proof_screenshot.py --role-id 2174 # one specific role
    python3 proof_screenshot.py --list         # show pending queue, do nothing

NOTE: live-screenshot driving is implemented against the OpenClaw browser and
the existing greenhouse/ashby fill helpers. Until that wiring is validated
end-to-end, run with --list / --dry-run; the archive (resume+fields) is already
complete and independent of this step.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
PROOF_DIR = os.path.abspath(os.path.join(PROJ, "..", "..", "outputs", "proof"))
QUEUE = os.path.join(PROOF_DIR, "screenshot_queue.json")


def load_queue():
    if not os.path.exists(QUEUE):
        return []
    try:
        return json.load(open(QUEUE))
    except Exception:
        return []


def save_queue(q):
    tmp = QUEUE + ".tmp"
    json.dump(q, open(tmp, "w"), indent=2)
    os.replace(tmp, QUEUE)


def pending(q):
    return [x for x in q if x.get("status") not in ("done", "skipped")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--role-id", type=int)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    q = load_queue()
    pend = pending(q)
    if args.role_id:
        pend = [x for x in pend if x["roleid"] == args.role_id]

    if args.list:
        print(f"screenshot queue: {len(load_queue())} total, {len(pending(load_queue()))} pending")
        for x in pending(load_queue()):
            print(f"  [{x['seq']}] {x['company']} {x['roleid']} -> {x['dir']}")
        return

    todo = pend[: args.limit]
    if not todo:
        print("proof_screenshot: nothing pending")
        return

    # Live browser driving is gated behind validation. For now this step is a
    # safe no-op that records intent; the resume+fields archive stands alone.
    # When the OpenClaw-browser re-fill path is validated, replace this block
    # with: open apply_url -> fill from prefill.json -> attach resume ->
    # screenshot pre-submit -> save <dir>/filled-form.png. NEVER submit.
    for x in todo:
        print(f"proof_screenshot: would capture {x['company']} {x['roleid']} "
              f"(dir={x['dir']}) [NOT YET WIRED]")
        if not args.dry_run:
            for e in q:
                if e["roleid"] == x["roleid"]:
                    e["status"] = "pending"  # keep pending until live wiring lands
                    e["last_attempt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    e["note"] = "screenshot path not yet wired; resume+fields proof present"
    if not args.dry_run:
        save_queue(q)


if __name__ == "__main__":
    main()
