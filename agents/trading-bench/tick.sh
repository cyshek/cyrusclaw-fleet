#!/usr/bin/env bash
# tick.sh — run strategies sequentially; print each receipt.
#
# Usage:
#   tick.sh strat1 strat2 ...           # live runner mode (strategies/<name>/)
#   tick.sh --candidate <name>          # Bar A bullet #7 smoke (strategies_candidates/<name>/, no DB/order)
#
# The --candidate mode is read-only: imports the candidate, calls decide()
# once with live market data, prints the action, exits. No DB writes, no
# orders. Used to satisfy Bar A bullet #7 without forcing premature
# promotion to strategies/.
#
# Dispatch: strategies whose strategy.py exports `decide_xsec` (and not
# `decide`) route to runner.runner_xsec; everything else routes to the
# default single-symbol runner.runner. Detection is a simple grep on a
# top-level `def decide_xsec(` line — matches the canonical signature in
# strategies/<name>/strategy.py without importing the module.
set -euo pipefail
cd "$(dirname "$0")"
set -a
# shellcheck disable=SC1091
source .env
set +a

if [[ "${1:-}" == "--candidate" ]]; then
  shift
  if [[ $# -lt 1 ]]; then
    echo "usage: tick.sh --candidate <name>" >&2
    exit 2
  fi
  python3 -m runner.candidate_smoke --candidate "$1"
  exit $?
fi

for s in "$@"; do
  strat_py="strategies/${s}/strategy.py"
  if [[ -f "$strat_py" ]] && grep -qE '^def decide_xsec\(' "$strat_py"; then
    python3 -m runner.runner_xsec --strategy "$s" || echo "[$s] runner exit=$?"
  else
    python3 -m runner.runner --strategy "$s" || echo "[$s] runner exit=$?"
  fi
done
