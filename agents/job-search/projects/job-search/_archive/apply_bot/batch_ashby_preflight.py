"""Preflight: simulate what batch_ashby.py would do, no actual submits."""
import time
from datetime import datetime, timedelta
import batch_ashby as ba

state = ba.url_status_index()
status = state["urls"]
tenant_recent_submits = state["tenant_recent_submits"]
discovered_caps = state["tenant_caps"]
tenant_spam_flagged = state["tenant_spam_flagged"]

caps = ba.load_tenant_caps()
for tenant, kind in discovered_caps.items():
    if tenant not in caps:
        caps[tenant] = {"kind": kind,
                        "first_seen": datetime.utcnow().isoformat() + "Z"}

# Merge spam_rejected entries from caps file into tenant_spam_flagged
for tenant, info in caps.items():
    if info.get("kind") == "spam_rejected":
        ts_str = info.get("first_seen", "")
        try:
            dt = datetime.fromisoformat(ts_str.rstrip("Z"))
            ts = dt.timestamp()
        except Exception:
            ts = time.time()
        prev = tenant_spam_flagged.get(tenant, 0)
        if ts > prev:
            tenant_spam_flagged[tenant] = ts

submitted_count = sum(1 for v in status.values() if v == "submitted")
rejected_count = sum(1 for v in status.values() if v == "rejected")
attempted_count = sum(1 for v in status.values() if v == "attempted")
print(f"Recent run history: submitted={submitted_count}, "
      f"rejected={rejected_count}, attempted={attempted_count}")
print(f"tenant_caps.json: {sorted(caps.keys())}")
print(f"Recent successful submits per tenant (within 7d):")
for t, ts in tenant_recent_submits.items():
    age_h = (time.time() - ts) / 3600
    print(f"  {t}: {age_h:.1f}h ago")
print(f"Tenants with spam-flag in last {ba.SPAM_LOCKOUT_HOURS}h:")
for t, ts in tenant_spam_flagged.items():
    age_h = (time.time() - ts) / 3600
    print(f"  {t}: {age_h:.1f}h ago")

print("\n=== PREFLIGHT DECISIONS ===")
cooldown_cutoff = time.time() - ba.TENANT_COOLDOWN_HOURS * 3600
spam_cutoff = time.time() - ba.SPAM_LOCKOUT_HOURS * 3600
submits_this_run = {}
proceed = 0
for i, (co, role, url) in enumerate(ba.ASHBY_QUEUE, 1):
    tenant = ba.tenant_of(url)
    decision = None
    # cap?
    if tenant in caps and caps[tenant].get("kind") == "cap_exceeded":
        cap_first_seen = caps[tenant].get("first_seen", "")
        try:
            first_dt = datetime.fromisoformat(cap_first_seen.rstrip("Z"))
            lockout_end = first_dt + timedelta(days=ba.CAP_LOCKOUT_DAYS)
            if datetime.utcnow() < lockout_end:
                days_left = (lockout_end - datetime.utcnow()).days
                decision = f"SKIP cap_exceeded (~{days_left}d left)"
        except Exception:
            decision = "SKIP cap_exceeded (unparseable ts)"
    if decision is None:
        last = max(tenant_recent_submits.get(tenant, 0),
                   submits_this_run.get(tenant, 0))
        if last > cooldown_cutoff:
            age_h = (time.time() - last) / 3600
            decision = f"SKIP tenant-cooldown ({age_h:.1f}h since last submit)"
    if decision is None:
        spam_ts = tenant_spam_flagged.get(tenant, 0)
        if spam_ts > spam_cutoff:
            age_h = (time.time() - spam_ts) / 3600
            decision = f"SKIP spam-cooldown ({age_h:.1f}h since flag)"
    if decision is None:
        prior = status.get(url)
        if prior == "submitted":
            decision = "SKIP already-submitted"
        elif prior in ("rejected", "attempted"):
            decision = f"SKIP prior={prior}"
    if decision is None:
        decision = "PROCEED"
        proceed += 1
    print(f"  [{i:>2}] {tenant:<10} {co:<10} {role[:50]:<50} -> {decision}")

print(f"\nWould attempt {proceed} of {len(ba.ASHBY_QUEUE)} roles.")
