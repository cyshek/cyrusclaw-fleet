#!/bin/bash
# Daily Polymarket paper-tracker: snapshot flagged markets, place/settle paper bets, score resolved.
# Logs to logs/polymarket_track.log

cd /home/azureuser/.openclaw/agents/trading-bench/workspace

python3 -c "
from runner.polymarket_tracker import snapshot_flagged_markets, score_resolved_markets, place_paper_bets, settle_paper_bets

snapped = snapshot_flagged_markets()
scored = score_resolved_markets()
bets_placed = place_paper_bets(min_edge=0.08, stake=100.0)
settled = settle_paper_bets()

print(
    f'Snapped {snapped} markets. '
    f'Resolved today: {scored.get(\"newly_resolved\", 0)}. '
    f'Running accuracy: {scored.get(\"accuracy_pct\", \"N/A\")}%. '
    f'Paper bets placed: {bets_placed}. '
    f'Settled today: {settled.get(\"newly_settled\", 0)} '
    f'(won={settled.get(\"won\", 0)}, lost={settled.get(\"lost\", 0)}, '
    f'pnl=\${settled.get(\"total_pnl\", 0.0):.2f}).'
)
" >> logs/polymarket_track.log 2>&1
