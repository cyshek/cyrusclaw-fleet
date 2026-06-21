import sqlite3
db = sqlite3.connect('tournament.db')
cur = db.cursor()

live = ['breakout_xlk','breakout_xlk_regime','breakout_xlk__mut_c382b1',
        'sma_crossover_qqq','sma_crossover_qqq_regime','sma_crossover_qqq_rth',
        'leveraged_long_trend_paper','tqqq_cot_combo',
        'rsi_oversold_spy','volume_breakout_qqq','macd_momentum_iwm']

print('=== LIVE STRATEGIES RANKINGS ===')
for s in live:
    cur.execute('''
      SELECT n_trades, realized_usd, unrealized_usd, total_usd, win_rate, ts_utc
      FROM rankings WHERE strategy=?
      ORDER BY ts_utc DESC LIMIT 1
    ''', (s,))
    r = cur.fetchone()
    if r:\n        print(f'{s}: trades={r[0]} realized=${r[1]:.2f} unreal=${r[2]:.2f} total=${r[3]:.2f} wr={r[4]} ({r[5][:10]})')
    else:
        print(f'{s}: NO RANKING DATA')

print()
print('=== TQQQ NET POSITIONS ===')
for strat in ['leveraged_long_trend_paper','tqqq_cot_combo']:
    cur.execute("SELECT side, SUM(qty), AVG(price), SUM(notional_usd) FROM trades WHERE strategy=? GROUP BY side", (strat,))
    print(f'--- {strat} ---')
    for r in cur.fetchall():
        print(f'  side={r[0]} total_qty={r[1]:.4f} avg_price={r[2]:.3f} total_notional={r[3]:.2f}')

print()
print('=== CRON STATUS ===')
import subprocess
result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
print(result.stdout)
