#!/usr/bin/env python3
"""backfill_stripe_exp.py

Backfill exp_req + LLM classification for every Stripe role in tracker.db.

Why: 9 Stripe roles got into the queue with `exp_req='exp:unstated'` and NULL
llm_* columns — never classified. Cyrus's hard filter is >=4 YOE => skip,
people-manager => skip, senior+ => skip, fit<40 => skip. Several of these
already auto-submitted today (1019/1049/1055/1171/1175/1177) — they are kept
as `applied` (NEVER touch applied_by/applied_on), but their exp_req + llm_*
columns are updated for diagnostic record.

Pipeline (per Stripe row, scoped by `company='Stripe'`):
  1. Extract gh_jid from app_url / jd_url (Stripe URL forms:
     stripe.com/jobs/search?gh_jid=<jid>,
     stripe.com/jobs/listing/<slug>/<jid>/apply)
     If only a linkedin source_key is present, fall back to the jd_url or
     app_url for the gh_jid extraction.
  2. Fetch JD via https://boards-api.greenhouse.io/v1/boards/stripe/jobs/<jid>
  3. Re-run parse_experience(jd) -> new exp_req (UPDATE if changed)
  4. Pre-seed jd_cache/<source_key>.txt so the LLM classifier reuses our body
     (Stripe URLs aren't recognized by the generic fetcher).
  5. Invoke jd_llm_classifier on the role (--role-id <id> --force) so it
     writes llm_classified_at/llm_yoe_required/llm_is_people_manager/
     llm_seniority/llm_fit_score/llm_reason.
     - For NOT-yet-applied rows the classifier's maybe_skip() will flip them
       to status='skip', flags+='llm-overreach' per Cyrus's rule.
     - For applied rows the classifier writes llm_* fields but leaves status
       and applied_by untouched (maybe_skip short-circuits on applied_by).

Outputs:
  applications/_stripe-backfill-2026-05-24.json
"""
from __future__ import annotations
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(HERE))

from core import parse_experience, is_overreach  # noqa: E402

DB = PROJECT / "tracker.db"
LOG_PATH = PROJECT / "applications" / "_stripe-backfill-2026-05-24.json"
JD_CACHE = HERE / "jd_cache"
JD_CACHE.mkdir(exist_ok=True)


def extract_gh_jid(*urls: str) -> str | None:
    for u in urls:
        if not u:
            continue
        m = re.search(r"gh_jid=(\d+)", u)
        if m:
            return m.group(1)
        m = re.search(r"stripe\.com/jobs/listing/[^/]+/(\d+)", u)
        if m:
            return m.group(1)
    return None


