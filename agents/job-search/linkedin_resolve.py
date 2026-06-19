#!/usr/bin/env python3
"""LinkedIn-row resolver. Tactics 1, 2, 4 in-process. Logs unresolved for tactic-3 sweep.

Usage: linkedin_resolve.py [--limit N] [--ids 1,2,3]
"""
from __future__ import annotations
import argparse, glob, json, os, re, sqlite3, sys, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
import requests
import yaml

WS = Path('/home/azureuser/.openclaw/agents/job-search/workspace')
DB = WS / 'projects/job-search/tracker.db'
COMPANIES = WS / 'projects/job-search/role-discovery/companies.yaml'
OUTPUT_DIR = WS / 'projects/job-search/role-discovery/output'
LOG = WS / 'projects/job-search/applications/_linkedin-resolve-20260524.log'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

ATS_DOMAINS = re.compile(r'(?:greenhouse\.io|boards\.greenhouse|jobs\.lever\.co|jobs\.ashbyhq\.com|myworkdayjobs\.com|smartrecruiters\.com|workable\.com|bamboohr\.com|recruitee\.com|jobvite\.com|icims\.com|breezy\.hr|teamtailor\.com|workatastartup\.com|notion\.so/Careers)', re.I)


def now_iso():
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def log_line(line: str):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open('a') as f:
        f.write(line + '\n')


def normalize_title(s: str) -> str:
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9 ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # normalize variants
    s = s.replace(' sr ', ' senior ').replace(' jr ', ' junior ')
    s = re.sub(r'\bpm\b', 'product manager', s)
    s = re.sub(r'\btpm\b', 'technical program manager', s)
    return s


def title_match(linkedin_title: str, candidate_title: str) -> float:
    """Return [0,1] match score. >=0.7 considered high-confidence."""
    a = set(normalize_title(linkedin_title).split())
    b = set(normalize_title(candidate_title).split())
    # remove ultra-common
    common = {'manager', 'product', 'senior', 'junior', 'a', 'the', 'i', 'ii', 'iii', 'iv', 'and', '&', 'of', 'for'}
    a2, b2 = a - common, b - common
    if not a2 or not b2:
        # fall back to full set similarity
        a2, b2 = a, b
    if not a2 or not b2:
        return 0.0
    overlap = len(a2 & b2) / max(len(a2), len(b2))
    # bonus if normalized strings are substring of each other
    na, nb = normalize_title(linkedin_title), normalize_title(candidate_title)
    if na in nb or nb in na:
        overlap = max(overlap, 0.85)
    return overlap


def company_match(linkedin_company: str, candidate_company: str) -> float:
    a = re.sub(r'[^a-z0-9]', '', (linkedin_company or '').lower())
    b = re.sub(r'[^a-z0-9]', '', (candidate_company or '').lower())
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.9
    # token overlap
    ta = set(re.findall(r'[a-z0-9]+', (linkedin_company or '').lower())) - {'inc', 'llc', 'ltd', 'co', 'corp', 'the', 'ai', 'labs'}
    tb = set(re.findall(r'[a-z0-9]+', (candidate_company or '').lower())) - {'inc', 'llc', 'ltd', 'co', 'corp', 'the', 'ai', 'labs'}
    if ta and tb and (ta & tb):
        return 0.7
    return 0.0


def load_companies_yaml():
    with COMPANIES.open() as f:
        data = yaml.safe_load(f)
    return data.get('companies', [])


def load_latest_roles_json():
    files = sorted(OUTPUT_DIR.glob('*-roles.json'))
    if not files:
        return []
    with files[-1].open() as f:
        return json.load(f)


def tactic1_yaml_match(company: str, role_title: str, yaml_companies, roles_index):
    """Look up company in companies.yaml, find matching role in latest crawl JSON."""
    cnorm = re.sub(r'[^a-z0-9]', '', company.lower())
    for entry in yaml_companies:
        name = entry.get('name', '')
        nnorm = re.sub(r'[^a-z0-9]', '', name.lower())
        if cnorm == nnorm or (cnorm in nnorm and len(cnorm) > 3) or (nnorm in cnorm and len(nnorm) > 3):
            # find in roles index
            best = (0.0, None)
            for r in roles_index:
                if r.get('company') != name:
                    continue
                score = title_match(role_title, r.get('title', ''))
                if score > best[0]:
                    best = (score, r)
            if best[1] and best[0] >= 0.7:
                return best[1].get('url'), f"companies-yaml({entry.get('adapter')}) score={best[0]:.2f}"
            elif best[1]:
                # near miss: return None but note
                return None, f"yaml-near-miss(best={best[0]:.2f})"
            return None, "yaml-listed-no-roles-match"
    return None, None  # not in yaml


