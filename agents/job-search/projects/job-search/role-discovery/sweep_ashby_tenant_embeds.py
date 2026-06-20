"""sweep_ashby_tenant_embeds.py — sweep candidate Ashby tenants to detect
which publish their hosted-form on the tenant's own public website (so the
standard reCAPTCHA Enterprise v3 wall on jobs.ashbyhq.com/<tenant>/<id>/application
can be bypassed). Run by chain `ashby-tenant-embed-2026-05-30`. To add a new
tenant to TENANTS_WITH_SAMPLES, drop in (tenant_slug, sample_job_uuid, sample_role_title).

Follow-up step: run sweep_ashby_tenant_embeds_enrich.py against the JSON output
to attach CDP-render probes (Chrome on port 18802) before promoting a tenant
into ashby_tenant_embed_registry.json.
"""
"""Sweep v2: differential test + slug heuristics + render-time probe.

Strategy per tenant:
  1. GraphQL → publicWebsite, customJobsPageUrl, name.
  2. Build candidate URL list (UUID-based + name-slug + customJobsPageUrl variants).
  3. For each candidate: GET (static HTML). Reject if redirects back to ashbyhq.com.
  4. Differential: also GET <base>/careers/<random-bogus-jobid>; if both 200 with no Ashby
     refs distinction, the page is probably a generic "page exists" fallback (skip).
  5. For passing candidates: scan static HTML for ashby embed signals + captcha scripts.
  6. Mark candidate as "embed_likely" if has ashby refs AND is differentiable AND no captcha.
"""
import json, re, requests, sys, time, uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"

TENANTS_WITH_SAMPLES = [
    ("anrok", "40367604-03ac-459e-9ac7-880fa8497f4e", "Solutions Engineer Pre Sales"),
    ("artisan", "558908d9-bbbb-4d98-9e8c-a03cc647fcba", "Forward Deployed Engineer"),
    ("assorthealth", "8fd31df0-056b-4cd4-99f4-ad9b7bd91306", "Solutions Engineer"),
    ("blacksmith", "915282a3-c12a-4ae8-9483-3f4b02a2e8ff", "Solutions Engineer"),
    ("brainco", "fe8d9afb-afd6-424e-aae4-9f31d6d60426", "Product Manager"),
    ("braintrust", "b2131234-080c-4c5b-85e1-56e3edafa4e3", "Customer Solutions Architect"),
    ("brellium", "ec618c95-e55b-433f-84b7-c7a2c9cfa4c5", "Forward Deployed Engineer"),
    ("brettonai", "b21f7919-92f0-4de8-bd76-daeb16341a31", "Forward Deployed Engineer"),
    ("claylabs", "13af486b-f105-443f-94f2-29206afb9a77", "Solutions Engineer"),
    ("coframe", "e618c66b-0bcc-4ace-8f7f-5b4d31e8632c", "Solutions Engineer"),
    ("console", "395c3f5b-759f-4bf1-b6ed-38db7f0c76ee", "Forward Deployed Engineer"),
    ("depthfirst", "b3664dd2-4d2c-4a06-9b9d-3f2a0762f7cb", "Solutions Engineer"),
    ("distyl", "ec9e338a-4040-4aa2-b049-424cd343f5f5", "Forward Deployed Engineer"),
    ("dust", "b310c837-22e8-4d23-8a5a-d0b1f71fa1db", "Solutions Engineer"),
    ("eliseai", "d400f45b-bc78-41c2-96ab-9c6c9eaecf06", "Solutions Engineer Implementation Delivery Housing"),
    ("fluency", "3a8b7396-eacd-43c7-a599-5b73f7eff752", "Forward Deployed Engineer"),
    ("fonoa", "d95f9ab3-20f9-4846-93f9-d21b2fa4fbf9", "Solutions Engineer"),
    ("happyrobot.ai", "ca2ec773-fa00-4b9e-a439-200599e4f0cf", "Forward Deployed Engineer"),
    ("hcompany", "e578da08-d9b5-4c4b-ac55-4f307a41f647", "Forward Deployed Engineer"),
    ("higharc", "6e1c2e07-b812-4e3e-ae44-9a55ed2c7f3f", "Solutions Engineer"),
    ("lancedb", "e999bd37-156a-4d22-8dc8-8ac978f8cc72", "Forward Deployed Engineer"),
    ("liquid-ai", "59fd7c6b-bc62-4855-bbd5-dd0233e6c672", "Founding Product Manager"),
    ("moment", "752a96ec-5ad1-456e-a98d-6c64c6dfa256", "Forward Deployed Engineer"),
    ("notion", "fede5201-c97f-4492-bfa6-66da7afbb068", "Solutions Engineer Commercial"),
    ("picogrid", "01f18b49-daf2-411e-ae50-f22f4496b678", "Forward Deployed Engineer"),
    ("plain", "8b47cc66-ddca-4c4b-943f-1bd2d7f1d7e5", "Solutions Engineer"),
    ("restate", "c9419551-7f51-4691-8ba9-d80a27f1e284", "Solutions Engineer"),
    ("snowflake", "3f8a210b-9003-489a-91c8-e3f0abeee1fc", "Product Manager Metadata Platform"),
    ("speak", "59865014-2fe7-434e-b30f-72925f052991", "Product Manager"),
    ("tessera-labs", "ea05dfd6-92d7-4ccc-aa53-2f31a85928c5", "Product Manager"),
    ("thought-machine", "c6d119df-b5e3-4d94-8a4f-22d5040a0924", "Forward Deployed Engineer"),
]

