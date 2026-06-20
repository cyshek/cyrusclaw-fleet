"""
Curated Ashby live-submit batch.
Submits to top-priority Ashby roles in --live mode with humanization.

Hard rules (learned from 2026-05-04 spam cascade + 2026-05-05 cap discovery):
  1. ONE submission per Ashby tenant per `TENANT_COOLDOWN_HOURS` window.
     Sierra rejected our 2nd application in 16 min with the spam banner.
  2. Skip any tenant that has hit the per-tenant application cap
     (e.g. OpenAI's "5 per 180 days"). Cap-exceeded tenants are recorded
     in `tenant_caps.json` and skipped for `CAP_LOCKOUT_DAYS` days.
  3. Skip any URL we've already touched in `dedupe_window_hours`.
"""
import subprocess
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timedelta

ASHBY_QUEUE = [
    # (company, role, url) — ordered to alternate tenants
    ("Decagon", "Technical Program Manager",
     "https://jobs.ashbyhq.com/decagon/d32da775-c5ea-420d-a07e-13412044c27b"),
    ("Harvey", "Innovation Product Manager",
     "https://jobs.ashbyhq.com/harvey/e5272fbe-4431-4841-bf00-b9f59812b82a"),
    ("OpenAI", "Deployed Product Manager, Codex",
     "https://jobs.ashbyhq.com/openai/60d1420a-8aa3-4d87-847e-e7b73d9d9a0c"),
    ("Sierra", "Product Manager, Agent Data Platform",
     "https://jobs.ashbyhq.com/sierra/422cb7bb-ab03-447b-808c-6d72f59bbd2f"),
    ("OpenAI", "Product Manager, API Infrastructure",
     "https://jobs.ashbyhq.com/openai/7ffa2a14-fa9c-46cb-a30a-1f7a35ae904a"),
    ("Sierra", "Product Manager, Agent SDK",
     "https://jobs.ashbyhq.com/sierra/10d2e2f1-6657-40c9-b6fb-6999c76df6cf"),
    ("Harvey", "Employee Experience Program Manager",
     "https://jobs.ashbyhq.com/harvey/da9f2961-fcfd-401f-a86a-9e548290b4a4"),
    ("OpenAI", "Technical Program Manager – Adversarial Model Research",
     "https://jobs.ashbyhq.com/openai/65913e57-80e0-4a1a-bbc3-265ae8a1a41b"),
    ("Sierra", "Product Manager, Agent Studio",
     "https://jobs.ashbyhq.com/sierra/5aaa2eeb-92bc-4b0a-901e-8e091eff819e"),
    ("OpenAI", "Technical Program Manager, Human Data",
     "https://jobs.ashbyhq.com/openai/71004494-9a55-4ed5-b458-2ff475f0d881"),
]

POLITE_DELAY_S = 90
SAME_TENANT_DELAY_S = 8 * 60  # 8min — was 90s, way too aggressive (got
# the entire 2026-05-04 batch flagged as spam by Ashby)
TENANT_COOLDOWN_HOURS = 24       # 1 successful Ashby submit per tenant per day
CAP_LOCKOUT_DAYS = 180           # OpenAI cap window — apply globally for any cap_exceeded tenant
SPAM_LOCKOUT_HOURS = 72          # spam-flagged tenant cooldown (per-tenant, not per-URL)
TENANT_CAPS_FILE = Path(__file__).parent / "tenant_caps.json"


def tenant_of(url: str) -> str:
    return url.split("ashbyhq.com/")[1].split("/")[0]


