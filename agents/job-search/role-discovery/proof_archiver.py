#!/usr/bin/env python3
"""
proof_archiver.py — maintain a browsable proof archive of submitted applications.

Cyrus directive (2026-06-02):
  - Save proof for EVERY submitted role: tailored resume (PDF+DOCX) + filled fields
    (prefill.json) + cover answers + JD + meta. (resume+fields always)
  - Flag every 5th submission (by chronological sequence) for a LIVE pre-submit
    SCREENSHOT (captured separately by proof_screenshot step — see screenshot_queue).
  - NEVER paste proof into the Discord channel. This script only writes to disk:
        outputs/proof/<YYYY-MM-DD>-<companyslug>-<roleid>/
        outputs/proof/INDEX.md            (newest-first browsable index)
        outputs/proof/.proof_state.json   (idempotency + sequence counter)
        outputs/proof/screenshot_queue.json (roles flagged for live screenshot)

Idempotent: safe to run after every submit / on a cron. Re-runs only add NEW
submitted rows; existing proof dirs are left untouched unless --refresh.

Usage:
    python3 proof_archiver.py            # reconcile, archive new submissions
    python3 proof_archiver.py --refresh  # re-copy artifacts even if dir exists
    python3 proof_archiver.py --dry-run  # show what would happen, write nothing
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)                      # .../projects/job-search
DB = os.path.join(PROJ, "tracker.db")
SUBMITTED_DIR = os.path.join(PROJ, "applications", "submitted")
PROOF_DIR = os.path.join(PROJ, "..", "..", "outputs", "proof")  # workspace/outputs/proof
PROOF_DIR = os.path.abspath(PROOF_DIR)
STATE_PATH = os.path.join(PROOF_DIR, ".proof_state.json")
INDEX_PATH = os.path.join(PROOF_DIR, "INDEX.md")
SCREENSHOT_QUEUE = os.path.join(PROOF_DIR, "screenshot_queue.json")

SCREENSHOT_EVERY = 5  # live screenshot sampled on every Nth submission

# artifacts copied verbatim from a packet (if present)
COPY_NAMES = ["JD.md", "meta.json", "prefill.json", "cover_answers.md",
              "tailoring-notes.md", "STATUS.md"]


def slugify(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown"


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            return json.load(open(STATE_PATH))
        except Exception:
            pass
    return {"seq": 0, "archived": {}}  # archived: roleid -> {dir, seq, screenshot}


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(obj, open(tmp, "w"), indent=2)
    os.replace(tmp, path)


def find_packet(roleid: int, company: str, meta_jid: str | None) -> str | None:
    """Locate the applications/submitted/<slug>/ dir for a submitted role.
    Strategy: scan packets, match by meta.json gh_jid OR company slug heuristics.
    The packet dir name is usually <companyslug>-<jid>."""
    if not os.path.isdir(SUBMITTED_DIR):
        return None
    cands = []
    cslug = slugify(company)
    for name in os.listdir(SUBMITTED_DIR):
        p = os.path.join(SUBMITTED_DIR, name)
        if not os.path.isdir(p):
            continue
        metap = os.path.join(p, "meta.json")
        meta = {}
        if os.path.exists(metap):
            try:
                meta = json.load(open(metap))
            except Exception:
                meta = {}
        # strongest signal: meta company slug match
        mcomp = slugify(meta.get("company", ""))
        score = 0
        if mcomp and mcomp == cslug:
            score += 3
        elif cslug and (cslug in name):
            score += 2
        if meta_jid and meta.get("gh_jid") and str(meta["gh_jid"]) == str(meta_jid):
            score += 5
        if score > 0:
            cands.append((score, p))
    if not cands:
        return None
    cands.sort(reverse=True)
    return cands[0][1]


def resume_files(packet: str) -> list[str]:
    out = []
    for f in os.listdir(packet):
        if re.search(r"resume.*\.(pdf|docx)$", f, re.I):
            out.append(os.path.join(packet, f))
    return out


def archive_role(row, seq, state, dry, refresh):
    roleid, company, role, status, applied_by, applied_on = row
    meta_jid = None
    packet = find_packet(roleid, company, None)
    if packet:
        mp = os.path.join(packet, "meta.json")
        if os.path.exists(mp):
            try:
                meta_jid = json.load(open(mp)).get("gh_jid")
            except Exception:
                pass
    date = (applied_on or datetime.now(timezone.utc).strftime("%Y-%m-%d"))[:10]
    dirname = f"{date}-{slugify(company)}-{roleid}"
    dest = os.path.join(PROOF_DIR, dirname)
    want_shot = (seq % SCREENSHOT_EVERY == 0)

    rec = {"roleid": roleid, "company": company, "role": role,
           "status": status, "applied_by": applied_by, "applied_on": applied_on,
           "seq": seq, "dir": dirname, "packet": packet,
           "screenshot": "pending" if want_shot else "n/a",
           "has_resume": False}

    if dry:
        rec["_dry"] = True
        return rec

    os.makedirs(dest, exist_ok=True)
    copied = []
    if packet and os.path.isdir(packet):
        for rf in resume_files(packet):
            shutil.copy2(rf, os.path.join(dest, os.path.basename(rf)))
            copied.append(os.path.basename(rf))
            rec["has_resume"] = True
        for nm in COPY_NAMES:
            sp = os.path.join(packet, nm)
            if os.path.exists(sp):
                shutil.copy2(sp, os.path.join(dest, nm))
                copied.append(nm)
    # write a small per-role summary
    summary = {
        "roleid": roleid, "company": company, "role": role,
        "applied_on": applied_on, "applied_by": applied_by, "seq": seq,
        "packet_source": packet, "copied": copied,
        "screenshot": rec["screenshot"],
        "note": "Proof artifacts for spot-checking submitted application. "
                "resume = the tailored doc actually attached; prefill.json = exact form fields filled.",
    }
    save_json(os.path.join(dest, "PROOF.json"), summary)
    rec["copied"] = copied
    return rec


def write_index(records):
    recs = sorted(records, key=lambda r: (r.get("applied_on") or "", r["seq"]), reverse=True)
    lines = ["# Proof Archive — submitted applications", "",
             f"_Auto-maintained by `proof_archiver.py`. Last run: {datetime.now(timezone.utc).isoformat(timespec='seconds')}._", "",
             "Resume + filled-fields saved for EVERY submission. Live pre-submit screenshot sampled every "
             f"{SCREENSHOT_EVERY}th role (look for `screenshot: pending/done`).", "",
             "**Not posted to channel** — Cyrus shares on request only.", "",
             f"Total archived: **{len(records)}**", "",
             "| # | Date | Company | Role | id | Resume | Screenshot | Folder |",
             "|---|------|---------|------|----|--------|-----------|--------|"]
    for r in recs:
        lines.append("| {seq} | {date} | {co} | {role} | {rid} | {res} | {shot} | `{dir}` |".format(
            seq=r["seq"], date=(r.get("applied_on") or "?")[:10],
            co=r["company"], role=(r["role"] or "")[:42].replace("|", "/"),
            rid=r["roleid"], res="✅" if r.get("has_resume") else "—",
            shot=r.get("screenshot", "n/a"), dir=r["dir"]))
    tmp = INDEX_PATH + ".tmp"
    open(tmp, "w").write("\n".join(lines) + "\n")
    os.replace(tmp, INDEX_PATH)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-copy artifacts even if dir exists")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(DB):
        print(f"ERROR: tracker.db not found at {DB}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(PROOF_DIR, exist_ok=True)
    state = load_state()

    con = sqlite3.connect(DB)
    rows = con.execute(
        "select id, company, role, status, applied_by, applied_on "
        "from roles where status in ('submitted','applied') "
        "order by applied_on asc nulls last, id asc"
    ).fetchall()
    con.close()

    all_records = []
    new_count = 0
    shot_flagged = []
    for row in rows:
        roleid = row[0]
        key = str(roleid)
        if key in state["archived"] and not args.refresh:
            all_records.append(state["archived"][key])
            continue
        # new submission (or refresh): assign next seq if new
        if key in state["archived"]:
            seq = state["archived"][key]["seq"]
        else:
            state["seq"] += 1
            seq = state["seq"]
            new_count += 1
        rec = archive_role(row, seq, state, args.dry_run, args.refresh)
        if not args.dry_run:
            state["archived"][key] = rec
        all_records.append(rec)
        if rec.get("screenshot") == "pending":
            shot_flagged.append({"roleid": roleid, "company": rec["company"],
                                 "role": rec["role"], "dir": rec["dir"], "seq": seq})

    if not args.dry_run:
        save_json(STATE_PATH, state)
        # screenshot queue = flagged-but-not-yet-captured
        existing_q = []
        if os.path.exists(SCREENSHOT_QUEUE):
            try:
                existing_q = json.load(open(SCREENSHOT_QUEUE))
            except Exception:
                existing_q = []
        done_ids = {q["roleid"] for q in existing_q if q.get("status") == "done"}
        queue = [q for q in shot_flagged if q["roleid"] not in done_ids]
        # merge: keep done entries, add new pending
        merged = existing_q + [q for q in queue if q["roleid"] not in {e["roleid"] for e in existing_q}]
        save_json(SCREENSHOT_QUEUE, merged)
        write_index(all_records)

    print(f"proof_archiver: {len(rows)} submitted rows | {new_count} newly archived | "
          f"{len([r for r in all_records if r.get('screenshot')=='pending'])} pending screenshots"
          + (" [DRY-RUN]" if args.dry_run else ""))
    print(f"  archive: {PROOF_DIR}")
    print(f"  index:   {INDEX_PATH}")


if __name__ == "__main__":
    main()
