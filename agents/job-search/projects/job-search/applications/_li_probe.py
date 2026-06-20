#!/usr/bin/env python
"""Quick LinkedIn JD extractor + ATS prober."""
import sys, re, urllib.request, urllib.parse, json, ssl

UA = "Mozilla/5.0"

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
            return r.read().decode("utf-8", errors="replace"), r.getcode()
    except Exception as e:
        return f"ERR:{e}", 0

def linkedin_jd(linkedin_id):
    html, _ = fetch(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{linkedin_id}")
    m = re.search(r'show-more-less-html__markup[^>]*>(.*?)</div>', html, re.DOTALL)
    if not m: return None, None
    text = re.sub(r'<[^>]+>', ' ', m.group(1))
    text = re.sub(r'\s+', ' ', text).strip()
    # title
    tm = re.search(r'top-card-layout__title[^>]*>([^<]+)<', html)
    title = tm.group(1).strip() if tm else None
    # location
    lm = re.search(r'topcard__flavor topcard__flavor--bullet[^>]*>([^<]+)<', html)
    loc = lm.group(1).strip() if lm else None
    return {"title": title, "loc": loc, "body": text}, html

def probe(slug, ats):
    if ats == "gh":
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    elif ats == "ashby":
        url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    elif ats == "lever":
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    elif ats == "smartrecruiters":
        url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=200"
    else:
        return None
    body, code = fetch(url)
    if code != 200: return None
    try:
        return json.loads(body)
    except: return None

def search_ats(slug, ats, query_terms):
    """Search ATS by company slug; return list of (title, url, location)."""
    data = probe(slug, ats)
    if not data: return []
    results = []
    if ats == "gh":
        for j in data.get("jobs", []):
            title = j.get("title", "")
            if all(t.lower() in title.lower() for t in query_terms):
                results.append((title, j.get("absolute_url"), j.get("location", {}).get("name")))
    elif ats == "ashby":
        for j in data.get("jobs", []):
            title = j.get("title", "")
            if all(t.lower() in title.lower() for t in query_terms):
                results.append((title, j.get("jobUrl"), j.get("locationName")))
    elif ats == "lever":
        for j in data:
            title = j.get("text", "")
            if all(t.lower() in title.lower() for t in query_terms):
                loc = j.get("categories", {}).get("location")
                results.append((title, j.get("hostedUrl"), loc))
    elif ats == "smartrecruiters":
        for j in data.get("content", []):
            title = j.get("name", "")
            if all(t.lower() in title.lower() for t in query_terms):
                loc = j.get("location", {}).get("city")
                results.append((title, f"https://jobs.smartrecruiters.com/{slug}/{j['id']}", loc))
    return results

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "jd":
        d, _ = linkedin_jd(sys.argv[2])
        if d:
            print("TITLE:", d["title"])
            print("LOC:", d["loc"])
            print("BODY:", d["body"][:1500])
        else:
            print("no JD found")
    elif cmd == "probe":
        slug, ats = sys.argv[2], sys.argv[3]
        d = probe(slug, ats)
        if d is None: print("404 or fail")
        else:
            if ats == "gh": print(f"jobs={len(d.get('jobs',[]))}")
            elif ats == "ashby": print(f"jobs={len(d.get('jobs',[]))}")
            elif ats == "lever": print(f"jobs={len(d)}")
            elif ats == "smartrecruiters": print(f"jobs={d.get('totalFound')}")
    elif cmd == "search":
        # search slug ats term1 term2...
        slug, ats = sys.argv[2], sys.argv[3]
        terms = sys.argv[4:]
        for r in search_ats(slug, ats, terms):
            print(r)
