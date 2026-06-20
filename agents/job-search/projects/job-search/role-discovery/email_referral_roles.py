#!/usr/bin/env python3
"""Email Cyrus newly-discovered REFERRAL-HOLD roles + tailored resumes.

Cyrus directive (2026-06-01): for companies where Cyrus has a referral or wants
to route applications himself, we DISCOVER but NEVER auto-apply. This step
tailors a 1-page resume for each NEW fit and emails it to him with the role
link (and, where he has one, his personal REFERRAL link), so he applies through
the path that credits him.

Referral-hold sources handled: uber, bytedance, tiktok.
  - uber: held for a friend's referral.
  - bytedance / tiktok: Cyrus has referral links + code CY6MGWW
    (projects/job-search/.referrals.json). Email includes his referral link so
    applying credits him — auto-applying would forfeit that.

This is a post-merge weekly step. It:
  1. Selects referral-hold tracker rows that are fresh (status open/discovered)
     and NOT yet emailed (`flags` lacks `emailed-referral`).
  2. Re-fetches the JD fresh from the source API by id, stages JD.md, tailors a
     1-page resume (family auto-detected from the title).
  3. Emails ONE digest to cyshekari@gmail.com: role link + referral link + PDF.
  4. Flags each emailed row `emailed-referral <date>` so it never re-sends.

Idempotent: re-running emails nothing new once rows are flagged. `--dry-run`
does everything except send + flag. Backs up tracker.db before flagging.
"""
from __future__ import annotations
import argparse, json, pathlib, re, smtplib, ssl, sqlite3, subprocess, sys, datetime
from email.message import EmailMessage

PROJ = pathlib.Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search")
RD = PROJ / "role-discovery"
DB = PROJ / "tracker.db"
QUEUED = PROJ / "applications" / "queued"
PY = str(RD / ".venv" / "bin" / "python")
PW_FILE = PROJ / ".gmail-app-password"
REFERRALS_FILE = PROJ / ".referrals.json"
EMAIL_ADDR = "cyshekari@gmail.com"

# Companies whose rows are referral-hold (discover + email, never auto-apply).
REFERRAL_COMPANIES = {"Uber": "uber", "ByteDance": "bytedance", "TikTok": "tiktok"}
UBER_SEARCH = "https://www.uber.com/api/loadSearchJobsResults?localeCode=en"

# ByteDance/TikTok shared public API (curl-reachable with these two headers).
_BD_HOST = {"bytedance": "jobs.bytedance.com", "tiktok": "lifeattiktok.com"}
_BD_WPATH = {"bytedance": "en", "tiktok": "tiktok"}


def _load_referral_links() -> dict:
    try:
        d = json.loads(REFERRALS_FILE.read_text())
        return {k: (v.get("referral_link") or "") for k, v in d.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _uber_jd(job_id: str, title_hint: str) -> tuple[str, str] | None:
    query = " ".join(title_hint.split()[:4]) or title_hint
    body = json.dumps({"params": {"query": query}, "page": 0, "limit": 25})
    out = subprocess.run(
        ["curl", "-s", "-X", "POST", UBER_SEARCH,
         "-H", "Content-Type: application/json", "-H", "x-csrf-token: x",
         "-d", body], capture_output=True, text=True).stdout
    try:
        results = json.loads(out).get("data", {}).get("results", []) or []
    except Exception:
        return None
    row = next((r for r in results if str(r.get("id")) == str(job_id)), None)
    if not row:
        return None
    desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row.get("description", "") or "")).strip()
    return row.get("title", title_hint), desc


def _bytedance_jd(brand: str, job_id: str, title_hint: str) -> tuple[str, str] | None:
    host, wpath = _BD_HOST[brand], _BD_WPATH[brand]
    url = f"https://{host}/api/v1/public/supplier/search/job/posts"
    body = json.dumps({"recruitment_id_list": [], "job_category_id_list": [],
                       "subject_id_list": [], "location_code_list": [],
                       "keyword": " ".join((title_hint or "").split()[:4]),
                       "limit": 50, "offset": 0})
    out = subprocess.run(
        ["curl", "-s", "-X", "POST", url,
         "-H", "Content-Type: application/json", "-H", "accept-language: en-US",
         "-H", f"website-path: {wpath}", "-H", "x-tt-env: boe_epam_api",
         "-H", f"origin: https://{host}", "-d", body],
        capture_output=True, text=True).stdout
    try:
        jl = (json.loads(out).get("data") or {}).get("job_post_list") or []
    except Exception:
        return None
    j = next((x for x in jl if str(x.get("id")) == str(job_id)), None)
    if not j:
        return None
    jd = (j.get("description") or "") + "\n" + (j.get("requirement") or "")
    jd = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", jd)).strip()
    return j.get("title", title_hint), jd


def _fetch_jd(source: str, job_id: str, title_hint: str):
    if source == "uber":
        return _uber_jd(job_id, title_hint)
    if source in ("bytedance", "tiktok"):
        return _bytedance_jd(source, job_id, title_hint)
    return None


def _job_id_from_row(source: str, row) -> str:
    sk = (row["source_key"] or "")
    m = re.match(rf"{source}-(.+)$", sk)
    if m:
        return m.group(1).strip()
    # fall back to numeric id in app/jd url
    m = re.search(r"/(?:list|position)/(\d+)", row["app_url"] or row["jd_url"] or "")
    return m.group(1) if m else ""


def _detect_family(title: str) -> str:
    sys.path.insert(0, str(RD))
    import tailor_resume as t  # noqa
    return t.detect_family(title)


