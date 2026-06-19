"""One-off / idempotent: drop Google rows that the LLM read as YOE-knockouts but
the 2026-06-08 historical regate KEPT on an "unstated YOE -> keep" fallback.

Context
-------
`regate_google_historical.py` (2026-06-08) re-opened skipped Google rows after
the company-blocklist was lifted. For LinkedIn-sourced Google rows it could NOT
fetch a Google min-quals page, so it gated on title+US with YOE *unstated*
(unstated -> KEEP). Result: rows whose REAL JD requires 5-10 YOE were left as
`status=''` (open / manual-apply discovery-only) -- false-keeps that pollute the
open+manual queue and resurface in every triage.

But the LLM classifier (`jd_llm_classifier`) independently parsed each real JD
and recorded `llm_yoe_required`. The canonical YOE doctrine
(`core.is_qualifying_experience`, Cyrus 2026-05-06) is:
    min stated >= 4 yrs -> DROP   (candidate has 3 YOE).

So any open Google row with `llm_yoe_required >= 4` is a genuine YOE knockout
that should be `status='skip'`, exactly as the gate would have dropped it had a
min-quals floor been available.

Scope (deliberately narrow & safe)
-----------------------------------
- ONLY rows: lower(company)='google' AND status='' (the regate KEEP state)
             AND llm_yoe_required IS NOT NULL AND llm_yoe_required >= MIN_DROP_YOE.
- Action: status -> 'skip', append flag 'llm-yoe-knockout-regate' (idempotent),
          append an agent_notes breadcrumb. Nothing else touched.
- Rows with llm_yoe_required <= 3 (genuine fits) are LEFT ALONE -- they stay
  'manual-apply discovery-only' (correct: Google has no auto-submit ATS, so the
  manual-apply packet is their channel).

Idempotent: re-running finds nothing new (already skipped). Dry-run by default.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from tracker_db import connect, today  # noqa: E402

# Canonical YOE gate: min stated >= 4 -> DROP (candidate has 3 YOE).
MIN_DROP_YOE = 4
KNOCKOUT_FLAG = "llm-yoe-knockout-regate"


def select_targets(conn):
    cur = conn.execute(
        "SELECT id, role, exp_req, llm_yoe_required, llm_fit_score, flags, agent_notes "
        "FROM roles "
        "WHERE lower(company)='google' AND COALESCE(status,'')='' "
        "  AND llm_yoe_required IS NOT NULL AND llm_yoe_required >= ? "
        "ORDER BY llm_yoe_required DESC, id",
        (MIN_DROP_YOE,),
    )
    return [dict(r) for r in cur.fetchall()]


def _add_flag(flags: str | None, flag: str) -> str:
    parts = (flags or "").split()
    if flag not in parts:
        parts.append(flag)
    return " ".join(parts).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write changes (default: dry run)")
    args = ap.parse_args()

    conn = connect()
    targets = select_targets(conn)
    print(f"Found {len(targets)} open Google rows with llm_yoe_required >= {MIN_DROP_YOE} "
          f"(candidate has 3 YOE -> DROP).")
    for r in targets:
        print(f"  [{r['id']}] yoe={r['llm_yoe_required']} fit={r['llm_fit_score']} "
              f"exp_req={r['exp_req']!r} :: {(r['role'] or '')[:54]!r}")

    if not targets:
        print("\nNothing to do (idempotent: already reconciled).")
        conn.close()
        return

    if not args.apply:
        print(f"\nDRY RUN -- would flip {len(targets)} rows to status='skip' "
              f"(+flag '{KNOCKOUT_FLAG}'). Re-run with --apply to write.")
        conn.close()
        return

    crumb = f"LLM-YOE-KNOCKOUT-REGATE {today()} (yoe>={MIN_DROP_YOE}, cand=3 -> skip)"
    n = 0
    for r in targets:
        new_flags = _add_flag(r["flags"], KNOCKOUT_FLAG)
        new_notes = ((r["agent_notes"] or "").strip() + " " + crumb).strip()
        conn.execute(
            "UPDATE roles SET status='skip', flags=?, agent_notes=?, last_seen=? WHERE id=?",
            (new_flags, new_notes, today(), r["id"]),
        )
        n += 1
    conn.commit()
    conn.close()
    print(f"\nAPPLIED -- flipped {n} rows to status='skip' (+flag '{KNOCKOUT_FLAG}').")


if __name__ == "__main__":
    main()
