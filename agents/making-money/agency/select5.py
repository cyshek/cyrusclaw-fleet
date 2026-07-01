#!/usr/bin/env python3
"""Select the final batch-5 set (target 25-30) from the 72 clean emailable drafts,
maximizing PERSONALIZATION while keeping city + vertical spread.

Priority tiers (highest first):
  T1  named greeting AND personal inbox          (best — real human + real inbox)
  T2  named greeting OR personal inbox OR low-review hook
  T3  strong hook (slow-SLA) on a primary metro
  T4  plain form-no-instant on a primary metro    (top-up only)

Primary metros (fresh, strongest harvest): Albuquerque NM, Colorado Springs CO, El Paso TX.
Always-keep: the Reno recovered lead (angela@paschallplus.com). Fresno/Greenville rows are
included only when they carry a named/personal signal (they add personalization, not filler).
Caps: <= 30 total; <= ~10 per metro; <= ~10 per vertical to avoid lopsidedness.
Reads batch5_payload.json (all 72) -> rewrites batch5_payload.json (selected subset).
"""
import json, re
from collections import Counter

NL = chr(10)
ALL = json.load(open("batch5_payload_full.json"))
PRIMARY = {"Albuquerque, NM", "Colorado Springs, CO", "El Paso, TX"}
TARGET = 30
PER_METRO_CAP = 10
PER_VERT_CAP = 11

def named(r):
    m = re.match(r"Hi (.+),", r["body"].split(NL)[0])
    return bool(m) and m.group(1) != "there"

def personal(r):
    return (r.get("email_source") or "").startswith("site-personal")

def lowrev(r):
    return bool(re.search(r"^\d+ review", r["subject"]))

def slowsla(r):
    return "quick one about" in r["subject"] and not lowrev(r)

def recovered(r):
    return "recovered-lead" in (r.get("email_source") or "")

def tier(r):
    if named(r) and personal(r):
        return 1
    if named(r) or personal(r) or lowrev(r):
        return 2
    if slowsla(r):
        return 3
    return 4

def score(r):
    # lower = better; sort key
    s = tier(r) * 100
    if recovered(r):
        s = 0  # force-keep recovered lead first
    # within tier, prefer named, then personal, then low-review, then primary metro
    s -= 30 if named(r) else 0
    s -= 20 if personal(r) else 0
    s -= 15 if lowrev(r) else 0
    s -= 5 if r["city_state"] in PRIMARY else 0
    return s

# eligibility: primary-metro rows always eligible; non-primary only if named/personal/recovered
def eligible(r):
    if recovered(r):
        return True
    if r["city_state"] in PRIMARY:
        return True
    return named(r) or personal(r)

pool = [r for r in ALL if eligible(r)]
pool.sort(key=score)

selected = []
metro_ct = Counter()
vert_ct = Counter()
for r in pool:
    if len(selected) >= TARGET:
        break
    m = r["city_state"]; v = r["vertical"]
    if not recovered(r):
        if metro_ct[m] >= PER_METRO_CAP:
            continue
        if vert_ct[v] >= PER_VERT_CAP:
            continue
    selected.append(r)
    metro_ct[m] += 1
    vert_ct[v] += 1

json.dump(selected, open("batch5_payload.json", "w"), ensure_ascii=False, indent=2)

print("SELECTED:", len(selected), "of", len(ALL), "emailable (pool eligible:", len(pool), ")")
print("named:", sum(named(r) for r in selected),
      "| personal:", sum(personal(r) for r in selected),
      "| low-review:", sum(lowrev(r) for r in selected))
print()
print("By metro:")
for k, v in sorted(metro_ct.items()):
    print("  %-24s %d" % (k, v))
print("By vertical:")
for k, v in sorted(vert_ct.items()):
    print("  %-24s %d" % (k, v))
print("By tier:", dict(Counter(tier(r) for r in selected)))