def http_get(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return r
    except Exception as e:
        return None


def extract_ats_urls_from_html(html: str) -> list:
    if not html:
        return []
    urls = set()
    for m in re.finditer(r'https?://[^\s"\'<>]+', html):
        u = m.group(0).rstrip('.,);]')
        if ATS_DOMAINS.search(u):
            urls.add(u)
    return list(urls)


def tactic2_linkedin_fetch(linkedin_url: str, company: str, title: str):
    r = http_get(linkedin_url)
    if not r or r.status_code != 200:
        return None, f"linkedin-fetch-status={r.status_code if r else 'err'}"
    ats_urls = extract_ats_urls_from_html(r.text)
    if not ats_urls:
        return None, "linkedin-fetch-no-ats-found"
    # pick the most-likely: prefer ones with company name in URL
    cnorm = re.sub(r'[^a-z0-9]', '', company.lower())
    scored = []
    for u in ats_urls:
        unorm = re.sub(r'[^a-z0-9]', '', u.lower())
        score = 1 if cnorm and cnorm in unorm else 0
        scored.append((score, u))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1], f"linkedin-jd-body(found={len(ats_urls)})"


def company_slug_candidates(company: str) -> list:
    base = re.sub(r'[^a-z0-9 ]', '', company.lower()).strip()
    base = re.sub(r'\b(inc|llc|ltd|co|corp|the)\b', '', base).strip()
    base = re.sub(r'\s+', '', base)
    if not base:
        return []
    cands = [base]
    # also try with hyphen
    h = re.sub(r'[^a-z0-9]+', '-', company.lower()).strip('-')
    h = re.sub(r'-(inc|llc|ltd|co|corp|the)$', '', h)
    if h and h != base:
        cands.append(h)
    return cands


def tactic4_careers_page(company: str, title: str):
    """Try common careers URL patterns. Look for ATS link in HTML."""
    slugs = company_slug_candidates(company)
    if not slugs:
        return None, "no-slug"
    bases = []
    for s in slugs:
        bases += [
            f'https://www.{s}.com/careers',
            f'https://{s}.com/careers',
            f'https://careers.{s}.com',
            f'https://www.{s}.com/jobs',
            f'https://jobs.{s}.com',
        ]
    seen = set()
    for url in bases:
        if url in seen:
            continue
        seen.add(url)
        r = http_get(url, timeout=10)
        if not r or r.status_code >= 400:
            continue
        ats_urls = extract_ats_urls_from_html(r.text)
        if ats_urls:
            # Take first ats with company hint
            cnorm = re.sub(r'[^a-z0-9]', '', company.lower())
            for u in ats_urls:
                unorm = re.sub(r'[^a-z0-9]', '', u.lower())
                if cnorm in unorm:
                    return u, f"careers-page({url})"
            # else first one
            return ats_urls[0], f"careers-page({url}) generic"
    return None, "careers-pages-tried"


def derive_source_key(ats_url: str) -> str:
    """Given an ATS URL, derive a source_key prefix like 'greenhouse:plaid:1234'."""
    u = urlparse(ats_url)
    host = u.netloc.lower()
    path = u.path
    if 'greenhouse.io' in host or 'boards.greenhouse' in host:
        # boards.greenhouse.io/<org>/jobs/<id> or jobs.lever-style
        m = re.search(r'/(?:embed/job_app\?for=|)([^/]+)/jobs/(\d+)', path)
        if m:
            return f'greenhouse:{m.group(1)}:{m.group(2)}'
        m = re.search(r'gh_jid=(\d+)', ats_url)
        if m:
            # try host-based slug
            m2 = re.search(r'jobs\.([a-z0-9-]+)\.com', host)
            slug = m2.group(1) if m2 else 'unknown'
            return f'greenhouse:{slug}:{m.group(1)}'
        return f'greenhouse:unknown:{int(time.time())}'
    if 'lever.co' in host:
        m = re.search(r'/([^/]+)/([0-9a-f-]+)', path)
        if m:
            return f'lever:{m.group(1)}:{m.group(2)}'
        return f'lever:unknown:{int(time.time())}'
    if 'ashbyhq.com' in host:
        m = re.search(r'/([^/]+)/([0-9a-f-]+)', path)
        if m:
            return f'ashby:{m.group(1)}:{m.group(2)}'
        return f'ashby:unknown:{int(time.time())}'
    if 'myworkdayjobs.com' in host:
        m = re.search(r'/job/[^/]+/[^/]+/([^/?_]+)', path)
        jid = m.group(1) if m else str(int(time.time()))
        tenant = host.split('.')[0]
        return f'workday:{tenant}:{jid}'
    if 'smartrecruiters.com' in host:
        m = re.search(r'/([^/]+)/(\d+)', path)
        if m:
            return f'smartrecruiters:{m.group(1)}:{m.group(2)}'
    return f'ats:{host}:{int(time.time())}'


def fetch_targets(con, limit=None, only_ids=None):
    cur = con.cursor()
    q = """SELECT id, company, role, est_tc, app_url
           FROM roles
           WHERE source_key LIKE 'linkedin:%'
             AND (status IS NULL OR status='')
             AND applied_by IS NULL
             AND (app_url LIKE '%linkedin.com%' OR app_url IS NULL)
             AND (agent_notes IS NULL OR agent_notes NOT LIKE 'LINKEDIN-RESOLVE 2026-05-24%')
           ORDER BY
             CASE WHEN est_tc IS NULL THEN 1 WHEN est_tc >= 180000 THEN 0 ELSE 2 END,
             CASE WHEN est_tc >= 180000 THEN -est_tc ELSE est_tc END"""
    rows = cur.execute(q).fetchall()
    if only_ids:
        rows = [r for r in rows if r[0] in only_ids]
    if limit:
        rows = rows[:limit]
    return rows


