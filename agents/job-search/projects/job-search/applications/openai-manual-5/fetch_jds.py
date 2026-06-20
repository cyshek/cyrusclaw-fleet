#!/usr/bin/env python3
import json, urllib.request, pathlib, html, re

APPS = pathlib.Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/applications/queued")

TARGETS = {
    "d23c6966-e702-4088-860b-0f529745e03c": "Product Manager, Self-Serve Business Growth Lead",
    "0f4da2b4-df8a-4560-809d-d0a6ac1ad9bc": "Product Manager, Personalization",
    "a4d772fc-1c97-43fd-8241-5e5afdc0ef51": "Program Manager, Partner Operations",
    "71004494-9a55-4ed5-b458-2ff475f0d881": "Technical Program Manager, Human Data",
    "a3f35235-c6c3-43e3-9c1c-eb844c9b6025": "Technical Program Manager, Frontier Evals",
}

def strip_html(s):
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</(p|div|li|h[1-6])>", "\n", s, flags=re.I)
    s = re.sub(r"<li[^>]*>", "- ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

url = "https://api.ashbyhq.com/posting-api/job-board/openai?includeCompensation=true"
req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(r.read())

jobs = data.get("jobs") or []
print("board returned %d jobs" % len(jobs))

by_id = {}
for j in jobs:
    jid = j.get("id") or j.get("jobId") or ""
    by_id[jid] = j

found = 0
for uuid, title in TARGETS.items():
    j = by_id.get(uuid)
    if not j:
        for jj in jobs:
            if jj.get("title", "").strip().lower() == title.strip().lower():
                j = jj
                break
    if not j:
        print("[MISS] %s %s -- not in feed" % (uuid, title))
        continue
    desc = j.get("descriptionHtml") or j.get("descriptionPlain") or j.get("description") or ""
    txt = strip_html(desc) if "<" in desc else desc
    if not txt.strip():
        print("[EMPTY] %s %s" % (uuid, title))
        continue
    out = APPS / ("openai-" + uuid)
    out.mkdir(parents=True, exist_ok=True)
    (out / "JD.md").write_text("# " + title + "\n\n" + txt + "\n")
    print("[OK] %s -> %s (%d chars)" % (uuid, out / "JD.md", len(txt)))
    found += 1

print("\nDONE: %d/%d JDs written" % (found, len(TARGETS)))
