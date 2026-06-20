"""Phase C: per-row careers-page sniff + ATS verify for rows where slug-sweep
returned no hit. Uses 8-tactic approach but compressed:
  1. Fetch LinkedIn JD body
  2. Slug-guess across greenhouse/ashby/lever (extended list)
  3. Probe www.<co>.com and careers.<co>.com for ATS link
  4. If ATS link found, search board for title-match + phrase-verify
  5. Commit high confidence, else UNRESOLVED with full evidence
"""
import requests, re, sqlite3, json, sys, time, html as _html
from datetime import datetime
sys.path.insert(0,'projects/job-search')
from linkedin_phase_b2 import fetch_li_jd, distinctive_phrases, gh_jobs, ashby_jobs, lever_jobs, job_body, job_title, job_url, job_id, job_location

H = {'User-Agent':'Mozilla/5.0'}

def slugify(name):
    base = re.sub(r'\([^)]*\)','', name)   # strip "(YC S21)" etc
    base = re.sub(r'[^a-zA-Z0-9 -]','', base).strip()
    parts = base.lower().split()
    cands = []
    cands.append(''.join(parts))
    cands.append('-'.join(parts))
    if len(parts) >= 2:
        cands.append(parts[0])  # just first word
    # remove common suffixes
    for s in ['inc','llc','co','corp','ltd','technologies','tech','ai','app','io','hq']:
        if s in parts:
            cands.append(''.join(p for p in parts if p != s))
            cands.append('-'.join(p for p in parts if p != s))
    return list(dict.fromkeys(c for c in cands if c and len(c) > 1))

