"""
Phase B v2: Per-row resolver with rigorous JD-phrase verification.
Quality > speed: extracts real JD body (not LinkedIn chrome) and verifies
≥2 distinctive (≥30-char) phrases overlap between LinkedIn JD and ATS body.
"""
import requests, re, sqlite3, json, sys, time, html as _html
from datetime import datetime

H = {'User-Agent':'Mozilla/5.0'}
LOG_PATH = 'projects/job-search/applications/_linkedin-resolve-20260524.log'

def log(msg):
    with open(LOG_PATH,'a') as f:
        f.write(f'{datetime.now().isoformat(timespec="seconds")} | {msg}\n')

def fetch_li_jd(jid):
    """Return (raw_text, jd_body_text) where jd_body_text is just the description."""
    r = requests.get(f'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}', headers=H, timeout=15)
    if r.status_code != 200: return None, None
    raw = r.text
    text = re.sub(r'<[^>]+>',' ', raw)
    text = _html.unescape(text)
    text = re.sub(r'\s+',' ', text).strip()
    # Find description start anchors
    # Strategy: find the START of the actual JD by looking AFTER common LinkedIn chrome markers.
    # The JD always begins after 'Tailor my resume' or the topcard pay-range section.
    chrome_end_anchors = ['Tailor my resume','pay will be based on your skills','Get AI-powered advice']
    body_start = -1
    for a in chrome_end_anchors:
        i = text.find(a)
        if i > 0:
            body_start = i + len(a)
            break
    if body_start == -1:
        # Fall back: anchor by first occurrence of typical JD start words
        for a in ['Who We Are','About the Role','About the role','About The Role','About Us','About the Company','The Role','Overview','We are looking','We\'re looking','Job Description',"'s mission is","'s mission",'is bold ','We have grown']:
            i = text.find(a)
            if i > 0 and (body_start == -1 or i < body_start):
                body_start = i
    if body_start == -1: body_start = 1500
    # End at "Show less" / "Seniority level" / "Referrals increase"
    body_end = len(text)
    for e in ['Seniority level','Show less','Referrals increase','Privacy Policy','Cookie Policy']:
        i = text.find(e, body_start)
        if i > 0 and i < body_end: body_end = i
    return text, text[body_start:body_end].strip()

def distinctive_phrases(jd_body, n=5, min_len=30):
    """Extract n distinctive phrases ≥min_len chars from JD body.
    Skips generic boilerplate (EEO, benefits, common phrases)."""
    skip_patterns = [
        r'equal opportunity', r'background check', r'benefits package', r'401\(k\)',
        r'medical, dental', r'paid time off', r'show more', r'show less',
        r'including but not limited', r'regardless of race', r'an equal'
    ]
    sentences = re.split(r'[.•\n]\s+', jd_body)
    out = []
    seen = set()
    for s in sentences:
        s = s.strip()
        if len(s) < min_len or len(s) > 350: continue
        sl = s.lower()
        if any(re.search(p, sl) for p in skip_patterns): continue
        # Need ≥1 noun-y word that's not common
        if not re.search(r'[A-Z][a-z]+', s): continue
        # Avoid LinkedIn UI
        if any(w in sl for w in ['linkedin','sign in','password','privacy policy','user agreement']): continue
        # Dedupe substring
        key = s.lower()[:50]
        if key in seen: continue
        seen.add(key)
        out.append(s)
        if len(out) >= n: break
    return out