def fetch_stripe_jd(jid: str) -> tuple[str, str, str]:
    """Return (title, jd_text_plain, content_html)."""
    api = f"https://boards-api.greenhouse.io/v1/boards/stripe/jobs/{jid}"
    r = requests.get(api, headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    d = r.json()
    title = d.get("title", "")
    raw_html = d.get("content", "") or ""
    # Stripe returns HTML-encoded HTML — single unescape gets real HTML
    import html as _html
    real_html = _html.unescape(raw_html)
    # Strip tags for parse_experience / cache body
    txt = re.sub(r"<[^>]+>", " ", real_html)
    txt = re.sub(r"\s+", " ", txt).strip()
    return title, txt, raw_html


def cache_jd(source_key: str, title: str, jd_text: str) -> None:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", source_key)[:200]
    body = f"# {title}\n\n{jd_text}"
    (JD_CACHE / f"{safe}.txt").write_text(body)
    (JD_CACHE / f"{safe}.meta").write_text("greenhouse")


def run_llm_classifier(role_id: int) -> dict:
    """Invoke jd_llm_classifier as a subprocess with --role-id --force.
    Returns parsed summary dict from log line or stdout."""
    py = HERE / ".venv" / "bin" / "python"
    cmd = [str(py), str(HERE / "jd_llm_classifier.py"),
           "--role-id", str(role_id), "--force", "--sleep", "0"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return {"rc": out.returncode, "stdout": out.stdout[-2000:],
                "stderr": out.stderr[-500:]}
    except subprocess.TimeoutExpired:
        return {"rc": -1, "stdout": "", "stderr": "TIMEOUT"}


def main():
    if not DB.exists():
        print(f"ERR no tracker.db at {DB}", file=sys.stderr)
        return 2

    # Backup
    bak = DB.with_suffix(".db.bak.20260524-stripe-backfill")
    if not bak.exists():
        shutil.copy2(DB, bak)
        print(f"backed up tracker.db -> {bak.name}")
    else:
        print(f"backup already exists: {bak.name}")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT id, source_key, company, role, status, applied_by, applied_on,
               exp_req, flags, app_url, jd_url, llm_classified_at
        FROM roles
        WHERE company='Stripe'
        ORDER BY id
    """).fetchall()
    print(f"Stripe rows total: {len(rows)}")

    stripe_open_before = sum(
        1 for r in rows
        if (r["status"] is None or r["status"] == "") and r["applied_by"] is None
    )
    print(f"open before (status NULL/'' AND applied_by NULL): {stripe_open_before}")

    results = []  # one entry per row
    for r in rows:
        rid = r["id"]
        jid = extract_gh_jid(r["app_url"] or "", r["jd_url"] or "", r["source_key"] or "")
        entry = {
            "role_id": rid,
            "title": r["role"],
            "source_key": r["source_key"],
            "status_before": r["status"],
            "applied_by": r["applied_by"],
            "applied_on": r["applied_on"],
            "exp_req_before": r["exp_req"],
            "flags_before": r["flags"],
            "gh_jid": jid,
        }
        if not jid:
            print(f"  [{rid}] no gh_jid in URLs/source_key; skip JD fetch")
            entry["error"] = "no_gh_jid"
            results.append(entry)
            continue
        try:
            title, jd_text, _html = fetch_stripe_jd(jid)
        except Exception as e:
            print(f"  [{rid}] fetch failed: {e}")
            entry["error"] = f"fetch:{type(e).__name__}:{str(e)[:120]}"
            results.append(entry)
            continue
        if len(jd_text) < 200:
            print(f"  [{rid}] JD too short ({len(jd_text)})")
            entry["error"] = "jd_too_short"
            results.append(entry)
            continue

        # 1. exp_req update
        new_exp = parse_experience(jd_text)
        entry["exp_req_after"] = new_exp
        if new_exp != (r["exp_req"] or ""):
            conn.execute("UPDATE roles SET exp_req=? WHERE id=?", (new_exp, rid))
            conn.commit()
            print(f"  [{rid}] exp_req: {r['exp_req']} -> {new_exp}")
        # 2. is_overreach diagnostic (yoe_cap=4)
        ovr, reason = is_overreach(new_exp, jd_text, r["role"], yoe_cap=4)
        entry["overreach_yoe_cap4"] = {"hit": ovr, "reason": reason}

        # 3. Pre-seed JD cache for the classifier (under source_key).
        cache_jd(r["source_key"] or f"stripe-{jid}", title, jd_text)

        # 4. LLM classify (only for rows we have not classified, OR always
        # via --force so re-runs are idempotent).
        is_open = (r["status"] is None or r["status"] == "") and r["applied_by"] is None
        print(f"  [{rid}] {r['role'][:48]:48s} | open={is_open} | exp={new_exp}")
        clsres = run_llm_classifier(rid)
        entry["llm_run"] = clsres
        # Read back llm_* columns to capture result
        post = conn.execute(
            "SELECT status, flags, llm_classified_at, llm_yoe_required, "
            "llm_is_people_manager, llm_seniority, llm_fit_score, llm_reason "
            "FROM roles WHERE id=?", (rid,)
        ).fetchone()
        entry["after"] = dict(post) if post else None
        entry["status_after"] = post["status"] if post else None

        # Augmented backfill flag on rows we touched in either path
        existing_flags = (post["flags"] if post else "") or ""
        parts = [f for f in re.split(r"[;,\s]+", existing_flags) if f]
        if "auto-skip-stripe-backfill" not in parts and post and post["status"] == "skip":
            # If classifier flipped to skip, add the backfill provenance flag
            parts.append("auto-skip-stripe-backfill")
            new_flags = ";".join(parts)
            conn.execute("UPDATE roles SET flags=? WHERE id=?", (new_flags, rid))
            conn.commit()
            entry["after"]["flags"] = new_flags

        results.append(entry)
        time.sleep(0.3)

    # Final counts
    after_rows = conn.execute("""
        SELECT id, status, applied_by FROM roles WHERE company='Stripe'
    """).fetchall()
    stripe_open_after = sum(1 for r in after_rows
                            if (r["status"] is None or r["status"] == "")
                            and r["applied_by"] is None)
    skipped = sum(1 for r in results
                  if r.get("status_before") in (None, "") and r.get("applied_by") is None
                  and r.get("status_after") == "skip")

    # Survivor status for the two key open rows
    def status_of(rid: int) -> dict:
        x = conn.execute(
            "SELECT id, status, exp_req, llm_yoe_required, llm_is_people_manager, "
            "llm_seniority, llm_fit_score, llm_reason, flags "
            "FROM roles WHERE id=?", (rid,)
        ).fetchone()
        return dict(x) if x else None

    s1180 = status_of(1180)
    s1249 = status_of(1249)

    # Retrospective on the 6 already-submitted today
    submitted_today_ids = [1019, 1049, 1055, 1171, 1175, 1177]
    submitted_yoe = {}
    for sid in submitted_today_ids:
        x = conn.execute(
            "SELECT id, role, exp_req, llm_yoe_required, llm_is_people_manager, "
            "llm_seniority, llm_fit_score, llm_reason "
            "FROM roles WHERE id=?", (sid,)
        ).fetchone()
        if x:
            submitted_yoe[sid] = dict(x)

    summary = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stripe_total_rows": len(rows),
        "stripe_open_before": stripe_open_before,
        "stripe_open_after": stripe_open_after,
        "skipped": skipped,
        "remaining_open": stripe_open_after,
        "row_1180": s1180,
        "row_1249": s1249,
        "submitted_today_diagnostics": submitted_yoe,
        "results": results,
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\nlog -> {LOG_PATH}")
    print(f"stripe_open_before={stripe_open_before} skipped={skipped} "
          f"remaining_open={stripe_open_after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
