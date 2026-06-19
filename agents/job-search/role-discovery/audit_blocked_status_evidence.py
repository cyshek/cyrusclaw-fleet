"""Audit blocked rows whose `block_reason` LIES vs. the on-disk evidence.

Why this exists (the recurring waste this kills)
-------------------------------------------------
Three+ times in the week of 2026-06-08 an autonomous tick burned time "fixing"
a non-bug because a stale auto-banked `block_reason` claimed an ENGINE GAP that
the actual on-disk artifacts disproved:
  - EliseAI 2727 / Dash0 comp cohort: block_reason said "comp free-text ABSENT
    from dryrun (field-walker gap)"; the cached dryrun showed the field PRESENT,
    filled, ready_to_submit. (DEBUNKED 2026-06-08.)
  - EliseAI 2725: block_reason said "office multiselect needs option-aware
    picker"; STATUS.md said `submitted` with a real confirmation_text — it was a
    genuine application sitting as `blocked`. (RECLASSIFIED 2026-06-09.)
  - Dash0 2758: block_reason said "field-DISCOVERY gap / field-walker skips
    custom selects, ABSENT from dryrun"; the dryrun was ready_to_submit=True,
    blockers=[], both "absent" fields present+filled. (RECLASSIFIED 2026-06-09.)

Each one cost a forensic dig. This script makes that dig a single command so a
future tick spots the lie in seconds instead of re-investigating from scratch.

What it does (READ-ONLY by default — never writes the DB)
---------------------------------------------------------
For every `status='blocked'` row it:
  1. resolves the row's app_url to an ATS job id (Ashby/Greenhouse),
  2. finds the matching `applications/submitted/<slug>/STATUS.md` (the
     authoritative submit signal) and the cached
     `applications/dryrun/<slug>.json` (the authoritative prep signal),
  3. classifies the row into one of:
       SUBMITTED_BUT_BLOCKED   STATUS.md says submitted  -> should be applied
       READY_BUT_BLOCKED_AS_ENGINE_GAP
                               dryrun ready_to_submit=True & blockers=[] BUT the
                               block_reason claims an engine/field gap -> phantom
       PREP_READY_AWAITING_SUBMIT
                               STATUS=PREP-READY and reason is a known infra wall
                               (residential/score-gate/applimit) -> consistent, OK
       CONSISTENT / NO_EVIDENCE
  4. prints the LIE classes loudly so they can be reclassified by judgement.

Deliberately does NOT auto-write: some "STATUS says submitted" rows were
*intentionally* relabeled blocked (e.g. Baseten/Mercor residential proof rows
with response_status=NULL = never server-confirmed). Reclassification stays a
decisive human/agent call; this tool just surfaces candidates with evidence.

Run:  python3 audit_blocked_status_evidence.py            # full report
      python3 audit_blocked_status_evidence.py --lies     # only the lie classes
      python3 audit_blocked_status_evidence.py --json      # machine-readable
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from tracker_db import connect, DB_PATH  # noqa: E402

# applications/ lives next to tracker.db (project root), not under role-discovery.
PROJECT_ROOT = DB_PATH.parent
SUBMITTED_DIR = PROJECT_ROOT / "applications" / "submitted"
DRYRUN_DIR = PROJECT_ROOT / "applications" / "dryrun"

# A block_reason that asserts a CODE/engine/field problem (something a future
# tick would try to "fix"). If the evidence contradicts it, that's the lie.
ENGINE_GAP_MARKERS = (
    "field-walker",
    "field-discovery",
    "field discovery",
    "absent from dryrun",
    "absent from the dryrun",
    "no label_rule",
    "no labelrule",
    "label-gap",
    "label gap",
    "needs option-aware",
    "needs field-walker",
    "engine-edge",
    "engine fix",
    "engine gap",
    "missing entry",
    "prep-blocker",
    "no plan emitted",
)

# Reasons that are genuine NON-engine infra walls — a PREP-READY row carrying one
# of these is internally consistent (prep done, blocked on egress/time), NOT a lie.
INFRA_WALL_MARKERS = (
    "applimit",
    "score-gate",
    "score gate",
    "proxy-ip-walled",
    "residential",
    "hcaptcha",
    "datadome",
    "hard-wall",
    "sso",
    "account",
    "resumewall",
    "filestack",
)

ASHBY_RE = re.compile(r"ashbyhq\.com/([^/]+)/([0-9a-f-]{36})", re.I)
GH_TOKEN_RE = re.compile(r"[?&](?:gh_jid|token|for)=([0-9a-zA-Z_-]+)", re.I)


def job_keys_from_url(url: str):
    """Return candidate job-id substrings to match a submitted/dryrun dir name."""
    keys = []
    if not url:
        return keys
    m = ASHBY_RE.search(url)
    if m:
        keys.append(m.group(2))            # the 36-char Ashby jid
    for m in GH_TOKEN_RE.finditer(url):
        keys.append(m.group(1))
    return keys


def _first_nonempty_line(path: Path) -> str:
    try:
        for line in path.read_text(errors="replace").splitlines():
            if line.strip():
                return line.strip()
    except OSError:
        pass
    return ""


def find_status_md(keys, submitted_dir: Path = SUBMITTED_DIR):
    for k in keys:
        for d in glob.glob(str(submitted_dir / ("*%s*" % k))):
            st = Path(d) / "STATUS.md"
            if st.exists():
                return st
    return None


def find_dryrun(keys, dryrun_dir: Path = DRYRUN_DIR):
    for k in keys:
        hits = glob.glob(str(dryrun_dir / ("*%s*.json" % k)))
        if hits:
            return Path(hits[0])
    return None


def status_says_submitted(status_first_line: str) -> bool:
    s = (status_first_line or "").lower()
    return s.startswith("submitted") or "status: submitted" in s or "submitted (" in s


def status_says_prep_ready(status_first_line: str) -> bool:
    return (status_first_line or "").lower().startswith("prep-ready")


def dryrun_ready(dryrun_path: Path):
    """Return (ready_to_submit: bool|None, blockers: list|None)."""
    try:
        d = json.loads(dryrun_path.read_text())
    except (OSError, ValueError):
        return None, None
    if not isinstance(d, dict):
        return None, None
    return d.get("ready_to_submit"), d.get("blockers")


def reason_claims_engine_gap(block_reason: str) -> bool:
    b = (block_reason or "").lower()
    return any(m in b for m in ENGINE_GAP_MARKERS)


def reason_is_infra_wall(block_reason: str) -> bool:
    b = (block_reason or "").lower()
    return any(m in b for m in INFRA_WALL_MARKERS)


def classify(row: dict) -> dict:
    """Pure classifier over a row dict (+ resolved evidence). Testable."""
    keys = job_keys_from_url(row.get("app_url") or "")
    status_md = row.get("_status_first_line")          # injected (real or test)
    ready = row.get("_dryrun_ready")
    blockers = row.get("_dryrun_blockers")
    br = row.get("block_reason") or ""

    verdict = "CONSISTENT"
    detail = ""

    if status_says_submitted(status_md or ""):
        verdict = "SUBMITTED_BUT_BLOCKED"
        detail = "STATUS.md reports submitted; row is blocked -> likely a real application miscounted."
    elif ready is True and (blockers is not None and len(blockers) == 0) and reason_claims_engine_gap(br):
        verdict = "READY_BUT_BLOCKED_AS_ENGINE_GAP"
        detail = "dryrun ready_to_submit=True, blockers=[]; block_reason claims an engine/field gap -> phantom."
    elif status_says_prep_ready(status_md or "") and reason_claims_engine_gap(br) and not reason_is_infra_wall(br):
        verdict = "PREPREADY_BUT_BLOCKED_AS_ENGINE_GAP"
        detail = "STATUS=PREP-READY but block_reason claims an engine gap (not an infra wall) -> suspect phantom."
    elif status_says_prep_ready(status_md or "") and reason_is_infra_wall(br):
        verdict = "PREP_READY_AWAITING_SUBMIT"
        detail = "PREP-READY + infra wall reason -> internally consistent (awaiting egress/time), not a lie."
    elif not keys or (status_md is None and ready is None):
        verdict = "NO_EVIDENCE"
        detail = "no STATUS.md / dryrun artifact resolvable from app_url."

    out = dict(row)
    out["_keys"] = keys
    out["verdict"] = verdict
    out["verdict_detail"] = detail
    return out


LIE_VERDICTS = {
    "SUBMITTED_BUT_BLOCKED",
    "READY_BUT_BLOCKED_AS_ENGINE_GAP",
    "PREPREADY_BUT_BLOCKED_AS_ENGINE_GAP",
}


def audit(conn):
    rows = conn.execute(
        "SELECT id, company, role, app_url, status, response_status, block_reason "
        "FROM roles WHERE status='blocked'"
    ).fetchall()
    results = []
    for r in rows:
        row = dict(r)
        keys = job_keys_from_url(row.get("app_url") or "")
        st = find_status_md(keys)
        dr = find_dryrun(keys)
        row["_status_first_line"] = _first_nonempty_line(st) if st else None
        row["_status_path"] = str(st) if st else None
        if dr:
            ready, blockers = dryrun_ready(dr)
            row["_dryrun_ready"] = ready
            row["_dryrun_blockers"] = blockers
            row["_dryrun_path"] = str(dr)
        results.append(classify(row))
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lies", action="store_true", help="only show the lie verdict classes")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    conn = connect()
    results = audit(conn)
    conn.close()

    if args.json:
        slim = [
            {k: v for k, v in r.items() if not k.startswith("_dryrun_blockers")}
            for r in results
        ]
        print(json.dumps(slim, indent=2, default=str))
        return

    from collections import Counter
    counts = Counter(r["verdict"] for r in results)
    print("Blocked-row evidence audit (%d blocked rows):" % len(results))
    for v, n in counts.most_common():
        tag = "  <-- LIE" if v in LIE_VERDICTS else ""
        print("  %-36s %d%s" % (v, n, tag))

    show = [r for r in results if (r["verdict"] in LIE_VERDICTS)] if args.lies else results
    show = [r for r in show if r["verdict"] != "CONSISTENT"] if not args.lies else show
    if show:
        print("\nDetails:")
        for r in sorted(show, key=lambda x: (x["verdict"] not in LIE_VERDICTS, x["id"])):
            print("  [%s] id=%s %s :: %s" % (
                r["verdict"], r["id"], (r["company"] or "")[:18], r["verdict_detail"]))
            if r["verdict"] in LIE_VERDICTS:
                print("        block_reason: %s" % ((r.get("block_reason") or "")[:110]))
                if r.get("_status_path"):
                    print("        evidence STATUS: %s :: %s" % (
                        r["_status_path"], (r.get("_status_first_line") or "")[:60]))
                if r.get("_dryrun_path"):
                    print("        evidence dryrun: %s (ready=%s)" % (
                        r["_dryrun_path"], r.get("_dryrun_ready")))
    if args.lies and not show:
        print("\nNo lie-class rows found (block_reasons consistent with on-disk evidence).")


if __name__ == "__main__":
    main()
