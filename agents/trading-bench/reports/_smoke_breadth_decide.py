import importlib, math, traceback
import sys
sys.path.insert(0, "/home/azureuser/.openclaw/agents/trading-bench/workspace")
S = importlib.import_module("strategies.leveraged_long_trend_paper.strategy")

n = 260
qqq = [100.0 * (1.0 + 0.0004) ** i for i in range(n)]
tqqq_closes = [50.0 * (1.0 + 0.0012) ** i for i in range(n)]
bars = [{"t": f"2026-01-{(i%28)+1:02d}", "o": c, "h": c, "l": c, "c": c, "v": 1000} for i, c in enumerate(tqqq_closes)]


def run(label, ms, check=None):
    print(label)
    try:
        a = S.decide(ms, {}, None)
        print(f"  action={a.action!r}")
        print(f"  reason={a.reason!r}")
        if check:
            check(a)
        print("  -> OK")
    except Exception as e:
        traceback.print_exc()
        print(f"  THREW: {type(e).__name__}: {e}")
    print()


run("=== CASE 1: plumbing gap (no underlying closes) -> fail-safe, no throw ===",
    {"last_price": tqqq_closes[-1], "bars": bars,
     "regime": {"spy_closes": qqq[-100:], "spy_last": qqq[-1]}})

run("=== CASE 2: WITH QQQ closes (uptrend) -> breadth g=1.0, sizes a BUY ===",
    {"last_price": tqqq_closes[-1], "bars": bars,
     "underlying": {"symbol": "QQQ", "closes": qqq}},
    check=lambda a: (
        None if "breadth{30/90/180}" in a.reason
        else (_ for _ in ()).throw(AssertionError("breadth descriptor missing"))))

qqq_down = [200.0 * (1.0 - 0.0006) ** i for i in range(n)]
run("=== CASE 3: QQQ DOWNTREND -> g=0 -> flat/hold ===",
    {"last_price": tqqq_closes[-1], "bars": bars,
     "underlying": {"symbol": "QQQ", "closes": qqq_down}},
    check=lambda a: (
        None if a.action in ("hold", "close")
        else (_ for _ in ()).throw(AssertionError("downtrend should be flat"))))

qqq_mixed = [100.0 + 30.0 * math.sin(i / 40.0) + 0.01 * i for i in range(n)]
run("=== CASE 4: PARTIAL breadth -> 0<g<1 graded path executes ===",
    {"last_price": tqqq_closes[-1], "bars": bars,
     "underlying": {"symbol": "QQQ", "closes": qqq_mixed}})

print("ALL RUNTIME CASES EXECUTED.")