def load_tenant_caps() -> dict:
    """Load persistent tenant lockouts. Schema:
        {tenant: {"kind": "cap_exceeded"|"spam_rejected", "first_seen": iso}}
    """
    if not TENANT_CAPS_FILE.exists():
        return {}
    try:
        return json.loads(TENANT_CAPS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_tenant_caps(caps: dict) -> None:
    TENANT_CAPS_FILE.write_text(
        json.dumps(caps, indent=2, sort_keys=True), encoding="utf-8"
    )


def url_status_index(dedupe_window_hours: int = 168):
    """Return per-URL state plus per-tenant aggregate state.

    Returns:
        dict with keys:
          'urls':   {url: status}  status in {'submitted','rejected','attempted'}
          'tenant_recent_submits': {tenant: latest_submit_unix_ts}
          'tenant_caps':           {tenant: 'cap_exceeded' if seen}
    """
    runs = Path(__file__).parent / "runs"
    out_urls: dict[str, str] = {}
    tenant_recent_submits: dict[str, float] = {}
    tenant_caps: dict[str, str] = {}
    tenant_spam_flagged: dict[str, float] = {}
    if not runs.exists():
        return {"urls": out_urls,
                "tenant_recent_submits": tenant_recent_submits,
                "tenant_caps": tenant_caps,
                "tenant_spam_flagged": tenant_spam_flagged}
    cutoff = time.time() - dedupe_window_hours * 3600
    for r in sorted(runs.iterdir(), key=lambda p: p.stat().st_mtime):
        rj = r / "result.json"
        if not rj.exists():
            continue
        try:
            o = json.loads(rj.read_text(encoding="utf-8"))
        except Exception:
            continue
        url = o.get("url")
        if not url or "ashbyhq.com" not in url:
            continue
        tenant = tenant_of(url)
        mtime = r.stat().st_mtime
        notes = o.get("notes", []) or []
        # Detect cap_exceeded — applies regardless of dedupe window
        for n in notes:
            if isinstance(n, dict) and n.get("rejection_kind") == "cap_exceeded":
                tenant_caps[tenant] = "cap_exceeded"
            elif isinstance(n, str) and "cap_exceeded" in n.lower():
                tenant_caps[tenant] = "cap_exceeded"
        # Detect spam_rejected — track latest per tenant
        for n in notes:
            spam_hit = False
            if isinstance(n, dict) and n.get("rejection_kind") == "spam_rejected":
                spam_hit = True
            elif isinstance(n, str) and "flagged as possible spam" in n.lower():
                spam_hit = True
            if spam_hit:
                prev = tenant_spam_flagged.get(tenant, 0)
                if mtime > prev:
                    tenant_spam_flagged[tenant] = mtime
        # Track recent successful submits per tenant
        if o.get("submitted") and o.get("mode") == "live":
            prev = tenant_recent_submits.get(tenant, 0)
            if mtime > prev:
                tenant_recent_submits[tenant] = mtime
        # URL-level dedupe (within window)
        if mtime < cutoff:
            continue
        if o.get("dry_run") or o.get("mode") == "dry-run":
            continue
        if o.get("submitted"):
            out_urls[url] = "submitted"
            continue
        rejected = False
        for n in notes:
            s = str(n).lower()
            if "submission rejected" in s or "flagged as possible spam" in s:
                rejected = True
                break
        out_urls[url] = "rejected" if rejected else "attempted"
    return {"urls": out_urls,
            "tenant_recent_submits": tenant_recent_submits,
            "tenant_caps": tenant_caps,
            "tenant_spam_flagged": tenant_spam_flagged}


def main():
    headless = "--headless" in sys.argv
    state = url_status_index()
    status = state["urls"]
    tenant_recent_submits = state["tenant_recent_submits"]
    discovered_caps = state["tenant_caps"]
    tenant_spam_flagged = state["tenant_spam_flagged"]

    # Merge discovered caps into persistent tenant_caps.json
    caps = load_tenant_caps()
    for tenant, kind in discovered_caps.items():
        if tenant not in caps:
            caps[tenant] = {"kind": kind,
                            "first_seen": datetime.utcnow().isoformat() + "Z"}
    save_tenant_caps(caps)

    # Pull spam-flag entries from the persistent file too (manual seeds).
    # Convert to seconds-since-epoch and merge into tenant_spam_flagged so
    # the same skip-window applies.
    for tenant, info in caps.items():
        if info.get("kind") == "spam_rejected":
            ts_str = info.get("first_seen", "")
            try:
                dt = datetime.fromisoformat(ts_str.rstrip("Z"))
                ts = dt.timestamp()
            except Exception:
                ts = time.time()  # be conservative
            prev = tenant_spam_flagged.get(tenant, 0)
            if ts > prev:
                tenant_spam_flagged[tenant] = ts

    submitted_count = sum(1 for v in status.values() if v == "submitted")
    rejected_count = sum(1 for v in status.values() if v == "rejected")
    attempted_count = sum(1 for v in status.values() if v == "attempted")
    print(f"Recent run history: submitted={submitted_count}, "
          f"rejected={rejected_count}, attempted={attempted_count}")
    if caps:
        print(f"Tenants with cap_exceeded (180-day lockout): "
              f"{sorted(caps.keys())}")
    if tenant_spam_flagged:
        print(f"Tenants with spam-flag in last {SPAM_LOCKOUT_HOURS}h: "
              f"{sorted(tenant_spam_flagged.keys())}")
    if tenant_recent_submits:
        print(f"Tenants with successful submits in last 7d: "
              f"{sorted(tenant_recent_submits.keys())}")

    cooldown_cutoff = time.time() - TENANT_COOLDOWN_HOURS * 3600
    spam_cutoff = time.time() - SPAM_LOCKOUT_HOURS * 3600
    last_tenant = None
    results = []
    submits_this_run: dict[str, float] = {}

    for i, (co, role, url) in enumerate(ASHBY_QUEUE, 1):
        print(f"\n{'=' * 60}")
        print(f"[{i}/{len(ASHBY_QUEUE)}] {co} | {role}")
        print(f"  URL: {url}")

        tenant = tenant_of(url)

        # Cap-exceeded tenants: skip permanently (180d). Only entries with
        # kind=cap_exceeded apply this lockout; spam_rejected entries are
        # handled by the SPAM_LOCKOUT_HOURS check below.
        if tenant in caps and caps[tenant].get("kind") == "cap_exceeded":
            cap_first_seen = caps[tenant].get("first_seen", "")
            try:
                first_dt = datetime.fromisoformat(cap_first_seen.rstrip("Z"))
                lockout_end = first_dt + timedelta(days=CAP_LOCKOUT_DAYS)
                if datetime.utcnow() < lockout_end:
                    days_left = (lockout_end - datetime.utcnow()).days
                    print(f"  SKIP: tenant '{tenant}' is cap_exceeded "
                          f"(unlocks in ~{days_left}d)")
                    results.append((co, role, "skip-cap-exceeded"))
                    continue
            except Exception:
                print(f"  SKIP: tenant '{tenant}' cap_exceeded "
                      f"(unparseable timestamp; skipping conservatively)")
                results.append((co, role, "skip-cap-exceeded"))
                continue

        # One-per-tenant-per-day
        last_submit_ts = max(
            tenant_recent_submits.get(tenant, 0),
            submits_this_run.get(tenant, 0),
        )
        if last_submit_ts > cooldown_cutoff:
            hours_left = (TENANT_COOLDOWN_HOURS * 3600
                          - (time.time() - last_submit_ts)) / 3600
            print(f"  SKIP: tenant '{tenant}' had a successful submit "
                  f"{(time.time() - last_submit_ts) / 3600:.1f}h ago; "
                  f"cooldown {hours_left:.1f}h remaining")
            results.append((co, role, "skip-tenant-cooldown"))
            continue

        # Spam-flagged tenant cooldown (3 days) — protects sibling roles at
        # the same tenant. URL-level dedupe alone is insufficient because
        # different roles at the same tenant share the spam-flag.
        spam_ts = tenant_spam_flagged.get(tenant, 0)
        if spam_ts > spam_cutoff:
            hours_left = (SPAM_LOCKOUT_HOURS * 3600
                          - (time.time() - spam_ts)) / 3600
            print(f"  SKIP: tenant '{tenant}' was spam-flagged "
                  f"{(time.time() - spam_ts) / 3600:.1f}h ago; "
                  f"cooldown {hours_left:.1f}h remaining")
            results.append((co, role, "skip-spam-cooldown"))
            continue

        prior = status.get(url)
        if prior == "submitted":
            print("  SKIP: already submitted")
            results.append((co, role, "skip-already"))
            continue
        if prior in ("rejected", "attempted"):
            # Don't re-hit a URL that was already attempted recently — that
            # was the root cause of the 2026-05-04 spam flag cascade.
            print(f"  SKIP: prior outcome={prior} within dedupe window "
                  f"(remove run dir to retry)")
            results.append((co, role, f"skip-{prior}"))
            continue

        if last_tenant == tenant and i > 1:
            print(f"  Same tenant as last ({tenant}); waiting "
                  f"{SAME_TENANT_DELAY_S}s")
            time.sleep(SAME_TENANT_DELAY_S)
        elif i > 1:
            print(f"  Polite pause {POLITE_DELAY_S}s")
            time.sleep(POLITE_DELAY_S)

        cmd = [
            sys.executable, "apply.py",
            "--url", url,
            "--company", co,
            "--role", role,
            "--live",
        ]
        if headless:
            cmd.append("--headless")

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            print(res.stdout[-1500:])
            if res.stderr:
                print("STDERR:", res.stderr[-400:])
            tail = res.stdout
            if "Submitted:     True" in tail:
                results.append((co, role, "SUBMITTED"))
                submits_this_run[tenant] = time.time()
            elif "cap_exceeded" in tail.lower():
                results.append((co, role, "CAP_EXCEEDED"))
                # Record the cap immediately so subsequent iterations honor it
                caps[tenant] = {"kind": "cap_exceeded",
                                "first_seen": datetime.utcnow().isoformat() + "Z"}
                save_tenant_caps(caps)
            elif "spam" in tail.lower():
                results.append((co, role, "SPAM_REJECTED"))
                # Honor in-batch: blacklist this tenant for the rest of the run
                tenant_spam_flagged[tenant] = time.time()
            elif "submit clicked but no confirmation" in tail.lower():
                results.append((co, role, "no-confirm"))
            else:
                results.append((co, role, "unknown"))
        except subprocess.TimeoutExpired:
            results.append((co, role, "TIMEOUT"))
            print("  TIMEOUT")
        last_tenant = tenant

    print("\n" + "=" * 60)
    print("=== BATCH SUMMARY ===")
    for co, role, st in results:
        print(f"  [{st}] {co} | {role}")


if __name__ == "__main__":
    main()
