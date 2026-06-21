import sqlite3, requests, re, json, time

conn = sqlite3.connect('../tracker.db'); cur = conn.cursor()
rows = cur.execute("""SELECT id, company, role, jd_url, block_reason FROM roles
    WHERE status='manual-apply'
    AND (block_reason LIKE '%linkedin-no-ats%' OR block_reason LIKE '%linkedin-stranded%' OR block_reason LIKE '%linkedin-auth-stranded%')
    ORDER BY id""").fetchall()
conn.close()

S = requests.Session()
S.headers.update({'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'})

def slugs(name):
    n = name.strip().lower()
    n = re.sub(r"[,.]", "", n)
    n = re.sub(r"\b(inc|llc|ltd|corp|corporation|company|co|group|industries|technologies|technology|solutions|the)\b", "", n)
    n = n.strip()
    base = re.sub(r"\s+", "", n)            # joined
    hyph = re.sub(r"\s+", "-", n).strip("-")  # hyphenated
    first = n.split()[0] if n.split() else base
    out = []
    for s in [base, hyph, first, name.lower().replace(" ", ""), name.lower().replace(" ", "-")]:
        s = re.sub(r"[^a-z0-9-]", "", s)
        if s and s not in out:
            out.append(s)
    return out

def probe(adapter, slug):
    urls = {
        'greenhouse': f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs',
        'ashby':      f'https://api.ashbyhq.com/posting-api/job-board/{slug}',
        'lever':      f'https://api.lever.co/v0/postings/{slug}?mode=json',
    }
    try:
        r = S.get(urls[adapter], timeout=6)
        if r.status_code == 200:
            # validate it actually has jobs / is a real board
            try:
                j = r.json()
            except Exception:
                return False, 0
            if adapter == 'greenhouse':
                n = len(j.get('jobs', []))
                return n > 0, n
            if adapter == 'ashby':
                n = len(j.get('jobs', []) or (j.get('data',{}) or {}).get('jobBoard',{}).get('jobPostings', []) if isinstance(j,dict) else [])
                # ashby posting-api returns {'jobs':[...]} 
                n = len(j.get('jobs', [])) if isinstance(j, dict) else 0
                return n > 0, n
            if adapter == 'lever':
                n = len(j) if isinstance(j, list) else 0
                return n > 0, n
        return False, 0
    except Exception:
        return False, 0

found = []
for rid, company, role, jd, br in rows:
    hit = None
    for adapter in ['greenhouse','ashby','lever']:
        for sl in slugs(company):
            ok, n = probe(adapter, sl)
            time.sleep(0.25)
            if ok:
                hit = (adapter, sl, n)
                break
        if hit:
            break
    status = f"FOUND {hit[0]}:{hit[1]} ({hit[2]} jobs)" if hit else "no-board"
    print(f"{rid:5} | {company[:24]:24} | {status}")
    if hit:
        found.append((rid, company, hit[0], hit[1], hit[2]))

print("\n=== SUMMARY: boards found ===")
for f in found:
    print(f)
json.dump([{'id':f[0],'company':f[1],'adapter':f[2],'slug':f[3],'jobs':f[4]} for f in found], open('_li_reprobe_found.json','w'), indent=2)
print(f"\nTotal probed: {len(rows)} | boards found: {len(found)}")
