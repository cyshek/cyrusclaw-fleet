#!/usr/bin/env python3
"""Re-fetch JDs flagged exp:unstated and re-classify experience."""
import re, json, sys, time, html
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
TRACKER = ROOT / "tracker.md"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/json,*/*"}

# --- experience extraction -----------------------------------------------

# Patterns yielding (min_years_int, raw_phrase). We choose the MAX min across
# all matches (most stringent / required).
PATTERNS = [
    # "minimum of 5 years", "at least 5 years"
    re.compile(r"\b(?:minimum(?: of)?|at\s+least|min\.?)\s+(\d{1,2})\+?\s*(?:\+|or\s+more)?\s*years?\b", re.I),
    # "5+ years", "5 or more years"
    re.compile(r"\b(\d{1,2})\s*\+\s*years?\b", re.I),
    re.compile(r"\b(\d{1,2})\s+or\s+more\s+years?\b", re.I),
    # "5-7 years", "5 to 7 years" -> take low end (min)
    re.compile(r"\b(\d{1,2})\s*[-–to]+\s*\d{1,2}\s*years?\b", re.I),
    # "5 years of experience" (bare)
    re.compile(r"\b(\d{1,2})\s+years?\s+of\s+(?:relevant\s+|professional\s+|industry\s+|related\s+|hands-?on\s+)?(?:work\s+)?experience\b", re.I),
    # "BS + 5 years" / "BA/BS plus 5 years"
    re.compile(r"\b(?:BS|BA|B\.S\.|B\.A\.|bachelor'?s?)[^.]{0,40}?(?:\+|plus|and)\s*(\d{1,2})\s*\+?\s*years?\b", re.I),
]

# Words that mean "preferred / nice to have" - if the match is right after these,
# treat as soft. We still consider but mark as preferred-only.
SOFT_CONTEXT = re.compile(r"\b(prefer(red)?|nice\s+to\s+have|bonus|plus\b|ideal(ly)?|desired)\b", re.I)
HARD_CONTEXT = re.compile(r"\b(require(d|ment)?|must\s+have|minimum|at\s+least)\b", re.I)

INTERN_HINT = re.compile(r"\b(intern(ship)?|new\s+grad|recent\s+grad|university\s+grad|early\s+career|entry[- ]level)\b", re.I)

def extract_min_years(text: str, title: str = "") -> tuple[int|None, str]:
    """Return (min_years, evidence_snippet) or (None, '')."""
    if not text:
        return None, ""
    # Normalize whitespace
    t = re.sub(r"\s+", " ", text)
    findings = []  # list of (years, hard_bool, snippet)
    for pat in PATTERNS:
        for m in pat.finditer(t):
            try:
                yrs = int(m.group(1))
            except (ValueError, IndexError):
                continue
            if yrs < 0 or yrs > 25:
                continue
            start = max(0, m.start() - 80)
            end = min(len(t), m.end() + 80)
            snippet = t[start:end].strip()
            soft = bool(SOFT_CONTEXT.search(t[max(0, m.start()-40):m.start()+1]))
            hard = bool(HARD_CONTEXT.search(t[max(0, m.start()-40):m.start()+1])) or "minimum" in pat.pattern.lower() or "least" in pat.pattern.lower()
            findings.append((yrs, hard, soft, snippet))
    if not findings:
        # intern / new grad => 0 (only if the ROLE TITLE indicates it; nav menus often mention 'Internships')
        if title and INTERN_HINT.search(title):
            return 0, "(role title: new grad / intern / entry-level)"
        return None, ""
    # Prefer hard over soft. If any hard, use min of hard mins. Else use min of soft.
    hard_findings = [f for f in findings if f[1] and not f[2]]
    soft_findings = [f for f in findings if f[2] and not f[1]]
    neutral = [f for f in findings if not f[1] and not f[2]]
    pool = hard_findings or neutral or soft_findings
    # Choose the SMALLEST stated requirement (most generous = actual minimum).
    pool.sort(key=lambda x: x[0])
    yrs, _, _, snip = pool[0]
    return yrs, snip

# --- fetching ------------------------------------------------------------

def strip_html(html_text: str) -> str:
    # Remove script/style
    html_text = re.sub(r"<script\b[^>]*>.*?</script>", " ", html_text, flags=re.S|re.I)
    html_text = re.sub(r"<style\b[^>]*>.*?</style>", " ", html_text, flags=re.S|re.I)
    # Strip tags
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

def fetch_workday(url: str) -> str:
    """Workday: strip /job/.../ID and call /wday/cxs/<tenant>/<site>/job/<ID>."""
    # url like https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/Some-Title_R166534
    m = re.match(r"https?://([^.]+)\.([a-z0-9]+)\.myworkdayjobs\.com/([^/]+)/job/[^/]+/([^/?]+)", url)
    if not m:
        return ""
    tenant, pod, site, slug = m.group(1), m.group(2), m.group(3), m.group(4)
    api = f"https://{tenant}.{pod}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/job/{slug}"
    try:
        r = requests.get(api, headers={**HEADERS, "Accept": "application/json"}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            desc = data.get("jobPostingInfo", {}).get("jobDescription", "")
            qual = data.get("jobPostingInfo", {}).get("jobRequirements", "")
            return strip_html(desc + " " + qual)
    except Exception:
        pass
    return ""

def fetch_greenhouse(url: str) -> str:
    """Greenhouse job-boards.greenhouse.io/<board>/jobs/<id>"""
    m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", url)
    if m:
        board, jid = m.group(1), m.group(2)
        api = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{jid}"
        try:
            r = requests.get(api, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                data = r.json()
                return strip_html(data.get("content", ""))
        except Exception:
            pass
    return ""

def fetch_ashby(url: str) -> str:
    """Ashby jobs.ashbyhq.com/<org>/<jobId>"""
    m = re.search(r"ashbyhq\.com/([^/]+)/([0-9a-f-]+)", url)
    if m:
        org, jid = m.group(1), m.group(2)
        api = f"https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting"
        body = {
            "operationName": "ApiJobPosting",
            "variables": {"organizationHostedJobsPageName": org, "jobPostingId": jid},
            "query": "query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) { jobPosting(organizationHostedJobsPageName: $organizationHostedJobsPageName, jobPostingId: $jobPostingId) { descriptionHtml } }"
        }
        try:
            r = requests.post(api, json=body, headers={**HEADERS, "Content-Type":"application/json"}, timeout=20)
            if r.status_code == 200:
                d = r.json()
                desc = ((d.get("data") or {}).get("jobPosting") or {}).get("descriptionHtml") or ""
                if desc:
                    return strip_html(desc)
        except Exception:
            pass
    return ""

def fetch_lever(url: str) -> str:
    m = re.search(r"jobs\.lever\.co/([^/]+)/([0-9a-f-]+)", url)
    if m:
        api = f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}"
        try:
            r = requests.get(api, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                d = r.json()
                txt = d.get("descriptionPlain","") + "\n" + d.get("additionalPlain","")
                for lst in d.get("lists", []):
                    txt += "\n" + strip_html(lst.get("content",""))
                return txt
        except Exception:
            pass
    return ""

def fetch_generic(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        if r.status_code == 200:
            return strip_html(r.text)
    except Exception:
        pass
    return ""

def fetch_jd(url: str) -> tuple[str, str]:
    """Return (text, source). Empty text means failed."""
    if "linkedin.com" in url:
        # Skip LinkedIn — usually blocked / requires JS.
        return "", "linkedin-skip"
    if "myworkdayjobs.com" in url:
        t = fetch_workday(url)
        if t: return t, "workday-api"
    if "greenhouse.io" in url:
        t = fetch_greenhouse(url)
        if t: return t, "greenhouse-api"
    if "ashbyhq.com" in url:
        t = fetch_ashby(url)
        if t: return t, "ashby-api"
    if "lever.co" in url:
        t = fetch_lever(url)
        if t: return t, "lever-api"
    t = fetch_generic(url)
    if t:
        return t, "generic"
    return "", "fetch-failed"

# --- tracker editing -----------------------------------------------------

PIPE_PLACEHOLDER = "\x00ESCPIPE\x00"

def _split_row(line: str) -> list[str]:
    s = line.rstrip("\n").replace("\\|", PIPE_PLACEHOLDER)
    parts = s.split("|")
    return [p.replace(PIPE_PLACEHOLDER, "\\|") for p in parts]

def parse_row(line: str) -> dict | None:
    if not line.startswith("|") or "exp:unstated" not in line:
        return None
    parts = _split_row(line)
    # parts[0]='', cells 1..9, parts[10]=''
    if len(parts) < 11:
        return None
    cells = [p.strip() for p in parts[1:10]]
    app_url = cells[6]
    return {"line": line, "cells": cells, "url": app_url}

def update_line(line: str, new_exp: str | None, new_status: str | None, note: str) -> str:
    """Mutate the markdown row preserving its exact column structure."""
    # Split keeping leading/trailing pipes
    parts = _split_row(line)
    if len(parts) < 11:
        return line
    # cell indices: 1=Company,2=Role,3=Level,4=Loc,5=Exp,6=JD,7=App,8=Status,9=Flags
    if new_exp:
        parts[5] = f" {new_exp} "
    if new_status:
        parts[8] = f" {new_status} "
    if note:
        flag = parts[9].strip()
        if flag in ("", "—"):
            parts[9] = f" {note} "
        else:
            parts[9] = f" {flag}; {note} "
    return "|".join(parts) + "\n"

def main():
    text = TRACKER.read_text()
    lines = text.splitlines(keepends=True)
    targets = []
    for i, line in enumerate(lines):
        row = parse_row(line)
        if row:
            row["idx"] = i
            targets.append(row)
    print(f"Found {len(targets)} exp:unstated rows", file=sys.stderr)

    results = {}
    def work(row):
        url = row["url"]
        text, source = fetch_jd(url)
        yrs, snip = extract_min_years(text, row["cells"][1]) if text else (None, "")
        return row["idx"], {"url": url, "source": source, "text_len": len(text), "yrs": yrs, "snippet": snip[:200]}

    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(work, r) for r in targets]
        for f in as_completed(futs):
            idx, info = f.result()
            results[idx] = info

    # Apply updates
    kept = dropped = unstated = failed = 0
    failed_rows = []
    audit = []
    for row in targets:
        idx = row["idx"]
        info = results[idx]
        line = lines[idx]
        company_role = " | ".join(row["cells"][:2])
        if info["source"] in ("fetch-failed", "linkedin-skip") and info["text_len"] == 0:
            failed += 1
            failed_rows.append(f"- {company_role} — {info['source']} — {info['url']}")
            audit.append({"row": company_role, "outcome": "fetch-failed", "source": info["source"], "url": info["url"]})
            continue
        yrs = info["yrs"]
        if yrs is None:
            unstated += 1
            lines[idx] = update_line(line, None, None, "JD silent on yrs")
            audit.append({"row": company_role, "outcome": "still-unstated", "source": info["source"]})
        elif yrs <= 3:
            kept += 1
            new_exp = f"exp:{yrs}+yrs" if yrs > 0 else "exp:0-3yrs"
            lines[idx] = update_line(line, new_exp, None, f"JD: {yrs}+yrs (auto JD-fetch 2026-05-06)")
            audit.append({"row": company_role, "outcome": "kept", "yrs": yrs, "source": info["source"], "snippet": info["snippet"]})
        else:
            dropped += 1
            new_exp = f"exp:{yrs}+yrs"
            lines[idx] = update_line(line, new_exp, "skip-too-senior", f"JD requires {yrs}yr (auto JD-fetch 2026-05-06)")
            audit.append({"row": company_role, "outcome": "skip-too-senior", "yrs": yrs, "source": info["source"], "snippet": info["snippet"]})

    # Re-read tracker before write to avoid clobbering concurrent edits
    fresh = TRACKER.read_text()
    fresh_lines = fresh.splitlines(keepends=True)
    if len(fresh_lines) != len(lines):
        print(f"WARN: tracker line count changed during run ({len(fresh_lines)} vs {len(lines)}). Re-applying by URL match.", file=sys.stderr)
        # Map original idx -> updated line; re-locate by URL
        new_by_url = {}
        for r in targets:
            new_by_url[r["url"]] = lines[r["idx"]]
        out = []
        for fl in fresh_lines:
            row = parse_row(fl)
            if row and row["url"] in new_by_url:
                out.append(new_by_url[row["url"]])
            else:
                out.append(fl)
        TRACKER.write_text("".join(out))
    else:
        TRACKER.write_text("".join(lines))

    summary = {
        "checked": len(targets),
        "kept": kept,
        "dropped_too_senior": dropped,
        "still_unstated": unstated,
        "failed": failed,
        "failed_rows": failed_rows,
        "audit": audit,
    }
    Path(ROOT.parent.parent / "outputs/jd-second-pass-audit.json").parent.mkdir(parents=True, exist_ok=True)
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
