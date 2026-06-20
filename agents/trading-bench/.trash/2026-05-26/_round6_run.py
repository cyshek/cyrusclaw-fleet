"""One-off round 6: sample ONLY from the 4 new exit-side directives (#10-13)
so we get actual signal on each before tuning further."""
import sys, time
from runner.tournament_loop import run_one_round
from runner.strategy_gen import MUTATION_DIRECTIVES

# Directives 10-13 (0-indexed 9-12): regime-cond stop, partial exit, time-stop, trailing stop.
new_directives = MUTATION_DIRECTIVES[9:13]
print(f"Sampling from {len(new_directives)} new directives only:")
for i, d in enumerate(new_directives, 10):
    print(f"  #{i}. {d[:80]}...")

result = run_one_round(n_candidates=6, seed=20265266, directives=new_directives)
print(f"\nDone. Report: {result.get('report_path')}")