def update_resolved(con, role_id, new_url, new_source_key, tactic, linkedin_url):
    note = f'LINKEDIN-RESOLVE 2026-05-24: resolved via {tactic} | original: {linkedin_url}'
    con.execute("UPDATE roles SET app_url=?, source_key=?, agent_notes=? WHERE id=?",
                (new_url, new_source_key, note, role_id))
    con.commit()


def update_unresolved(con, role_id):
    note = 'LINKEDIN-RESOLVE 2026-05-24: UNRESOLVED | tried: companies-yaml, web_fetch, careers-page | next-resort: ProxyCurl ($3) or LinkedIn-auth scrape'
    con.execute("UPDATE roles SET agent_notes=? WHERE id=?", (note, role_id))
    con.commit()


def regen_xlsx():
    import subprocess
    py = WS / 'projects/job-search/role-discovery/.venv/bin/python'
    rx = WS / 'projects/job-search/role-discovery/render_xlsx.py'
    try:
        subprocess.run([str(py), str(rx)], cwd=WS, timeout=120, capture_output=True)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--ids', type=str, default='')
    ap.add_argument('--no-xlsx', action='store_true')
    ap.add_argument('--max-seconds', type=int, default=10500)  # ~2h55m
    args = ap.parse_args()

    only_ids = set(int(x) for x in args.ids.split(',') if x.strip()) if args.ids else None

    yaml_cos = load_companies_yaml()
    roles_idx = load_latest_roles_json()
    print(f'[init] yaml companies: {len(yaml_cos)} | roles index: {len(roles_idx)}', flush=True)

    con = sqlite3.connect(DB)
    targets = fetch_targets(con, limit=args.limit or None, only_ids=only_ids)
    print(f'[init] targets: {len(targets)}', flush=True)

    start = time.time()
    resolved = 0
    unresolved = 0
    ats_breakdown = {}

    for i, (rid, company, title, est_tc, app_url) in enumerate(targets, 1):
        elapsed = time.time() - start
        if elapsed > args.max_seconds:
            print(f'[stop] time budget exhausted after {i-1} rows', flush=True)
            break
        linkedin_url = app_url or ''
        print(f'\n[{i}/{len(targets)}] id={rid} | {company} | {title}', flush=True)

        resolved_url = None
        tactic_used = None
        notes = []

        # Tactic 1
        try:
            url1, info1 = tactic1_yaml_match(company, title, yaml_cos, roles_idx)
            if info1:
                notes.append(info1)
            if url1:
                resolved_url = url1
                tactic_used = f'tactic1:{info1}'
        except Exception as e:
            notes.append(f't1-err:{e}')

        # Tactic 2
        if not resolved_url and linkedin_url:
            try:
                url2, info2 = tactic2_linkedin_fetch(linkedin_url, company, title)
                if info2:
                    notes.append(info2)
                if url2:
                    resolved_url = url2
                    tactic_used = f'tactic2:{info2}'
            except Exception as e:
                notes.append(f't2-err:{e}')

        # Tactic 4
        if not resolved_url:
            try:
                url4, info4 = tactic4_careers_page(company, title)
                if info4:
                    notes.append(info4)
                if url4:
                    resolved_url = url4
                    tactic_used = f'tactic4:{info4}'
            except Exception as e:
                notes.append(f't4-err:{e}')

        if resolved_url:
            sk = derive_source_key(resolved_url)
            ats_prefix = sk.split(':', 1)[0]
            ats_breakdown[ats_prefix] = ats_breakdown.get(ats_prefix, 0) + 1
            update_resolved(con, rid, resolved_url, sk, tactic_used, linkedin_url)
            resolved += 1
            log_line(f'{now_iso()} | id={rid} | {company} | {title} | RESOLVED via {tactic_used}: {resolved_url}')
            print(f'  -> RESOLVED ({tactic_used}): {resolved_url}', flush=True)
        else:
            update_unresolved(con, rid)
            unresolved += 1
            log_line(f'{now_iso()} | id={rid} | {company} | {title} | UNRESOLVED | notes={"; ".join(notes)}')
            print(f'  -> UNRESOLVED | {"; ".join(notes)}', flush=True)

        # xlsx regen every 10 rows to save time
        if not args.no_xlsx and i % 10 == 0:
            regen_xlsx()

    if not args.no_xlsx:
        regen_xlsx()

    result = {
        'total_attempted': resolved + unresolved,
        'resolved': resolved,
        'unresolved': unresolved,
        'ats_breakdown': ats_breakdown,
        'log_path': str(LOG),
        'elapsed_sec': int(time.time() - start),
    }
    print('\n' + json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
