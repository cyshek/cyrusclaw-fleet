#!/usr/bin/env python3
"""Reconcile bogus BLOCKED 2026-05-25 sequential-driver notes from real STATUS.md.

Targets ONLY rows whose sequential-driver line contains 'unparseable inline_submit'
(the JSON-parse-bug rows). Leaves 'unsupported-ats' rows untouched (those are real).
"""
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "tracker.db"
SUBMITTED = ROOT / "applications" / "submitted"
SUMMARY = ROOT / "applications" / "_burndown-v2-reconcile-summary.md"

# import slugify from inline_submit
sys.path.insert(0, str(ROOT / "role-discovery"))
from inline_submit import slugify  # noqa: E402

# Patterns to extract a job id from various ATS URLs (matches inline_submit logic)
JID_PATTERNS = [
    (re.compile(r"greenhouse\.io/(?:embed/job_app\?for=[^&]+&token=|[^/]+/jobs/)(\d+)"), "gh"),
    (re.compile(r"job-boards\.greenhouse\.io/[^/]+/jobs/(\d+)"), "gh"),
    (re.compile(r"jobs\.ashbyhq\.com/[^/]+/([0-9a-f-]{36})"), "ashby"),
    (re.compile(r"jobs\.lever\.co/[^/]+/([0-9a-f-]+)"), "lever"),
]


def derive_slug(company: str, app_url: str) -> str | None:
    company_slug = slugify(company)
    for pat, kind in JID_PATTERNS:
        m = pat.search(app_url or "")
        if m:
            jid = m.group(1)
            if kind == "lever":
                jid = jid[:8]
            return f"{company_slug}-{jid}"
    # Workday: extract reqid
    m = re.search(r"_(R\d+[A-Z0-9-]*)/?", app_url or "")
    if m:
        return f"{company_slug}-{m.group(1).lower()}"
    return None


def build_status_index() -> dict[int, Path]:
    """Map role_id -> STATUS.md path, by parsing each STATUS.md for `role_id:` / `Role ID:`."""
    idx: dict[int, Path] = {}
    for status in SUBMITTED.glob("*/STATUS.md"):
        try:
            text = status.read_text(errors="replace")
        except Exception:
            continue
        m = re.search(r"(?im)^[*\-\s]*(?:\*\*)?(?:role[_ ]id|Role ID)(?:\*\*)?:\s*(\d+)", text)
        if m:
            idx[int(m.group(1))] = status
    return idx


def slug_to_status() -> dict[str, Path]:
    return {p.parent.name: p for p in SUBMITTED.glob("*/STATUS.md")}


def headline(status_md: Path) -> str:
    try:
        for line in status_md.read_text(errors="replace").splitlines():
            line = line.strip()
            if line:
                # strip markdown header markers
                return line.lstrip("# ").strip()
    except Exception as e:
        return f"<read error: {e}>"
    return ""


def categorize(headline_str: str) -> str:
    h = headline_str.lower()
    if "submitted-auto" in h or h.startswith("submitted") or "status: submitted" in h:
        return "submitted"
    if "prep-ready-manual" in h or "prep-ready" in h or h == "status: prep-ready-manual":
        return "prep-ready-manual"
    if "iframe-runner" in h:
        return "prep-ready-iframe-runner"
    if "maintenance" in h:
        return "maintenance-retry"
    if "captcha" in h:
        return "blocked-captcha"
    if "csp" in h:
        return "blocked-csp"
    if "abort-dryrun-blockers" in h:
        return "abort-dryrun-blockers"
    if "abort-jd-fetch" in h:
        return "abort-jd-fetch"
    if "abort-spam" in h:
        return "abort-spam-flag"
    if "abort-eu" in h:
        return "abort-eu-greenhouse"
    if "abort-overreach" in h:
        return "abort-overreach"
    if "abort-partial" in h:
        return "abort-partial"
    if "abort" in h:
        return "abort-other"
    if "blocked" in h:
        return "blocked-other"
    if "skipped" in h or "posting removed" in h:
        return "skipped-removed"
    return "other"


