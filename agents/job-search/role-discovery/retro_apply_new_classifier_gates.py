#!/usr/bin/env python3
"""retro_apply_new_classifier_gates.py

Apply the rewritten deterministic skip gates (2026-05-25 policy) against
already-classified open roles. Uses cached JD text from jd_cache/ when
available; if missing, the JD-dependent gates (YOE, non-US) silently
abstain for that row, but title-only and LLM-signal gates still apply.

Usage:
    .venv/bin/python retro_apply_new_classifier_gates.py [--apply]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jd_llm_classifier as J  # noqa: E402

PROJ = HERE.parent
DB = PROJ / "tracker.db"
JD_CACHE = HERE / "jd_cache"
REPORT_DIR = PROJ / "applications"


def load_cached_jd(source_key: str) -> str | None:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", source_key)[:200]
    p = JD_CACHE / f"{safe}.txt"
    if p.exists():
        try:
            return p.read_text()
        except Exception:
            return None
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="Commit flips to tracker.db. Default is dry-run.")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    rows = con.execute("""
        SELECT id, source_key, company, role, loc, app_url, jd_url, status,
               flags, applied_by, llm_yoe_required, llm_is_people_manager,
               llm_seniority, llm_fit_score
          FROM roles
         WHERE applied_by IS NULL
           AND (status = '' OR status IS NULL)
         ORDER BY id
    """).fetchall()

    print(f"[retro] scanning {len(rows)} open unapplied roles")
    flips: list[dict] = []
    flag_counter: collections.Counter[str] = collections.Counter()
    jd_missing = 0

    for r in rows:
        jd_text = load_cached_jd(r["source_key"] or "")
        if jd_text is None:
            jd_missing += 1
        cls = {
            "yoe_required": r["llm_yoe_required"],
            "is_people_manager": bool(r["llm_is_people_manager"]),
            "seniority": r["llm_seniority"] or "unclear",
            "fit_score": r["llm_fit_score"],
        }
        flip = J.maybe_skip(con, r, cls, jd_text, dry_run=True)
        if flip:
            flips.append(flip)
            for f in flip["new_flags"]:
                flag_counter[f] += 1

    print(f"[retro] {len(flips)} roles would flip to skip")
    print(f"[retro] jd-text-missing for {jd_missing}/{len(rows)} rows (yoe/non-us gates silent for those)")
    print(f"[retro] flag breakdown: {dict(flag_counter)}")

    # Per-flag samples
    by_flag: dict[str, list[dict]] = collections.defaultdict(list)
    for f in flips:
        for fl in f["new_flags"]:
            by_flag[fl].append(f)
    for fl, items in by_flag.items():
        print(f"\n== {fl} ({len(items)} rows) sample ==")
        for it in items[:5]:
            print(f"  id={it['id']:>5}  {it['company'][:20]:20s}  {it['role'][:60]:60s}  reasons={it['reasons']}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "apply" if args.apply else "dry-run",
        "total_open": len(rows),
        "jd_missing": jd_missing,
        "would_flip": len(flips),
        "flag_breakdown": dict(flag_counter),
        "flips": flips,
    }
    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / f"_classifier-rewrite-retro-{stamp}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n[retro] wrote report -> {report_path}")

    if not args.apply:
        print("[retro] dry-run mode; no DB writes. Re-run with --apply to commit.")
        return 0

    # --apply: actually flip
    flipped = 0
    for r in rows:
        jd_text = load_cached_jd(r["source_key"] or "")
        cls = {
            "yoe_required": r["llm_yoe_required"],
            "is_people_manager": bool(r["llm_is_people_manager"]),
            "seniority": r["llm_seniority"] or "unclear",
            "fit_score": r["llm_fit_score"],
        }
        flip = J.maybe_skip(con, r, cls, jd_text, dry_run=False)
        if flip:
            flipped += 1
    con.commit()
    print(f"[retro] APPLIED: flipped {flipped} rows to status='skip'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
