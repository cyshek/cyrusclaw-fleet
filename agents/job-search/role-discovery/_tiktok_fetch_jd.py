#!/usr/bin/env python3
"""Fetch a TikTok (lifeattiktok) JD via the authenticated OpenClaw browser and
write applications/queued/tiktok-<jobid>/JD.md. Used to stage JDs for the
referral auto-apply scale batch (tiktok-scale, 2026-06-02)."""
import os, re, sys, time
from pathlib import Path
sys.path.insert(0, '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery')
from playwright.sync_api import sync_playwright

ROOT = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search'
CDP = "http://127.0.0.1:18800"


def fetch(job_id, title=""):
    out = Path(ROOT) / "applications" / "queued" / f"tiktok-{job_id}"
    out.mkdir(parents=True, exist_ok=True)
    jd_file = out / "JD.md"
    with sync_playwright() as pw:
        b = pw.chromium.connect_over_cdp(CDP)
        page = b.contexts[0].new_page()
        try:
            page.goto(f"https://lifeattiktok.com/position/{job_id}/detail",
                      wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            # JD body renders in a content container; grab the main article text.
            txt = page.evaluate(r"""()=>{
              let best=null, bestLen=1e9;
              document.querySelectorAll('div,section,article').forEach(e=>{
                const t=e.innerText||'';
                if(/Responsibilit|Minimum Qualif|Qualifications/i.test(t)
                   && t.length>250 && t.length<bestLen){ best=t; bestLen=t.length; }
              });
              if(best) return best;
              return document.body.innerText;}""")
            h1 = page.evaluate("()=>{const h=document.querySelector('h1');return h?h.innerText.trim():''}")
        finally:
            page.close()
    title = title or h1 or f"TikTok role {job_id}"
    # trim nav/footer noise: keep from first Responsibilit/About to end-ish
    body = txt
    m = re.search(r'(About\s|Responsibilit|Minimum Qualif|Job Description)', body)
    if m:
        body = body[m.start():]
    body = body[:6000]
    jd_file.write_text(f"# {title}\n\n{body}\n")
    print(f"OK {job_id}: JD.md {len(body)} chars title={title[:50]!r}")
    return len(body)


if __name__ == "__main__":
    job_id = sys.argv[1]
    title = sys.argv[2] if len(sys.argv) > 2 else ""
    n = fetch(job_id, title)
    sys.exit(0 if n > 150 else 2)
