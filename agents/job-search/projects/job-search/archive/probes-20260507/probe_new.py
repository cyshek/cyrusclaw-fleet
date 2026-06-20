"""Probe new high-comp companies for working ATS slugs.

Tests Greenhouse + Ashby + Lever for a batch of candidate slugs.
Prints results for direct inclusion into companies.yaml.
"""
import requests
from concurrent.futures import ThreadPoolExecutor

CANDIDATES = [
    # (name, ats, slug)
    # ---- Big tech / public ----
    ("Palantir", "lever", "palantir"),
    ("Palantir", "greenhouse", "palantir"),
    ("Shopify", "greenhouse", "shopify"),
    ("Shopify", "lever", "shopify"),
    ("HubSpot", "greenhouse", "hubspot"),
    ("Zendesk", "greenhouse", "zendesk"),
    ("Smartsheet", "greenhouse", "smartsheet"),
    ("Roku", "greenhouse", "roku"),
    ("The Trade Desk", "greenhouse", "thetradedesk"),
    ("The Trade Desk", "greenhouse", "thetradedeskinc"),
    # ---- Security unicorns ----
    ("Crowdstrike", "greenhouse", "crowdstrike"),
    ("Palo Alto Networks", "greenhouse", "paloaltonetworks"),
    ("Wiz", "ashby", "wiz"),
    ("Wiz", "greenhouse", "wiz"),
    ("SentinelOne", "greenhouse", "sentinelone"),
    ("Snyk", "greenhouse", "snyk"),
    ("Sentry", "greenhouse", "sentry"),
    ("Fortinet", "greenhouse", "fortinet"),
    ("Tanium", "greenhouse", "tanium"),
    # ---- Data/Infra unicorns ----
    ("Cockroach Labs", "greenhouse", "cockroachlabs"),
    ("dbt Labs", "ashby", "dbtlabs"),
    ("dbt Labs", "greenhouse", "dbtlabs"),
    ("Fivetran", "greenhouse", "fivetran"),
    ("LaunchDarkly", "greenhouse", "launchdarkly"),
    ("Amplitude", "greenhouse", "amplitude"),
    ("Mixpanel", "greenhouse", "mixpanel"),
    ("Algolia", "greenhouse", "algolia"),
    ("Astronomer", "greenhouse", "astronomer"),
    ("Hex", "ashby", "hex"),
    ("Hex", "greenhouse", "hex"),
    # ---- Gaming ----
    ("Unity", "greenhouse", "unity"),
    ("Unity", "greenhouse", "unitytechnologies"),
    ("Niantic", "greenhouse", "niantic"),
    # ---- Quant/HFT (very high comp) ----
    ("Two Sigma", "greenhouse", "twosigma"),
    ("Two Sigma", "greenhouse", "twosigmainvestments"),
    ("Citadel", "greenhouse", "citadel"),
    ("Citadel Securities", "greenhouse", "citadelsecurities"),
    ("Jane Street", "greenhouse", "janestreet"),
    ("Hudson River Trading", "greenhouse", "hudsonrivertrading"),
    ("Hudson River Trading", "greenhouse", "hrt"),
    ("Jump Trading", "greenhouse", "jumptrading"),
    ("DRW", "greenhouse", "drw"),
    ("Optiver", "greenhouse", "optiver"),
    ("Akuna Capital", "greenhouse", "akunacapital"),
    ("IMC Trading", "greenhouse", "imc"),
    # ---- Crypto/Fintech ----
    ("Klarna", "greenhouse", "klarna"),
    ("Gemini", "greenhouse", "gemini"),
    ("Kraken", "greenhouse", "kraken"),
    ("Circle", "greenhouse", "circle"),
    ("Chainalysis", "greenhouse", "chainalysis"),
    # ---- Networking/CDN ----
    ("Akamai", "greenhouse", "akamai"),
    ("Arista Networks", "greenhouse", "aristanetworks"),
    # ---- AI/ML startups ----
    ("Character AI", "greenhouse", "characterai"),
    ("Character AI", "ashby", "characterai"),
    ("Adept", "ashby", "adept"),
    ("Runway", "greenhouse", "runwayml"),
    ("Runway", "ashby", "runway"),
    ("ElevenLabs", "ashby", "elevenlabs"),
    ("Glean", "greenhouse", "glean"),
    ("Glean", "ashby", "glean"),
    ("Harvey", "ashby", "harvey"),
    ("Sierra", "ashby", "sierra"),
    ("Decagon", "ashby", "decagon"),
    ("Imbue", "ashby", "imbue"),
    ("Pika", "ashby", "pika"),
    # ---- Devtools ----
    ("CircleCI", "greenhouse", "circleci"),
    ("Sourcegraph", "ashby", "sourcegraph"),  # already skipped, retry
    ("Replit", "ashby", "replit"),
    ("Replit", "greenhouse", "replit"),
    ("Vercel", "greenhouse", "vercel"),  # already in
    ("Render", "ashby", "render"),
    ("Supabase", "ashby", "supabase"),
    ("PlanetScale", "ashby", "planetscale"),
    ("PlanetScale", "greenhouse", "planetscale"),
    ("Neon", "ashby", "neon"),
    # ---- SaaS misc ----
    ("Monday.com", "greenhouse", "mondaycom"),
    ("ClickUp", "greenhouse", "clickup"),
    ("Pendo", "greenhouse", "pendo"),
    ("Fullstory", "greenhouse", "fullstory"),
    ("Heap", "greenhouse", "heapanalytics"),
    ("Segment", "greenhouse", "segment"),
    ("Segment", "greenhouse", "twiliosegment"),
    # ---- Logistics/marketplaces ----
    ("Faire", "greenhouse", "faire"),
    ("Flexport", "greenhouse", "flexport"),
    ("GoodRx", "greenhouse", "goodrx"),
    ("Carvana", "greenhouse", "carvana"),
    # ---- Newer hot AI startups ----
    ("xAI", "ashby", "xai"),
    ("xAI", "greenhouse", "xai"),
    ("Anthropic", "greenhouse", "anthropic"),  # already in
    ("Inflection", "ashby", "inflection"),
    ("Magic Dev", "ashby", "magic"),
    ("World Labs", "ashby", "worldlabs"),
    ("Suno", "ashby", "suno"),
    ("Lovable", "ashby", "lovable"),
    ("Bolt", "ashby", "bolt"),
    ("Synthesia", "greenhouse", "synthesia"),
    ("Pika Labs", "ashby", "pikalabs"),
]


