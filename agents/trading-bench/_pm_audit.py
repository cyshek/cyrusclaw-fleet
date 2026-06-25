import sqlite3
import json
import time
import urllib.request

GAMMA = "https://gamma-api.polymarket.com/markets/"

def fetch(mid):
    req = urllib.request.Request(GAMMA + str(mid), headers={"User-Agent": "trading-bench-research research@example.com"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    except Exception as ex:
        return {"_error": str(ex)[:120]}

c = sqlite3.connect("polymarket_track.db")
c.row_factory = sqlite3.Row
rows = list(c.execute("select id, market_id, side, our_prior, implied_prob, stake_usd, substr(question,1,55) q from paper_bets where status='open' order by id"))

print("id  | mkt          | closed | outPrices        | side prior  -> RESOLVED? P&L est   | question")
print("-" * 130)
results = []
for r in rows:
    m = fetch(r["market_id"])
    time.sleep(0.4)
    if "_error" in m:
        print(f'{r["id"]:>3} | {r["market_id"]:>12} | FETCH_ERR {m["_error"]}')
        results.append((r["id"], "fetch_err", None, None))
        continue
    closed = m.get("closed", False)
    op = m.get("outcomePrices")
    end = str(m.get("endDate", ""))[:10]
    # outcomePrices is a JSON string like '["1","0"]'
    op_parsed = None
    if op:
        try:
            op_parsed = json.loads(op) if isinstance(op, str) else op
        except Exception:
            op_parsed = op
    # determine YES outcome price
    yes_px = None
    if op_parsed and len(op_parsed) >= 1:
        try:
            yes_px = float(op_parsed[0])
        except Exception:
            yes_px = None
    # P&L: bet $stake on side at entry implied_prob. If resolved, win pays stake/entry_prob (binary), lose = -stake.
    pnl = None
    outcome = None
    if closed and yes_px is not None:
        if yes_px >= 0.99:
            outcome = "YES"
        elif yes_px <= 0.01:
            outcome = "NO"
        else:
            outcome = f"MID({yes_px:.2f})"
        side_is_yes = r["side"].strip().lower() in ("yes",)
        if outcome in ("YES", "NO"):
            won = (outcome == "YES" and side_is_yes) or (outcome == "NO" and not side_is_yes)
            entry = r["implied_prob"] if r["implied_prob"] and r["implied_prob"] > 0 else None
            if entry is not None and entry > 0 and entry < 1:
                # paper convention: pay = stake/entry on win (binary fair), -stake on loss
                pnl = (r["stake_usd"] / entry - r["stake_usd"]) if won else -r["stake_usd"]
            else:
                pnl = None
    flag = "RESOLVED" if closed else "open"
    pnls = f"{pnl:+.2f}" if pnl is not None else " n/a "
    print(f'{r["id"]:>3} | {r["market_id"]:>12} | {str(closed):>6} | {str(op_parsed):>16} | {r["side"]:>3} {r["our_prior"]:.2f} -> {flag:>8} {pnls:>9} | end={end} {r["q"]}')
    results.append((r["id"], flag, outcome, pnl))

c.close()
print()
res_closed = [x for x in results if x[1] == "RESOLVED"]
print(f"RESOLVED-but-still-open-in-DB: {len(res_closed)}  ->", [x[0] for x in res_closed])
tot = sum(x[3] for x in res_closed if x[3] is not None)
print(f"net P&L on those resolved: {tot:+.2f}")
