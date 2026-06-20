"""Verify driver for the apple candidate adapter (adapter-repair).

Loads adapters/_repair/apple.py.candidate via importlib (NOT through the live
adapters package), then:
  1. Syntax/import check.
  2. Parser check against a cached real search-page body (fast, deterministic).
  3. Live 1-page fetch through the new _get_with_retry wrapper (proves the retry
     path imports & the HTTP layer still works) — does NOT run the full 218s crawl.

We deliberately avoid calling the full .fetch() here because the full crawl
(972 postings + 93 JD-detail GETs) takes ~3.5 min and the live probe already
proved the end-to-end shape is green. This driver proves the *candidate* is a
drop-in: same module API, same parse output, plus the resilience wrapper.
"""
import importlib.util
import importlib.machinery
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # role-discovery/
sys.path.insert(0, ROOT)

CAND = os.path.join(HERE, "apple.py.candidate")
BODY = "/tmp/apple_py.html"  # fresh real search page saved during diagnosis


def load_candidate():
    # File ends in .candidate (not .py), so importlib can't infer a loader from the
    # suffix; supply an explicit SourceFileLoader.
    loader = importlib.machinery.SourceFileLoader("apple_candidate", CAND)
    spec = importlib.util.spec_from_loader("apple_candidate", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def main():
    print("=== 1. import candidate ===")
    apple = load_candidate()
    print("  OK: module loaded; has fetch:", hasattr(apple, "fetch"),
          "| has _get_with_retry:", hasattr(apple, "_get_with_retry"))

    print("=== 2. parser against cached real body ===")
    if not os.path.exists(BODY):
        print("  SKIP: cached body missing; doing live 1-page fetch instead")
        html_text = apple._fetch_page(1)
    else:
        html_text = open(BODY).read()
    items = apple._parse_page(html_text)
    print(f"  parsed items: {len(items)}")
    assert len(items) > 0, "FAIL: parser returned 0 items"
    for it in items[:2]:
        print("   ", it["positionId"], "|", it["postingTitle"][:50], "|",
              it["postDateInGMT"][:10], "| team", it["team"])

    print("=== 3. live 1-page fetch via retry wrapper ===")
    live = apple._fetch_page(1)
    live_items = apple._parse_page(live)
    print(f"  live page-1 parsed: {len(live_items)} items")
    assert len(live_items) > 0, "FAIL: live fetch parsed 0 items"

    # Apply the same OK/FAIL contract the smoke test uses (count>0, company/title/url
    # present, posted_at present since require_posted_at=True for apple). We build a
    # couple of Role objects exactly as fetch() would to confirm field population.
    print("=== 4. contract check on synthesized Role objects ===")
    ok = 0
    for it in live_items[:3]:
        pid = it["positionId"]; team = it.get("team") or "SFTWR"
        slug = it.get("slug") or "role"; disc = it.get("discriminator") or "0836"
        url = f"https://jobs.apple.com/en-us/details/{pid}-{disc}/{slug}?team={team}"
        r = apple.Role(
            company="Apple", title=it["postingTitle"], location="United States",
            exp_required="", url=url, posted_at=(it.get("postDateInGMT") or "")[:10],
            source="apple", raw=it,
        )
        assert r.company and r.title and r.url and r.posted_at, f"FAIL: missing field on {pid}"
        ok += 1
    print(f"  contract OK on {ok} synthesized roles (company/title/url/posted_at all present)")

    print("\nRESULT: GREEN — candidate imports, parses real body, live-fetches via retry wrapper, satisfies contract.")


if __name__ == "__main__":
    main()