def main():
    con = sqlite3.connect(DB)
    rows = con.execute(
        "SELECT id, company, app_url, agent_notes FROM roles "
        "WHERE agent_notes LIKE '%BLOCKED 2026-05-25: sequential-driver%unparseable inline_submit%'"
    ).fetchall()
    print(f"target rows (unparseable bug): {len(rows)}")

    rid_to_status = build_status_index()
    slug_to_st = slug_to_status()
    print(f"STATUS.md w/ explicit role_id: {len(rid_to_status)}")
    print(f"total STATUS.md folders: {len(slug_to_st)}")

    cat_counter = Counter()
    cat_role_ids: dict[str, list[int]] = defaultdict(list)
    fixed = 0
    no_folder = 0

    for rid, company, app_url, notes in rows:
        status_md = rid_to_status.get(rid)
        match_method = "role_id"
        if not status_md:
            slug = derive_slug(company or "", app_url or "")
            if slug and slug in slug_to_st:
                status_md = slug_to_st[slug]
                match_method = f"slug={slug}"

        if not status_md:
            real_cat = "no-prep-folder"
            new_line = (
                f"BLOCKED 2026-05-25: no-prep-folder | inline_submit didn't write STATUS.md (real failure)"
            )
            no_folder += 1
        else:
            head = headline(status_md)
            real_cat = categorize(head)
            rel = status_md.relative_to(ROOT)
            new_line = (
                f"BLOCKED 2026-05-25: {real_cat} | {head[:160]} | source: {rel} ({match_method})"
            )
            fixed += 1

        cat_counter[real_cat] += 1
        cat_role_ids[real_cat].append(rid)

        # Replace ONLY the bogus sequential-driver/unparseable line(s); keep other lines
        new_lines = []
        for line in notes.split("\n"):
            if "BLOCKED 2026-05-25: sequential-driver" in line and "unparseable inline_submit" in line:
                new_lines.append(new_line)
            else:
                new_lines.append(line)
        new_notes = "\n".join(new_lines)
        con.execute("UPDATE roles SET agent_notes=? WHERE id=?", (new_notes, rid))

    con.commit()

    # Re-attempt eligible: prep-ready-manual + iframe-runner where prep is done but submit pending
    reattempt = sorted(cat_role_ids.get("prep-ready-manual", []) + cat_role_ids.get("prep-ready-iframe-runner", []))
    submitted_already = sorted(cat_role_ids.get("submitted", []))

    # Cross-check: any 'submitted' rows? Those should already be applied — flag them
    not_marked_applied = []
    for srid in submitted_already:
        r = con.execute("SELECT applied_by, applied_on, prep_status FROM roles WHERE id=?", (srid,)).fetchone()
        if r and not r[0]:
            not_marked_applied.append((srid, r))

    con.close()

    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    md = [
        "# Burndown V2 — Bogus-BLOCKED Reconciliation Summary (2026-05-25)",
        "",
        f"- Target rows (sequential-driver | unparseable inline_submit): **{len(rows)}**",
        f"- Reconciled from STATUS.md: **{fixed}**",
        f"- No STATUS.md found: **{no_folder}**",
        f"- DB backup: `tracker.db.bak.20260525-notes-reconcile`",
        "",
        "## Real-status category breakdown",
        "",
    ]
    for cat, n in cat_counter.most_common():
        md.append(f"- **{cat}** — {n}")
    md.append("")
    md.append("## Re-attempt eligible (prep done, browser submit pending)")
    md.append("")
    if reattempt:
        md.append(f"{len(reattempt)} role IDs: {reattempt}")
    else:
        md.append("(none)")
    md.append("")
    md.append("## STATUS.md says 'submitted' but tracker still shows unapplied")
    md.append("")
    if not_marked_applied:
        md.append(f"{len(not_marked_applied)} mismatches:")
        for srid, r in not_marked_applied:
            md.append(f"- role_id={srid} applied_by={r[0]!r} applied_on={r[1]!r} prep_status={r[2]!r}")
    else:
        md.append("(none — clean)")
    md.append("")
    md.append("## Per-category role IDs (first 25 each)")
    md.append("")
    for cat, n in cat_counter.most_common():
        ids = cat_role_ids[cat][:25]
        md.append(f"- **{cat}** ({n}): {ids}{' ...' if n > 25 else ''}")
    md.append("")
    SUMMARY.write_text("\n".join(md))
    print(f"summary written: {SUMMARY}")
    print(f"fixed: {fixed}  no_folder: {no_folder}")
    print(f"categories: {dict(cat_counter)}")
    print(f"re-attempt eligible: {len(reattempt)} -> {reattempt[:20]}...")


if __name__ == "__main__":
    main()