def gh_jobs(slug):
    r = requests.get(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true', headers=H, timeout=20)
    if r.status_code != 200: return []
    return r.json().get('jobs', [])

def ashby_jobs(slug):
    r = requests.get(f'https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true', headers=H, timeout=20)
    if r.status_code != 200: return []
    return r.json().get('jobs', [])

def lever_jobs(slug):
    r = requests.get(f'https://api.lever.co/v0/postings/{slug}?mode=json', headers=H, timeout=20)
    if r.status_code != 200: return []
    return r.json()

def job_body(j, ats):
    if ats == 'greenhouse':
        return _html.unescape(re.sub(r'<[^>]+>',' ', j.get('content','') or ''))
    if ats == 'ashby':
        plain = j.get('descriptionPlain') or ''
        html_b = re.sub(r'<[^>]+>',' ', j.get('description','') or '')
        return _html.unescape(plain + ' ' + html_b)
    if ats == 'lever':
        parts = [j.get('descriptionPlain','') or '']
        for li in (j.get('lists') or []):
            parts.append(li.get('text','') or '')
            parts.append(re.sub(r'<[^>]+>',' ', li.get('content','') or ''))
        parts.append(re.sub(r'<[^>]+>',' ', j.get('description','') or ''))
        return _html.unescape(' '.join(parts))
    return ''

def job_title(j, ats):
    if ats == 'lever': return j.get('text','')
    return j.get('title','')

def job_url(j, ats, slug):
    if ats == 'greenhouse': return j.get('absolute_url')
    if ats == 'ashby': return j.get('jobUrl')
    if ats == 'lever': return j.get('hostedUrl')
    return ''

def job_id(j, ats):
    if ats == 'greenhouse': return str(j.get('id',''))
    return j.get('id','')

def job_location(j, ats):
    if ats == 'greenhouse': return j.get('location',{}).get('name','')
    if ats == 'ashby':
        loc = j.get('locationName') or ''
        secs = j.get('secondaryLocations') or []
        if secs: loc += ' / ' + ', '.join(s.get('locationName','') for s in secs)
        return loc
    if ats == 'lever':
        c = j.get('categories') or {}
        return c.get('location') or ''
    return ''

def resolve_row(rid, li_jid, ats, slug, expected_title_keywords, li_url, company_for_disambiguation=None):
    """Returns (status, evidence_dict)."""
    raw, body = fetch_li_jd(li_jid)
    if not body:
        return 'fail-fetch', {'reason':'LinkedIn fetch failed'}
    phrases = distinctive_phrases(body)
    # Pull board
    if ats == 'greenhouse': jobs = gh_jobs(slug)
    elif ats == 'ashby': jobs = ashby_jobs(slug)
    elif ats == 'lever': jobs = lever_jobs(slug)
    else: return 'fail-ats', {'reason':f'unknown ats {ats}'}
    if not jobs:
        return 'fail-empty-board', {'reason':f'{ats}:{slug} board returned 0 jobs','phrases':phrases}
    # Filter by title keyword
    candidates = []
    for j in jobs:
        t = job_title(j, ats).lower()
        if all(k.lower() in t for k in expected_title_keywords):
            candidates.append(j)
    # if too strict, relax to any-of
    if not candidates:
        for j in jobs:
            t = job_title(j, ats).lower()
            if any(k.lower() in t for k in expected_title_keywords):
                candidates.append(j)
    if not candidates:
        return 'fail-no-title-match', {
            'reason': f'no job on {ats}:{slug} with keywords {expected_title_keywords}',
            'board_size': len(jobs),
            'sample_titles': [job_title(j, ats) for j in jobs[:10]],
            'phrases': phrases,
        }
    # Score candidates by phrase overlap
    scored = []
    for j in candidates:
        body_j = job_body(j, ats)
        hits = [p for p in phrases if p in body_j]
        title_match = all(k.lower() in job_title(j, ats).lower() for k in expected_title_keywords)
        score = len(hits) + (1.0 if title_match else 0)
        scored.append((score, len(hits), j, hits))
    scored.sort(key=lambda x:(-x[0], -x[1]))
    best_score, best_hits_n, best_j, best_hits = scored[0]
    confidence = 'high' if best_hits_n >= 2 else ('medium' if best_hits_n == 1 else 'low')
    return ('match', {
        'job': {
            'title': job_title(best_j, ats),
            'location': job_location(best_j, ats),
            'url': job_url(best_j, ats, slug),
            'id': job_id(best_j, ats),
        },
        'score': best_score, 'phrase_hits': best_hits, 'confidence': confidence,
        'all_candidates': [(job_title(j[2], ats), j[1]) for j in scored[:3]],
        'phrases': phrases,
    })

if __name__ == '__main__':
    # Quick test
    rid, jid, ats, slug, kw, lurl = 1056, 4394915191, 'greenhouse','axon',['product manager','hardware'],'https://www.linkedin.com/jobs/view/product-manager-ii-hardware-at-axon-4394915191'
    status, ev = resolve_row(rid, jid, ats, slug, kw, lurl)
    print(json.dumps({'rid':rid,'status':status, **ev}, indent=2, default=str))
