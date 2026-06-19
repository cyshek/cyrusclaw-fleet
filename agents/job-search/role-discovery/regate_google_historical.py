"""One-off: re-gate historical Google rows after the 2026-06-08 re-enable.

Cyrus 2026-06-08 (BACKLOG #1): Google discovery was re-enabled. Existing
Google rows that were SKIPPED while the company-blocklist was active must be
re-gated through the now-real gates:
  - title gate  (core.is_qualifying_title)  -> drops Senior/Group/Director/...
  - US location (core.is_us_location)
  - YOE gate    (core.is_qualifying_experience) using a REAL Min-quals floor
    fetched from the Google careers JD detail page (adapters.google).

Two row classes among status='skip' Google rows:
  (1) Google-careers rows  (app_url .../jobs/results/<numeric id>): we fetch
      the JD, parse the Min-quals MAX-year floor, and gate on title+US+YOE.
  (2) LinkedIn-sourced Google rows (app_url linkedin.com/...at-google-...):
      no Google min-quals page to fetch -> gate on title+US with YOE
      unstated (unstated->keep, the standing rule). They'd be re-admitted on
      the next crawl anyway once the blocklist is gone.

KEEP  -> status='' (open queue) + flags 'manual-apply discovery-only'
         (same as tracker_merger uses for google rows) + exp_req updated.
DROP  -> leave status='skip' (untouched queue state).
Either way: stamp an agent_notes breadcrumb.

Status-only + agent_notes + exp_req. No deletes. --apply to write; default
is a dry run.
"""
from __future__ import annotations
import argparse
import re
import sys
import time
import random
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "adapters"))

from tracker_db import connect, today  # noqa: E402
from core import is_qualifying_title, is_us_location, is_qualifying_experience  # noqa: E402
import google as G  # noqa: E402

_NUMERIC_DETAIL_RE = re.compile(r"/jobs/results/(\d{6,})")

GOOGLE_KEEP_FLAGS = "manual-apply discovery-only"


def _is_google_careers(url: str):
    m = _NUMERIC_DETAIL_RE.search(url or "")
    return m.group(1) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="cap rows processed (0=all)")
    args = ap.parse_args()

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, role, loc, status, app_url, exp_req, agent_notes "
        "FROM roles WHERE lower(company)='google' AND status='skip'"
    )
    rows = [dict(r) for r in cur.fetchall()]
    print(f"Found {len(rows)} skipped Google rows.")

    kept = dropped = skipped_junk = fetch_fail = 0
    examples = []
    processed = 0

    for r in rows:
        if args.limit and processed >= args.limit:
            break
        rid = r["id"]
        title = r["role"] or ""
        loc = r["loc"] or ""
        url = r["app_url"] or ""
        jid = _is_google_careers(url)

        # Junk / non-role artifacts (scan-error rows). Leave untouched.
        if title.startswith("(scan-blocked") or not title.strip():
            skipped_junk += 1
            continue

        # Gate 1: title. Cheap, do first to avoid needless fetches.
        title_ok = is_qualifying_title(title)
        us_ok = is_us_location(loc)

        floor = None
        exp_req = r["exp_req"] or "exp:unstated"
        yoe_source = "unstated(no-fetch)"

        if title_ok and us_ok and jid:
            # Only spend a JD fetch on rows that could still KEEP.
            time.sleep(random.uniform(0.5, 1.5))
            try:
                floor, _posted = G._fetch_detail(jid)
                exp_req = G._exp_required_from_floor(floor)
                yoe_source = f"min-quals:{floor}" if floor is not None else "unstated(min-quals)"
            except Exception as e:  # noqa: BLE001
                fetch_fail += 1
                exp_req = "exp:unstated"
                yoe_source = f"unstated(fetch-fail:{type(e).__name__})"
        elif title_ok and us_ok and not jid:
            # LinkedIn-sourced Google row: no Google min-quals to fetch.
            yoe_source = "unstated(linkedin-src)"

        yoe_ok = is_qualifying_experience(exp_req)
        keep = bool(title_ok and us_ok and yoe_ok)

        floor_str = floor if floor is not None else "unstated"
        verdict = "KEEP" if keep else "DROP"
        reason = ""
        if not title_ok:
            reason = "title-gate"
        elif not us_ok:
            reason = "non-us"
        elif not yoe_ok:
            reason = f"yoe>={4}"
        breadcrumb = (f"GOOGLE-REGATE {today()} floor={floor_str} "
                      f"{verdict}" + (f"({reason})" if reason else ""))

        if len(examples) < 8 and title_ok and us_ok:
            examples.append(f"  [{verdict}] {title[:54]!r} floor={floor_str} src={yoe_source}")

        if keep:
            kept += 1
            if args.apply:
                new_notes = ((r["agent_notes"] or "").strip() + " " + breadcrumb).strip()
                cur.execute(
                    "UPDATE roles SET status='', flags=?, exp_req=?, agent_notes=?, last_seen=? WHERE id=?",
                    (GOOGLE_KEEP_FLAGS, exp_req, new_notes, today(), rid),
                )
        else:
            dropped += 1
            if args.apply:
                # Leave status='skip'; just record exp_req (if fetched) + breadcrumb.
                new_notes = ((r["agent_notes"] or "").strip() + " " + breadcrumb).strip()
                cur.execute(
                    "UPDATE roles SET exp_req=?, agent_notes=?, last_seen=? WHERE id=?",
                    (exp_req, new_notes, today(), rid),
                )
        processed += 1

    if args.apply:
        conn.commit()
    conn.close()

    print(f"\n{'APPLIED' if args.apply else 'DRY RUN'} results:")
    print(f"  Processed:        {processed}")
    print(f"  KEPT (-> open):   {kept}")
    print(f"  DROPPED (skip):   {dropped}")
    print(f"  Junk left alone:  {skipped_junk}")
    print(f"  Fetch failures:   {fetch_fail}")
    print("\nExamples (title+US passed; verdict by YOE):")
    for e in examples:
        print(e)


if __name__ == "__main__":
    main()
