#!/usr/bin/env python3
"""Apply ERC capital weights to the 8 live strategies' params.json.

Respects each strategy's DISTINCT notional knob:
  - 6 event strategies: 'notional_usd'
  - tqqq_cot_combo: 'notional' (vol-target deployable base; weight<=1 applied on top)
  - allocator_blend: 'max_notional_usd' AND 'notional_usd' (both = the blend cap)

Backs up every file to memory/params_backup_<ts>/ first. Validates JSON round-trip.
Pass --execute to write; default dry-run prints the diff.
"""
import json, sys, shutil, time
from pathlib import Path

WS = Path(__file__).resolve().parent
E = json.load(open(WS / "reports/_erc_weights.json"))
cap = E["capital_usd_v2_tradeable"]   # {strategy: dollars} -- tradeable (share-floored) ERC

# which knob(s) each strategy uses
KNOBS = {
    "breakout_xlk__mut_c382b1": ["notional_usd"],
    "sma_crossover_qqq_regime": ["notional_usd"],
    "sma_crossover_qqq_rth": ["notional_usd"],
    "rsi_oversold_spy": ["notional_usd"],
    "volume_breakout_qqq": ["notional_usd"],
    "macd_momentum_iwm": ["notional_usd"],
    "tqqq_cot_combo": ["notional"],
    "allocator_blend": ["max_notional_usd", "notional_usd"],
}

execute = "--execute" in sys.argv
ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
bkdir = WS / f"memory/params_backup_{ts}"

changes = []
for strat, knobs in KNOBS.items():
    p = WS / "strategies" / strat / "params.json"
    d = json.loads(p.read_text())
    new_val = round(cap[strat], 2)
    rowchg = {"strategy": strat, "file": str(p), "knobs": {}}
    for k in knobs:
        old = d.get(k)
        rowchg["knobs"][k] = {"old": old, "new": new_val}
        d[k] = new_val
    changes.append((strat, p, d, rowchg))

print(f"{'strategy':30s} {'knob':18s} {'old':>10s} {'new$':>10s}")
for strat, p, d, rc in changes:
    for k, v in rc["knobs"].items():
        print(f"{strat:30s} {k:18s} {str(v['old']):>10s} {v['new']:>10.2f}")

if not execute:
    print("\nDRY-RUN — no files written. Re-run with --execute to apply.")
    sys.exit(0)

# backup
bkdir.mkdir(parents=True, exist_ok=True)
for strat, p, d, rc in changes:
    shutil.copy2(p, bkdir / f"{strat}__params.json")
# write (atomic-ish: write temp then replace)
for strat, p, d, rc in changes:
    txt = json.dumps(d, indent=2) + "\n"
    # validate round-trip
    json.loads(txt)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(txt)
    tmp.replace(p)
print(f"\nWROTE {len(changes)} params.json files. Backup: {bkdir}")
print("ERC capital applied. Total budget: $%.2f" % sum(cap.values()))