def probe_ats(slug):
    """Return (ats, valid_url_or_None) for each test."""
    hits = []
    for ats, url in [
        ('greenhouse', f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs'),
        ('ashby', f'https://api.ashbyhq.com/posting-api/job-board/{slug}'),
        ('lever', f'https://api.lever.co/v0/postings/{slug}?mode=json'),
    ]:
        try:
            r = requests.get(url, headers=H, timeout=8)
            if r.status_code == 200 and len(r.text) > 80:
                try:
                    d = r.json()
                    if ats == 'greenhouse' and d.get('jobs') is not None:
                        hits.append((ats, slug, len(d.get('jobs',[]))))
                    elif ats == 'ashby' and d.get('jobs') is not None:
                        hits.append((ats, slug, len(d.get('jobs',[]))))
                    elif ats == 'lever' and isinstance(d, list):
                        hits.append((ats, slug, len(d)))
                except: pass
        except: pass
    return hits

def find_careers_ats(company_name):
    """Probe domains for ATS links. Return list of (ats, slug) tuples."""
    parts = re.sub(r'[^a-zA-Z0-9]',' ', company_name).split()
    domain_bases = [''.join(parts).lower(),
                    '-'.join(parts).lower(),
                    parts[0].lower() if parts else '',
                    ''.join(parts[:2]).lower() if len(parts)>=2 else '']
    domain_bases = [d for d in dict.fromkeys(domain_bases) if d]
    discovered = []
    for base in domain_bases:
        for tld in ['com','io','ai','co','app','dev','so']:
            for prefix in ['https://www.','https://','https://careers.','https://jobs.']:
                url = f'{prefix}{base}.{tld}'
                try:
                    r = requests.get(url, headers=H, timeout=5, allow_redirects=True)
                    if r.status_code == 200 and len(r.text) > 500:
                        # search HTML for ATS URLs
                        for m in re.finditer(r'https?://(?:boards|jobs|api|job-boards)[.-]?(?:greenhouse|lever|ashby|smartrecruiters|workable)(?:\.io|hq\.com|\.co)[/?][^"\'<>\s]*', r.text):
                            u = m.group(0)
                            # extract slug
                            ms = re.search(r'(?:greenhouse\.io|hq\.com|lever\.co|smartrecruiters\.com|workable\.com)/(?:boards/)?([a-zA-Z0-9_-]+)', u)
                            if ms:
                                slug = ms.group(1)
                                if 'greenhouse' in u: discovered.append(('greenhouse', slug))
                                elif 'ashby' in u: discovered.append(('ashby', slug))
                                elif 'lever' in u: discovered.append(('lever', slug))
                        # try /careers subpath
                        if '/careers' not in r.url:
                            for cpath in ['/careers','/jobs','/about/careers']:
                                try:
                                    r2 = requests.get(url+cpath, headers=H, timeout=5, allow_redirects=True)
                                    if r2.status_code == 200:
                                        for m in re.finditer(r'https?://(?:boards|jobs|api|job-boards)[.-]?(?:greenhouse|lever|ashby|smartrecruiters|workable)(?:\.io|hq\.com|\.co)[/?][^"\'<>\s]*', r2.text):
                                            u = m.group(0)
                                            ms = re.search(r'(?:greenhouse\.io|hq\.com|lever\.co|smartrecruiters\.com|workable\.com)/(?:boards/)?([a-zA-Z0-9_-]+)', u)
                                            if ms:
                                                slug = ms.group(1)
                                                if 'greenhouse' in u: discovered.append(('greenhouse', slug))
                                                elif 'ashby' in u: discovered.append(('ashby', slug))
                                                elif 'lever' in u: discovered.append(('lever', slug))
                                except: pass
                        return list(dict.fromkeys(discovered)), url  # return on first successful domain
                except: pass
    return discovered, None

def find_best_role(ats, slug, jd_body, expected_kw):
    if ats == 'greenhouse': jobs = gh_jobs(slug)
    elif ats == 'ashby': jobs = ashby_jobs(slug)
    elif ats == 'lever': jobs = lever_jobs(slug)
    else: return None, 0, []
    if not jobs: return None, 0, []
    phrases = distinctive_phrases(jd_body)
    candidates = [j for j in jobs if any(k.lower() in job_title(j, ats).lower() for k in expected_kw)]
    if not candidates: return None, 0, phrases
    best = None; best_hits = []
    for j in candidates:
        body = job_body(j, ats)
        hits = [p for p in phrases if p in body]
        if len(hits) > len(best_hits):
            best = j; best_hits = hits
    if best is None: best = candidates[0]
    return best, len(best_hits), best_hits

def resolve(rid, jid, company, expected_kw, lurl):
    print(f'\n=== rid={rid} | {company} ===')
    raw, body = fetch_li_jd(jid)
    if not body:
        print(' LinkedIn fetch failed')
        return None
    tactics_tried = []
    # tactic 1: extended slug guess
    tactics_tried.append('slug-guess')
    for slug in slugify(company):
        for ats, s2, n in probe_ats(slug):
            print(f' slug-hit {ats}:{s2} ({n} jobs)')
            best, hits_n, hits = find_best_role(ats, s2, body, expected_kw)
            if best and hits_n >= 2:
                print(f'  HIGH match: {job_title(best, ats)} | {job_location(best, ats)} | hits={hits_n}')
                return ('match', ats, s2, best, hits, body, tactics_tried)
            if best:
                print(f'  weak: {job_title(best, ats)} hits={hits_n}')
    # tactic 2: careers-page sniff
    tactics_tried.append('careers-page-sniff')
    discovered, domain_used = find_careers_ats(company)
    print(f' careers sniff: domain={domain_used}, discovered={discovered}')
    for ats, slug in discovered:
        best, hits_n, hits = find_best_role(ats, slug, body, expected_kw)
        if best and hits_n >= 2:
            print(f'  HIGH match: {job_title(best, ats)} | {job_location(best, ats)} | hits={hits_n}')
            return ('match', ats, slug, best, hits, body, tactics_tried)
        if best:
            print(f'  weak via careers: {ats}:{slug} {job_title(best, ats)} hits={hits_n}')
    return ('no-match', None, None, None, None, body, tactics_tried)

if __name__ == '__main__':
    ROWS = [
        (1111, 4414130676, 'Checkmarx', ['solutions engineer'], 'https://www.linkedin.com/jobs/view/solutions-engineer-at-checkmarx-4414130676'),
        (1121, 4414950405, 'Point & Pay', ['solutions engineer'], 'https://www.linkedin.com/jobs/view/solutions-engineer-at-point-pay-4414950405'),
        (1125, 4411960390, 'Ascend', ['solutions engineer'], 'https://www.linkedin.com/jobs/view/solutions-engineer-at-ascend-4411960390'),
        (1129, 4403171502, 'Alibaba Cloud', ['solutions architect'], 'https://www.linkedin.com/jobs/view/solutions-architect-at-alibaba-cloud-4403171502'),
        (1136, 4413800585, 'Smartcat', ['forward deployed engineer'], 'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-smartcat-4413800585'),
        (1152, 4320282467, 'Epic', ['integration','solutions engineer'], 'https://www.linkedin.com/jobs/view/integration-solutions-engineer-at-epic-4320282467'),
        (1166, 4410197158, 'Sitetracker', ['solution architect'], 'https://www.linkedin.com/jobs/view/solution-architect-at-sitetracker-4410197158'),
        (1201, 4415149388, 'Synth', ['forward deployed engineer'], 'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-synth-yc-s21-4415149388'),
        (1209, 4410340265, 'HappyRobot', ['forward deployed engineer'], 'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-happyrobot-4410340265'),
        (1210, 4414759236, 'Easol', ['forward deployed engineer'], 'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-easol-4414759236'),
        (1213, 4386953210, 'Moment', ['forward deployed engineer'], 'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-moment-4386953210'),
        (1243, 4403640464, 'Daloopa', ['product manager'], 'https://www.linkedin.com/jobs/view/product-manager-at-daloopa-4403640464'),
        (1244, 4413787223, 'Bear Robotics', ['product manager'], 'https://www.linkedin.com/jobs/view/product-manager-at-bear-robotics-4413787223'),
        (1254, 4379884400, 'Sportworks', ['product manager','hardware'], 'https://www.linkedin.com/jobs/view/product-manager-hardware-at-sportworks-4379884400'),
        (1301, 4403656824, 'Basis', ['solutions engineer'], 'https://www.linkedin.com/jobs/view/solutions-engineer-at-basis-4403656824'),
        (1303, 4415403081, 'Cloudera Government Solutions', ['solutions engineer'], 'https://www.linkedin.com/jobs/view/solutions-engineer-at-cloudera-government-solutions-4415403081'),
        (1304, 4373720490, 'Weights & Biases', ['solutions engineer'], 'https://www.linkedin.com/jobs/view/ai-solutions-engineer-post-sales-scale-w-b-at-weights-biases-4373720490'),
        (1320, 4384712368, 'Mattermost', ['forward deployed engineer'], 'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-mattermost-4384712368'),
        (1322, 4412021189, 'AVSystem', ['forward deployed engineer'], 'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-avsystem-4412021189'),
        (1333, 4393947587, 'Stuut', ['forward deployed engineer'], 'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-stuut-4393947587'),
    ]
    results = {}
    for r in ROWS:
        try:
            out = resolve(*r)
            results[r[0]] = out
        except Exception as e:
            print(f' ERR rid={r[0]}: {e}')
            results[r[0]] = None
        time.sleep(0.3)
    # save
    with open('projects/job-search/applications/_linkedin-phase-c-results.json','w') as f:
        def ser(o):
            try: json.dumps(o); return o
            except: return str(o)
        json.dump({k: (v[:5] if v else None) for k,v in results.items()}, f, default=ser, indent=2)
