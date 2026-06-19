"""
Phase B: for rows where the company slug on an ATS has been confirmed,
verify exact role match via LinkedIn JD distinctive-phrase overlap.
Quality-over-speed: writes a per-row report, commits only when ≥2 of 3
distinctive phrases match AND title overlap.
"""
import requests, re, sqlite3, json, sys, time
from datetime import datetime
H = {'User-Agent':'Mozilla/5.0'}

CONFIRMED = [
    # (row_id, linkedin_job_id, ats, slug, expected_title_keywords)
    (1036, 4371708110, 'greenhouse', 'otter', ['product manager','money platform']),
    (1056, 4394915191, 'greenhouse', 'axon', ['product manager','hardware']),
    (1140, 4351760206, 'greenhouse', 'hackerrank', ['forward deployed','engineer']),
    (1141, 4375000029, 'greenhouse', 'sixfold', ['solutions engineer']),
    (1147, 4401665335, 'ashby', 'neuralconcept', ['solutions engineer']),
    (1166, 4410197158, 'lever', 'sitetracker', ['solution architect']),
    (1213, 4386953210, 'ashby', 'moment', ['forward deployed engineer']),
    (1299, 4415429063, 'ashby', 'dust', ['solutions engineer']),
    (1320, 4384712368, 'greenhouse', 'mattermost', ['forward deployed engineer']),
    (1325, 4414925294, 'ashby', 'blaxel', ['forward deployed']),
    (1332, 4415571509, 'ashby', 'thought-machine', ['forward deployed engineer']),
    (1152, 4320282467, 'greenhouse', 'epicgames', ['integration solutions','solutions engineer']),  # likely wrong - Epic Systems not Epic Games
    (1301, 4403656824, 'lever', 'basis', ['solutions engineer']),
]

def fetch_li_jd(jid):
    r = requests.get(f'https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}', headers=H, timeout=15)
    text = re.sub(r'<[^>]+>',' ', r.text)
    text = re.sub(r'\s+',' ', text)
    return text

def extract_distinctive_phrases(jd, role_title):
    # Return 5 distinctive ≥4-word phrases. Skip generic ones.
    candidates = re.findall(r'[A-Z][a-zA-Z][a-zA-Z\-&\.\s,]{20,120}[a-zA-Z0-9]', jd)
    skip = {'product manager','equal opportunity','benefits package','show more','show less'}
    phrases = []
    for p in candidates:
        p = p.strip()
        if any(s in p.lower() for s in skip): continue
        if len(p.split()) < 4: continue
        if any(p == q for q in phrases): continue
        phrases.append(p)
        if len(phrases) >= 5: break
    return phrases

def gh_jobs(slug):
    r = requests.get(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true', headers=H, timeout=15)
    if r.status_code != 200: return []
    return r.json().get('jobs', [])

def ashby_jobs(slug):
    r = requests.get(f'https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true', headers=H, timeout=15)
    if r.status_code != 200: return []
    return r.json().get('jobs', [])

def lever_jobs(slug):
    r = requests.get(f'https://api.lever.co/v0/postings/{slug}?mode=json', headers=H, timeout=15)
    if r.status_code != 200: return []
    return r.json()

def body_of(job, ats):
    if ats == 'greenhouse':
        return re.sub(r'<[^>]+>',' ', job.get('content','') or '')
    if ats == 'ashby':
        return (job.get('descriptionPlain') or '') + ' ' + re.sub(r'<[^>]+>',' ', job.get('description','') or '')
    if ats == 'lever':
        parts = [job.get('descriptionPlain','')]
        for li in (job.get('lists') or []):
            parts.append(li.get('text','') or '')
            parts.append(re.sub(r'<[^>]+>',' ', li.get('content','') or ''))
        parts.append(re.sub(r'<[^>]+>',' ', job.get('description','') or ''))
        return ' '.join(parts)
    return ''

def title_of(j, ats):
    if ats == 'lever': return j.get('text','')
    return j.get('title','')

def url_of(j, ats, slug):
    if ats == 'greenhouse': return j.get('absolute_url')
    if ats == 'ashby': return j.get('jobUrl')
    if ats == 'lever': return j.get('hostedUrl')
    return ''

def id_of(j, ats):
    if ats == 'greenhouse': return str(j.get('id',''))
    return j.get('id','')

def location_of(j, ats):
    if ats == 'greenhouse': return j.get('location',{}).get('name','')
    if ats == 'ashby': return j.get('locationName') or ''
    if ats == 'lever': return ((j.get('categories') or {}).get('location') or '')
    return ''

def main():
    out = []
    for rid, jid, ats, slug, kw in CONFIRMED:
        print(f'\n=== rid={rid} li={jid} {ats}:{slug} ===')
        try:
            jd = fetch_li_jd(jid)
        except Exception as e:
            print(' LinkedIn fetch fail:', e); continue
        phrases = extract_distinctive_phrases(jd, '')
        print(f' phrases ({len(phrases)}):')
        for p in phrases: print(f'   - {p[:90]}')
        # Pull ATS board
        if ats == 'greenhouse': jobs = gh_jobs(slug)
        elif ats == 'ashby': jobs = ashby_jobs(slug)
        elif ats == 'lever': jobs = lever_jobs(slug)
        print(f' board jobs: {len(jobs)}')
        # Score each job
        best = None; best_score = 0; best_phrases = []
        for j in jobs:
            t = title_of(j, ats).lower()
            if not any(k in t for k in kw): continue
            body = body_of(j, ats)
            hits = [p for p in phrases if p in jd and p in body]
            # Title contribution
            tscore = sum(1 for k in kw if k in t) / max(1,len(kw))
            pscore = len(hits)
            total = pscore + tscore
            if total > best_score:
                best_score = total; best = j; best_phrases = hits
        if best:
            print(f' BEST: {title_of(best, ats)} | {location_of(best, ats)} | score={best_score:.2f} | phrase_hits={len(best_phrases)}')
            for p in best_phrases[:5]: print(f'   ✓ "{p[:80]}"')
            out.append({
                'row_id': rid, 'ats': ats, 'slug': slug,
                'job_id': id_of(best, ats), 'title': title_of(best, ats),
                'location': location_of(best, ats), 'url': url_of(best, ats, slug),
                'score': best_score, 'phrase_hits': best_phrases,
                'confidence': 'high' if (best_score >= 2.0 and len(best_phrases) >= 2) else ('medium' if best_score >= 1.5 else 'low')
            })
        else:
            print(' NO MATCH')
            out.append({'row_id': rid, 'ats': ats, 'slug': slug, 'status': 'no-match'})
        time.sleep(0.5)
    with open('projects/job-search/applications/_linkedin-phase-b-verify.json','w') as f:
        json.dump(out, f, indent=2)
    print(f'\nwrote phase-b-verify json with {len(out)} rows')

if __name__ == '__main__':
    main()