def probe(entry):
    name, ats, slug = entry
    try:
        if ats == "greenhouse":
            url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                jobs = r.json().get("jobs", [])
                return (name, ats, slug, "OK", len(jobs))
            return (name, ats, slug, f"HTTP {r.status_code}", 0)
        elif ats == "ashby":
            url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                jobs = r.json().get("jobs", [])
                return (name, ats, slug, "OK", len(jobs))
            return (name, ats, slug, f"HTTP {r.status_code}", 0)
        elif ats == "lever":
            url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                jobs = r.json()
                return (name, ats, slug, "OK", len(jobs) if isinstance(jobs, list) else 0)
            return (name, ats, slug, f"HTTP {r.status_code}", 0)
    except Exception as e:
        return (name, ats, slug, f"ERR {type(e).__name__}", 0)


def main():
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(probe, CANDIDATES))

    print("\n=== WORKING (use these) ===")
    seen_names = set()
    for r in results:
        name, ats, slug, status, n = r
        if status == "OK" and n > 0:
            mark = "*" if name not in seen_names else " "
            seen_names.add(name)
            print(f"{mark} {name:30s} {ats:12s} {slug:25s} {n} jobs")

    print("\n=== NOT WORKING ===")
    for r in results:
        name, ats, slug, status, n = r
        if status != "OK" or n == 0:
            print(f"  {name:30s} {ats:12s} {slug:25s} {status}")


if __name__ == "__main__":
    main()
