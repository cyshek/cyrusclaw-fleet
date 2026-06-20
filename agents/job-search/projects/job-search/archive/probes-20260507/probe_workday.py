"""Quick probe: for every workday entry in companies.yaml, hit the API once
and report success/failure with HTTP status. No filtering — just connectivity."""
from __future__ import annotations
import yaml, sys, os
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import http_post_json


def probe(entry):
    name = entry["name"]
    if entry.get("skip"):
        return (name, "SKIP", entry.get("reason", ""))
    if entry.get("adapter") != "workday":
        return None
    host = entry["host"]
    tenant = entry["tenant"]
    site = entry["site"]
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    try:
        r = http_post_json(
            url,
            {"appliedFacets": {}, "limit": 5, "offset": 0, "searchText": "manager"},
            headers={"X-Calypso-PageBlocked": "false"},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            total = data.get("total", 0)
            return (name, f"OK ({total} jobs)", url)
        else:
            return (name, f"HTTP {r.status_code}", url)
    except Exception as e:
        return (name, f"ERR {type(e).__name__}: {str(e)[:120]}", url)


def main():
    with open("companies.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    entries = cfg["companies"]

    results = []
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = [ex.submit(probe, e) for e in entries]
        for fut in as_completed(futs):
            r = fut.result()
            if r is not None:
                results.append(r)

    results.sort(key=lambda x: (0 if x[1].startswith("OK") else 1, x[0]))
    print(f"\n{'Company':<25} {'Status':<35} URL")
    print("=" * 120)
    for name, status, url in results:
        print(f"{name:<25} {status:<35} {url}")
    print(f"\nTotal: {len(results)} workday entries")
    ok = sum(1 for _, s, _ in results if s.startswith("OK"))
    print(f"OK: {ok}    Broken: {len(results) - ok}")


if __name__ == "__main__":
    main()
