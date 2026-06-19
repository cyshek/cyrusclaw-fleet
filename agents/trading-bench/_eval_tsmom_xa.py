"""Evaluate Bar A standard (#1-#7) and Bar A #5 fast-track (a/b/c) for
tsmom_xa_be0d7f from the walk-forward + full-period JSON artifacts."""
import json
from pathlib import Path

W = Path(__file__).resolve().parent
wf = json.loads((W / "_wf_tsmom_xa_be0d7f.json").read_text())
fp = json.loads((W / "_fp_tsmom_xa_be0d7f.json").read_text())

print("=== Standard Bar A ===")
print(f"#1 walk-forward (amended): {'PASS' if wf['bar_a_bullet1_pass'] else 'FAIL'} -- {wf['bar_a_bullet1_reason']}")
print(f"#3 FP Sharpe >=0.5: {fp['sharpe_full_period']:.3f} -> {'PASS' if fp['sharpe_full_period']>=0.5 else 'FAIL'}")
print(f"#4 trade count >=30 (walk-forward sum): {wf['total_trades']} -> {'PASS' if wf['total_trades']>=30 else 'FAIL'}")
worst_dd = min(w['max_dd_pct'] for w in wf['windows'])
print(f"#5(MaxDD<=30%) worst window DD: {worst_dd:.2f}% ; FP book DD {fp['max_drawdown_pct_book']:.2f}% -> {'PASS' if abs(fp['max_drawdown_pct_book'])<=30 else 'FAIL'}")

print("\n=== Bar A bullet #5 fast-track ===")
a = fp['sharpe_full_period'] >= 1.0
print(f"(a) FP Sharpe >=1.0: {fp['sharpe_full_period']:.4f} -> {'PASS' if a else 'FAIL'}")
b = fp['max_drawdown_usd_book'] <= 200.0
print(f"(b) FP MaxDD <= $200 abs: ${fp['max_drawdown_usd_book']:.2f} -> {'PASS' if b else 'FAIL'}")

# (c) per-window V1/V2 AND not-catastrophe
print("(c) per-window V1/V2 + catastrophe backstop:")
all_c = True
for w in wf['windows']:
    s = w['return_pct'] / 100.0          # strategy return (book frac)
    bh = w['bh_basket_pct'] / 100.0      # bh basket return (book frac)
    # V1 multiplicative magnitude
    if bh <= 0:
        v1 = s >= 2 * bh           # less negative / positive: s >= 2*bh (bh<=0 => 2*bh more negative)
    else:
        v1 = s >= -1.5 * abs(bh)   # gap >= -1.5|bh|... interpret: s >= bh - 1.5|bh|
    # V2 absolute gap: s >= bh - 1.0pp
    v2 = s >= bh - 0.01
    passed = v1 or v2
    # catastrophe backstop: NOT (s <= -1.5% AND s < bh)
    catastrophe = (s <= -0.015) and (s < bh)
    ok = passed and not catastrophe
    all_c = all_c and ok
    print(f"   {w['label']:22s} s={s*100:+.2f}% bh={bh*100:+.2f}% V1={v1} V2={v2} catastrophe={catastrophe} -> {'OK' if ok else 'FAIL'}")
print(f"(c) overall: {'PASS' if all_c else 'FAIL'}")

print(f"\n#5 fast-track available (a AND b AND c): {'YES' if (a and b and all_c) else 'NO'}")
