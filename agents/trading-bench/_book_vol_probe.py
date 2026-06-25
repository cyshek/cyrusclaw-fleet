import json
import math
import _tsmom_engine as E
import _xstrat_corr as X

LIVE8 = [
    "breakout_xlk__mut_c382b1", "sma_crossover_qqq_regime", "sma_crossover_qqq_rth",
    "rsi_oversold_spy", "volume_breakout_qqq", "macd_momentum_iwm",
    "tqqq_cot_combo", "allocator_blend",
]
erc = json.load(open("reports/_erc_weights.json"))
rw = erc["risk_weights"]
wsum = sum(rw.values())
rwn = {k: v / wsum for k, v in rw.items()}
series, meta, spy_ret = X.build_all_series()
ds = sorted(set.intersection(*[set(series[nm].keys()) for nm in LIVE8]))
book = [sum(rwn[nm] * series[nm][d] for nm in LIVE8) for d in ds]
n = len(book)
mean = sum(book) / n
var = sum((x - mean) ** 2 for x in book) / (n - 1)
sd = math.sqrt(var)
ann_vol = sd * math.sqrt(252)
ann_mean = mean * 252
print("book n=", n)
print("daily mean=%.6f daily sd=%.6f" % (mean, sd))
print("annualized mean=%.4f (%.2f%%)" % (ann_mean, ann_mean * 100))
print("annualized vol=%.4f (%.2f%%)" % (ann_vol, ann_vol * 100))
print("naive ann_mean/ann_vol=%.3f" % (ann_mean / ann_vol))
print("engine sharpe=%.3f" % E.sharpe_from_returns(book, E.BPY))
# per-strategy standalone sharpe + vol for context
print("--- per-strategy (on its own dates) ---")
for nm in LIVE8:
    rr = [series[nm][d] for d in sorted(series[nm].keys())]
    m = sum(rr) / len(rr)
    v = math.sqrt(sum((x - m) ** 2 for x in rr) / (len(rr) - 1))
    print("  %-26s n=%4d annVol=%5.1f%% sharpe=%.3f w_risk=%.3f"
          % (nm, len(rr), v * math.sqrt(252) * 100, E.sharpe_from_returns(rr, E.BPY), rwn[nm]))
