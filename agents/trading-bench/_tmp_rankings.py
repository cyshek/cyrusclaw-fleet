import sqlite3, subprocess

db = sqlite3.connect('tournament.db')
cur = db.cursor()

live = [
    'breakout_xlk','breakout_xlk_regime','breakout_xlk__mut_c382b1',
    'sma_crossover_qqq','sma_crossover_qqq_regime','sma_crossover_qqq_rth',
    'leveraged_long_trend_paper','tqqq_cot_combo',
    'rsi_oversold_spy','volume_breakout_qqq','macd_momentum_iwm'
]

print('=== LIVE STRATEGIES RANKINGS ===')
for s in live:
    cur.execute(
        'SELECT n_trades, realized_usd, unrealized_usd, total_usd, win_rate, ts_utc '
        'FROM rankings WHERE strategy=? ORDER BY ts_utc DESC LIMIT 1', (s,)
    )
    r = cur.fetchone()
    if r:\n+        wr = '{:.0%}'.format(r[4]) if r[4] is not None else 'n/a'
        print('{}: trades={} realized={:+.2f} unreal={:+.2f} total={:+.2f} wr={}'.format(s, r[0], r[1], r[2], r[3], wr))
    else:
        print('{}: NO RANKING DATA'.format(s))

print('')
print('=== TQQQ NET POSITIONS ===')
for strat in ['leveraged_long_trend_paper','tqqq_cot_combo']:
    cur.execute(
        'SELECT side, SUM(qty), AVG(price), SUM(notional_usd) FROM trades '
        'WHERE strategy=? GROUP BY side', (strat,)
    )
    print('--- {} ---'.format(strat))
    for r in cur.fetchall():
        print('  side={} total_qty={:.4f} avg_price={:.3f} total_notional={:.2f}'.format(r[0], r[1], r[2], r[3]))

print('')
result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
print('=== CRONTAB ===')
print(result.stdout)