def _tailor(source: str, job_id: str, title: str, jd_text: str) -> pathlib.Path | None:
    out_dir = QUEUED / f"{source}-{job_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "JD.md").write_text(f"# {title}\n\n{jd_text}\n")
    fam = _detect_family(title)
    r = subprocess.run(
        [PY, "tailor_resume.py", "--org", source, "--job-id", str(job_id),
         "--family", fam, "--auto-rewrite", "--out-dir", str(out_dir), "--max-loops", "3"],
        cwd=str(RD), capture_output=True, text=True)
    pdfs = sorted(out_dir.glob("*_v2.pdf"))
    if not pdfs:
        sys.stderr.write(f"[tailor FAIL] {source}-{job_id}\n{r.stdout[-800:]}\n{r.stderr[-400:]}\n")
        return None
    return pdfs[0]


def _send(items: list[dict]) -> None:
    """Send ONE email PER COMPANY (Cyrus directive 2026-06-02: never bundle
    multiple companies into one email — a separate TikTok email, a separate Uber
    email, etc.). Groups items by company and sends one message per group."""
    pw = PW_FILE.read_text().strip()
    by_company: dict[str, list[dict]] = {}
    for it in items:
        by_company.setdefault(it["company"], []).append(it)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(EMAIL_ADDR, pw)
        for company in sorted(by_company):
            group = by_company[company]
            _send_one_company(s, company, group)


def _send_one_company(s, company: str, items: list[dict]) -> None:
    msg = EmailMessage()
    n = len(items)
    msg["Subject"] = f"{company} referral roles — {n} new tailored resume{'s' if n!=1 else ''}"
    msg["From"] = EMAIL_ADDR
    msg["To"] = EMAIL_ADDR
    lines = ["Hey Cyrus,", "",
             f"{n} newly-discovered role{'s' if n!=1 else ''} at {company} that fit your "
             "profile (IC, ~3 yrs, US). Tailored resume attached for each — held, NOT "
             "applied, so you apply through your referral and keep the credit.", ""]
    for i, it in enumerate(items, 1):
        lines += [f"{i}. {it['title']} — {it['loc']}",
                  f"   Role link: {it['url']}"]
        if it.get("referral"):
            lines += [f"   ➜ Apply via YOUR referral: {it['referral']}"]
        lines += [f"   Resume: {it['pdf'].name}", ""]
    lines += ["From the weekly discovery run. Reply to widen the filter "
              "(e.g. allow Senior) for referral cases.", "", "— job-search agent"]
    msg.set_content("\n".join(lines))
    for it in items:
        p = it["pdf"]
        msg.add_attachment(p.read_bytes(), maintype="application", subtype="pdf", filename=p.name)
    s.send_message(msg)
    print(f"  EMAILED {company}: {n} role(s)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=25)
    args = ap.parse_args()

    referral_links = _load_referral_links()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in REFERRAL_COMPANIES)
    rows = con.execute(
        f"""SELECT id, source_key, company, role, loc, app_url, jd_url, flags
            FROM roles
            WHERE company IN ({placeholders})
              AND IFNULL(status,'') IN ('', 'discovered', 'new', 'open')
              AND (IFNULL(flags,'') LIKE '%hold-for-referral%'
                   OR IFNULL(flags,'') LIKE '%discovery-only%'
                   OR IFNULL(flags,'') LIKE '%manual-apply%')
              AND IFNULL(flags,'') NOT LIKE '%emailed-referral%'
            ORDER BY id LIMIT ?""",
        (*REFERRAL_COMPANIES.keys(), args.limit)).fetchall()

    if not rows:
        print("No new referral roles to email.")
        return 0

    items, emailed_ids = [], []
    for row in rows:
        source = REFERRAL_COMPANIES.get(row["company"])
        if not source:
            continue
        job_id = _job_id_from_row(source, row)
        if not job_id:
            print(f"  skip id={row['id']} ({row['company']}): no job id"); continue
        jd = _fetch_jd(source, job_id, row["role"] or "")
        if not jd:
            print(f"  skip {source}-{job_id}: JD not found at source (likely closed)"); continue
        title, jd_text = jd
        pdf = _tailor(source, job_id, title, jd_text)
        if not pdf:
            print(f"  skip {source}-{job_id}: tailor failed"); continue
        ref = referral_links.get(source, "")
        items.append({"company": row["company"], "title": title, "loc": row["loc"] or "",
                      "url": row["app_url"] or row["jd_url"] or "", "referral": ref, "pdf": pdf})
        emailed_ids.append(row["id"])
        print(f"  ready: {source}-{job_id} | {title} -> {pdf.name}{' (+referral)' if ref else ''}")

    if not items:
        print("Nothing tailorable to email."); return 0

    if args.dry_run:
        print(f"[dry-run] would email {len(items)} role(s) + flag ids {emailed_ids}")
        return 0

    _send(items)
    today = datetime.date.today().isoformat()
    bak = DB.with_suffix(f".db.bak.{datetime.datetime.now():%Y%m%d-%H%M}-referral-email")
    con.close()
    import shutil; shutil.copy(DB, bak)
    con = sqlite3.connect(DB)
    for rid in emailed_ids:
        cur = con.execute("SELECT IFNULL(flags,'') FROM roles WHERE id=?", (rid,)).fetchone()[0]
        con.execute("UPDATE roles SET flags=? WHERE id=?",
                    ((cur + f" emailed-referral {today}").strip(), rid))
    con.commit(); con.close()
    print(f"EMAILED {len(items)} role(s) to {EMAIL_ADDR}; flagged ids {emailed_ids}; backup {bak.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