GQL_URL = "https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiOrganizationFromHostedJobsPageName"
GQL_QUERY = """
query ApiOrganizationFromHostedJobsPageName($organizationHostedJobsPageName: String!) {
  organization: organizationFromHostedJobsPageName(organizationHostedJobsPageName: $organizationHostedJobsPageName) {
    name
    publicWebsite
    customJobsPageUrl
  }
}
"""
CAPTCHA_RX = re.compile(r"(recaptcha|hcaptcha|turnstile|challenges\.cloudflare\.com|cf-turnstile)", re.I)
ASHBY_REF_RX = re.compile(r"(_systemfield_resume|jobs\.ashbyhq\.com|ashby-job-board|data-ashby|ashby_embed)", re.I)

def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s

def gql_org(tenant):
    try:
        r = requests.post(GQL_URL,
                          json={"operationName": "ApiOrganizationFromHostedJobsPageName",
                                "variables": {"organizationHostedJobsPageName": tenant},
                                "query": GQL_QUERY},
                          timeout=15,
                          headers={"User-Agent": UA, "Content-Type": "application/json"})
        if r.status_code != 200:
            return None, f"gql {r.status_code}"
        return (r.json().get("data", {}).get("organization") or {}), None
    except Exception as e:
        return None, f"gql exc: {e}"

def http_get(url, timeout=15):
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True,
                         headers={"User-Agent": UA})
        return {"status": r.status_code, "final_url": r.url,
                "html": r.text if r.status_code == 200 else "",
                "len": len(r.text)}
    except Exception as e:
        return {"status": None, "final_url": None, "html": "", "len": 0, "error": str(e)}

