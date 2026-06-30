import sqlite3, os, json
from collections import defaultdict

# Find the tournament/live trades DB
DBS = ["tournament.db", "runner/tournament.db", "data/tournament.db"]
db = next((d for d in DBS if os.path.exists(d)), None)
print("trades DB:", db)
if not db:
    raise SystemExit(0)

c = sqlite3.connect(db)
cols = [r[1] for r in c.execute("PRAGMA table_info(trades)").fetchall()]
print("trades cols:", cols)

# Synthetic-row guard per MEMORY.md standing rule
SYNTH_STRATS = {"any", "backstop_test", "bp2"}
def is_synth(strat, oid):
    if strat in SYNTH_STRATS:
        return True
    if oid is None:
        return True
    if oid in ("order-1", "ord-seed"):
        return True
    if len(str(oid)) < 20:
        return True
    return False

LIVE = ["sma_crossover_qqq_regime","sma_crossover_qqq_rth","volume_breakout_qqq",
        "macd_momentum_iwm","tqqq_cot_combo","allocator_blend"]

# Detect column names
strat_col = "strategy" if "strategy" in cols else ("strategy_name" if "strategy_name" in cols else None)
oid_col = "alpaca_order_id" if "alpaca_order_id" in cols else ("order_id" if "order_id" in cols else None)
side_col = "side" if "side" in cols else None
ts_col = next((x for x in ("created_at","ts","timestamp","filled_at") if x in cols), None)
status_col = next((x for x in ("status","order_status") if x in cols), None)
print(f"using strat={strat_col} oid={oid_col} side={side_col} ts={ts_col} status={status_col}")

rows = c.execute(f"SELECT * FROM trades").fetchall()
idx = {name:i for i,name in enumerate(cols)}

per = defaultdict(lambda: {"n":0,"buys":0,"sells":0,"first":None,"last":None,"statuses":defaultdict(int),"synth":0})
for r in rows:
    strat = r[idx[strat_col]] if strat_col else None
    oid = r[idx[oid_col]] if oid_col else None
    if is_synth(strat, oid):
        per[strat]["synth"] += 1
        continue
    d = per[strat]
    d["n"] += 1
    if side_col:
        s = (r[idx[side_col]] or "").lower()
        if s == "buy": d["buys"] += 1
        elif s in ("sell","close","trim"): d["sells"] += 1
    if ts_col:
        t = r[idx[ts_col]]
        if t:
            if d["first"] is None or t < d["first"]: d["first"] = t
            if d["last"] is None or t > d["last"]: d["last"] = t
    if status_col:
        d["statuses"][r[idx[status_col]]] += 1

print("\n=== LIVE TRADE REALITY (synthetic rows excluded) ===")
for s in LIVE:
    d = per.get(s)
    if not d or d["n"]==0:
        print(f"  {s:30s}: NO REAL TRADES YET")
        continue
    st = dict(d["statuses"])
    print(f"  {s:30s}: trades={d['n']:3d} buys={d['buys']:3d} sells={d['sells']:3d} | first={d['first']} last={d['last']}")
    if st:
        print(f"    {'':30s}  statuses={st}")

# Flag any non-terminal orders on live strategies
print("\n=== NON-TERMINAL ORDER CHECK (live strategies) ===")
TERMINAL = {"filled","canceled","cancelled","expired","rejected","done_for_day","replaced"}
any_stuck = False
for s in LIVE:
    d = per.get(s)
    if not d: continue
    for stat, n in d["statuses"].items():
        if stat and str(stat).lower() not in TERMINAL:
            print(f"  ⚠️ {s}: {n} order(s) in non-terminal status '{stat}'")
            any_stuck = True
if not any_stuck:
    print("  ✓ no stuck/non-terminal orders on any live strategy")
c.close()
