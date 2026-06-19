"""Probe LinkedIn guest endpoints for offsite apply URL extraction. READ-ONLY."""
import re, sys, time, json, sqlite3, urllib.parse
import requests
sys.path.insert(0, ".")
from tracker_db import DB_PATH

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
                  "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})

LI_ID = re.compile(r"-(\d{8,})(?:[/?]|$)")
ATS_HOSTS = [
    ("greenhouse", re.compile(r"https?://(?:boards|job-boards)\.greenhouse\.io/[^\s\"'<>)]+", re.I)),
    ("ashby", re.compile(r"https?://jobs\.ashbyhq\.com/[^\s\"'<>)]+", re.I)),
    ("lever", re.compile(r"https?://jobs\.lever\.co/[^\s\"'<>)]+", re.I)),
    ("workday", re.compile(r"https?://[a-z0-9.\-]*myworkdayjobs\.com/[^\s\"'<>)]+", re.I)),
    ("smartrecruiters", re.compile(r"https?://(?:jobs|careers)\.smartrecruiters\.com/[^\s\"'<>)]+", re.I)),
    ("icims", re.compile(r"https?://[a-z0-9.\-]*icims\.com/[^\s\"'<>)]+", re.I)),
    ("workable", re.compile(r"https?://(?:apply\.)?workable\.com/[^\s\"'<>)]+", re.I)),
    ("jobvite", re.compile(r"https?://jobs\.jobvite\.com/[^\s\"'<>)]+", re.I)),
    ("bamboohr", re.compile(r"https?://[a-z0-9.\-]*bamboohr\.com/[^\s\"'<>)]+", re.I)),
]

def extract_ats(html):
    out = []
    for kind, pat in ATS_HOSTS:
        for m in pat.finditer(html):
            out.append((kind, m.group(0).rstrip("\"'<>),.;\\")))
    return out

def jid_from(url):
    m = LI_ID.search(url or "")
    return m.group(1) if m else None

def probe(jid):
    res = {"jid": jid, "jd_status": None, "jd_ats": [], "apply_status": None,
           "apply_final": None, "apply_ats": [], "offsite_company": None}
    # 1. JD HTML
    api = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}"
    try:
        r = S.get(api, timeout=20)
        res["jd_status"] = r.status_code
        if r.status_code == 200:
            res["jd_ats"] = list({(k,u) for k,u in extract_ats(r.text)})
            # look for apply-url data attribute / offsite indicator
            m = re.search(r'data-tracking-control-name="public_jobs_apply-link-offsite[^"]*"[^>]*href="([^"]+)"', r.text)
            if not m:
                m = re.search(r'<a[^>]+href="([^"]+)"[^>]*data-tracking-control-name="[^"]*apply[^"]*offsite', r.text)
            if m:
                res["offsite_company"] = urllib.parse.unquote(m.group(1))
    except Exception as e:
        res["jd_status"] = f"ERR {e}"
    time.sleep(1)
    return res

def main():
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, company, role, app_url FROM roles "
        "WHERE source_key LIKE 'linkedin%' AND app_url LIKE '%linkedin.com%' "
        "AND applied_by IS NULL AND status NOT IN ('applied','submitted','skip','closed') "
        "ORDER BY id LIMIT 15").fetchall()
    out = []
    for row in rows:
        jid = jid_from(row["app_url"])
        rec = {"id": row["id"], "company": row["company"], "role": row["role"][:40], "jid": jid}
        if jid:
            rec.update(probe(jid))
        out.append(rec)
        ats = rec.get("jd_ats", [])
        off = rec.get("offsite_company")
        print(f"id={row['id']:4} {row['company'][:20]:20} jid={jid} jd={rec.get('jd_status')} ats={ats} offsite={off}")
    json.dump(out, open("/tmp/li_probe.json","w"), indent=2)
    print("\nwrote /tmp/li_probe.json")

if __name__ == "__main__":
    main()