def probe_tenant(tenant, job_id, role_title):
    out = {"tenant": tenant, "sample_job_id": job_id, "sample_role_title": role_title,
           "publicWebsite": None, "customJobsPageUrl": None, "org_name": None,
           "candidates": [], "winner": None,
           "verdict": "no_embed", "verdict_reason": "",
           "errors": []}

    org, err = gql_org(tenant)
    if err:
        out["errors"].append(err)
    if not org:
        out["verdict_reason"] = "gql_failed"
        return out
    out["publicWebsite"] = org.get("publicWebsite")
    out["customJobsPageUrl"] = org.get("customJobsPageUrl")
    out["org_name"] = org.get("name")

    # Build candidates
    cands = []
    role_slug = slugify(role_title)
    if out["customJobsPageUrl"]:
        b = out["customJobsPageUrl"].rstrip("/")
        cands += [f"{b}/{job_id}", f"{b}/{role_slug}", f"{b}/{job_id}/application"]
    if out["publicWebsite"]:
        b2 = out["publicWebsite"].rstrip("/")
        cands += [f"{b2}/careers/{job_id}",
                  f"{b2}/careers/{role_slug}",
                  f"{b2}/careers/{job_id}/application",
                  f"{b2}/jobs/{job_id}",
                  f"{b2}/jobs/{role_slug}"]
    seen = set(); cands = [c for c in cands if not (c in seen or seen.add(c))]

    bogus_id = str(uuid.uuid4())
    for url in cands:
        rec = {"url": url}
        res = http_get(url)
        rec.update(res); rec.pop("html", None)
        # Reject if redirected back to ashbyhq.com
        final = res.get("final_url") or ""
        if "ashbyhq.com" in final and "ashbyhq.com" not in url:
            rec["reject"] = "redirect_to_ashby"
            out["candidates"].append(rec)
            continue
        if res.get("status") != 200:
            rec["reject"] = f"http_{res.get('status')}"
            out["candidates"].append(rec)
            continue
        html = res.get("html") or ""
        ashby_refs = bool(ASHBY_REF_RX.search(html))
        captcha_hits = sorted(set(CAPTCHA_RX.findall(html)))
        rec["ashby_refs"] = ashby_refs
        rec["captcha"] = captcha_hits
        rec["has_resume_input"] = '_systemfield_resume' in html
        # Differential test: GET same path but with bogus job_id
        bogus_url = url.replace(job_id, bogus_id) if job_id in url else None
        differentiated = None
        if bogus_url and bogus_url != url:
            bres = http_get(bogus_url, timeout=10)
            differentiated = (bres.get("status") != 200) or (abs((bres.get("len") or 0) - res.get("len", 0)) > 500)
            rec["bogus_url"] = bogus_url
            rec["bogus_status"] = bres.get("status")
            rec["differentiated"] = differentiated
        else:
            rec["differentiated"] = None
        out["candidates"].append(rec)

    # Pick winner: a candidate with ashby_refs AND no captcha AND differentiated != False
    for c in out["candidates"]:
        if c.get("reject"):
            continue
        if c.get("ashby_refs") and not c.get("captcha") and c.get("differentiated") is not False:
            out["winner"] = c
            out["verdict"] = "embed_clean"
            out["verdict_reason"] = "ashby_refs+no_captcha+differentiated"
            return out

    # Fallback verdicts
    captcha_winners = [c for c in out["candidates"] if not c.get("reject") and c.get("ashby_refs") and c.get("captcha")]
    if captcha_winners:
        out["winner"] = captcha_winners[0]
        out["verdict"] = "embed_captcha_walled"
        out["verdict_reason"] = "ashby_refs+captcha=" + ",".join(captcha_winners[0]["captcha"])
        return out

    # Candidates that returned 200 but no ashby refs
    plain_200 = [c for c in out["candidates"] if not c.get("reject") and c.get("status") == 200]
    if plain_200:
        out["verdict"] = "no_embed_plain_200"
        out["verdict_reason"] = "page_exists_but_no_ashby_refs"
    return out

def main():
    results = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(probe_tenant, t, jid, title): t for t, jid, title in TENANTS_WITH_SAMPLES}
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception as e:
                print("worker exc:", e)
                continue
            results.append(r)
            w = r.get("winner") or {}
            print(f"{r['tenant']:18s} {r['verdict']:25s} {(w.get('url') or '-')[:80]}")
    results.sort(key=lambda x: x["tenant"])
    out_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ashby-sweep2.json"
    with open(out_path, "w") as f:
        json.dump({"generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "tenants": results,
                   "summary": {
                       "total": len(results),
                       "embed_clean": sum(1 for r in results if r["verdict"] == "embed_clean"),
                       "embed_captcha_walled": sum(1 for r in results if r["verdict"] == "embed_captcha_walled"),
                       "no_embed": sum(1 for r in results if r["verdict"].startswith("no_embed")),
                       "gql_failed": sum(1 for r in results if r["verdict_reason"] == "gql_failed"),
                   }}, f, indent=2)
    print(f"\nWrote {out_path}")
    print(f"Summary: clean={sum(1 for r in results if r['verdict']=='embed_clean')} walled={sum(1 for r in results if r['verdict']=='embed_captcha_walled')} no_embed={sum(1 for r in results if r['verdict'].startswith('no_embed'))}")

if __name__ == "__main__":
    main()
