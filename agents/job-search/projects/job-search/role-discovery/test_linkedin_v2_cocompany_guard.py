import linkedin_ats_resolver_v2 as m

# Force the Brave-API path with a dummy key and stub the network + validation.
m._brave_api_key = lambda: "TESTKEY"
m._validate_ats_url = lambda kind, url, title: 1.0  # title always matches

def run(company, title, urls):
    m._brave_api_urls = lambda q, k: urls
    res = m.Resolution(role_id=0, company=company, role_title=title)
    ok = m.tactic3_websearch(res)
    return ok, res.ats_url

cases = [
    # (label, company, title, [candidate urls], expect_resolved)
    ("Xe.com->Easygenerator (FP)", "Xe.com", "Product Manager",
     ["https://jobs.ashbyhq.com/Easygenerator/e2c07a5d-0319-4007-a525-d27a1bf3c664"], False),
    ("Gen->ServiceNow gen-ai (FP)", "Gen", "Forward Deployed Engineer",
     ["https://jobs.smartrecruiters.com/ServiceNow/744000112870877-forward-deployed-software-engineer-gen-ai"], False),
    ("Eurofins->Eurofins (legit)", "Eurofins", "Solution Architect",
     ["https://jobs.smartrecruiters.com/Eurofins/743999689361520-solution-architect-soa-center-of-excellence"], True),
    ("Valence->jobs-valence (legit)", "Valence", "Solutions Engineer, AI",
     ["https://jobs.ashbyhq.com/jobs-valence/89d325c5-93f0-47b6-8806-ff6258e51a56"], True),
    ("Parloa embed (legit)", "Parloa", "Forward Deployed Engineer, VoIP",
     ["https://boards.greenhouse.io/embed/job_app?for=parloa&token=4604587101"], True),
    ("Cisco workday (legit)", "Cisco", "Engineering Product Manager",
     ["https://cisco.wd5.myworkdayjobs.com/Cisco_Careers/job/Engineering-Product-Manager--Cloud-Control-Studio_2016349"], True),
]

fail = 0
for label, co, title, urls, expect in cases:
    ok, url = run(co, title, urls)
    status = "PASS" if ok == expect else "FAIL"
    if ok != expect: fail += 1
    print("%-4s %-32s resolved=%s expect=%s url=%s" % (status, label, ok, expect, url or ""))
print()
print("ALL PASS" if fail == 0 else ("%d FAILURES" % fail))
raise SystemExit(1 if fail else 0)
