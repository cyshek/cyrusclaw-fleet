"""LIVE smoke (network) — not part of the unit suite. Proves the real Wikipedia
fetch + PIT reconstruction produces sane membership counts across history."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runner import sp500_pit_membership as pit

tbl = pit.load_live_membership_table()
cur = tbl["current"]
ch = tbl["changes"]
print(f"current constituents scraped: {len(cur)}")
print(f"dated change rows parsed:     {len(ch)}")
if ch:
    print(f"change-log span: {ch[0]['date']} -> {ch[-1]['date']}")

# Spot-check as-of counts at a few historical dates. A healthy S&P 500
# reconstruction should stay near ~500 names at every point (it's a 500-member
# index by construction); large deviations would signal a parse drift.
for y in (2010, 2015, 2018, 2020, 2022, 2024):
    s = pit.members_asof(tbl, dt.date(y, 6, 30))
    print(f"  members_asof {y}-06-30: {len(s)}")

today = dt.date.today()
assert pit.members_asof(tbl, today) == cur, "today must equal current snapshot"
print("OK: today == current snapshot")

# sanity: a well-known long-tenured name present in 2015
probe = "AAPL"
in2015 = probe in pit.members_asof(tbl, dt.date(2015, 6, 30))
print(f"AAPL in index 2015-06-30: {in2015}")
