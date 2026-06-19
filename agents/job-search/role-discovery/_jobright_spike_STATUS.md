# JobRight Spike STATUS
started: 2026-06-11 13:13 PDT
phase: setup
probes:

phase: COMPLETE (all 6 questions answered)
KEY FINDINGS:
- Public surface: Next.js __NEXT_DATA__ on /remote-jobs/<category> = 30 jobs/page server-rendered JSON, NO auth needed. Fields: jobTitle, companyName, jobLocation, publishTime, publishTimeDesc, isRemote, workModel, jobSeniority, minYearsOfExperience, h1BStatus, jobSummary, requirements, applyLink.
- RECENCY: publishTime (ISO) + publishTimeDesc ("1 minute ago"); pages newest-first. product-design newest=20:12:39 (1min before fetch). EXPLICIT recency, fresh-first. This is the value.
- APPLY URL: applyLink = jobright.ai/jobs/info/<id> WRAPPER only. 100% of 60 sampled = jobright host, ZERO direct ATS. Wrapper SSR JSON has NO originalUrl/externalUrl. Real URL behind /swan/* (401) + /jobs/external client page.
- AUTH: /swan/job/detail, /swan/job/jt-apply, /swan/recommend = 401 anon. logined:false in SSR. Need session cookie for real apply URL.
- IP: Azure DC IP = clean HTTP 200, NO cloudflare/datadome challenge on public pages.
- DATA QUALITY: real direct-employer roles (Drake Software, Telix, GuidePoint), PM/Project/Design = target profile, US/remote.
VERDICT: GO-IF (need real ATS URL recovery) — public feed = great DISCOVERY/recency, but apply-URL is wrapped behind auth.
