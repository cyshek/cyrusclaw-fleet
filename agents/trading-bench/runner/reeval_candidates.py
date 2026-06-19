"""Re-evaluate all quarantined candidates against the (now fixed) backtester.

For each strategies_candidates/<name>/ dir:
  1. Load strategy module + params
  2. Look up parent (strip __mut_xxxxxx suffix)
  3. Run walk_forward() on parent and mutant
  4. Apply mutation_gate
  5. Print one CSV-ish line per candidate

Writes a summary report to RE_EVAL_<timestamp>.md.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from runner.walk_forward import walk_forward, passes_mutation_gate  # noqa: E402

CANDIDATES_ROOT = WORKSPACE / "strategies_candidates"


def _load_mutant(mut_dir: Path):
    name = mut_dir.name
    spec = importlib.util.spec_from_file_location(f"reeval_{name}",
                                                  mut_dir / "strategy.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"reeval_{name}"] = mod
    spec.loader.exec_module(mod)
    params = json.loads((mut_dir / "params.json").read_text())
    return mod, params


def _parent_of(mut_name: str) -> str:
    # naming convention: parent__mut_xxxxxx
    if "__mut_" in mut_name:
        return mut_name.split("__mut_")[0]
    return mut_name


def main():
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = WORKSPACE / f"RE_EVAL_{ts}.md"
    rows = []
    cands = sorted(d for d in CANDIDATES_ROOT.iterdir() if d.is_dir())
    print(f"Re-evaluating {len(cands)} candidates...", file=sys.stderr)
    # Cache parent results so we don't recompute per mutant.
    parent_cache: dict = {}
    t0 = time.time()
    for i, mut_dir in enumerate(cands, 1):
        name = mut_dir.name
        parent = _parent_of(name)
        try:
            mod, params = _load_mutant(mut_dir)
        except Exception as e:
            rows.append({"name": name, "parent": parent, "verdict": "LOAD_ERROR",
                         "err": str(e)[:200]})
            print(f"[{i}/{len(cands)}] {name} LOAD_ERROR: {e}", file=sys.stderr)
            continue
        try:
            if parent not in parent_cache:
                pagg = walk_forward(parent)
                parent_cache[parent] = pagg
            pagg = parent_cache[parent]
            magg = walk_forward(name, params=params, decide_fn=mod.decide)
            gate_passes, gate_reason = passes_mutation_gate(magg, pagg)
            rows.append({
                "name": name, "parent": parent,
                "verdict": "PROMOTE" if gate_passes else "REJECT_GATE",
                "reason": gate_reason,
                "medRet": magg.median_return_pct,
                "p_medRet": pagg.median_return_pct,
                "delta_pp": (magg.median_return_pct - pagg.median_return_pct),
                "medSharpe": magg.median_sharpe,
            })
            elapsed = time.time() - t0
            # median_return_pct is already percent (e.g. 0.41 = 0.41%); don't ×100 again.
            print(f"[{i}/{len(cands)}] {name} {rows[-1]['verdict']} "
                  f"medRet={magg.median_return_pct:+.3f}% (p {pagg.median_return_pct:+.3f}%) "
                  f"Δ={magg.median_return_pct - pagg.median_return_pct:+.3f}pp  [{elapsed:.0f}s]",
                  file=sys.stderr)
        except Exception as e:
            rows.append({"name": name, "parent": parent, "verdict": "BACKTEST_ERROR",
                         "err": str(e)[:200]})
            print(f"[{i}/{len(cands)}] {name} BACKTEST_ERROR: {e}", file=sys.stderr)

    # Write report
    lines = [f"# Re-evaluation report {ts}",
             "",
             f"_Re-ran all {len(cands)} quarantined candidates against the fixed backtester (position_state state-persistence fix)._",
             "",
             "## Summary",
             "",
             "| # | Candidate | Parent | Verdict | medRet | parent medRet | Δ (pp) | medSharpe | Notes |",
             "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        if r["verdict"] in ("LOAD_ERROR", "BACKTEST_ERROR"):
            lines.append(f"| {i} | `{r['name']}` | `{r['parent']}` | "
                         f"⚠️ {r['verdict']} |  |  |  |  | {r.get('err','')} |")
        else:
            icon = "✅ PROMOTE" if r["verdict"] == "PROMOTE" else "🟡 REJECT_GATE"
            lines.append(
                f"| {i} | `{r['name']}` | `{r['parent']}` | {icon} | "
                f"{r['medRet']:+.3f}% | {r['p_medRet']:+.3f}% | "
                f"{r['delta_pp']:+.3f} | {r['medSharpe']:+.3f} | {r.get('reason','')[:120]} |"
            )
    promotes = [r for r in rows if r["verdict"] == "PROMOTE"]
    lines.append("")
    lines.append(f"**PROMOTE: {len(promotes)} / {len(rows)}**")
    if promotes:
        lines.append("")
        lines.append("## Promoted candidates")
        for p in promotes:
            lines.append(f"- `{p['name']}` (parent `{p['parent']}`, "
                         f"Δ={p['delta_pp']:+.3f}pp, Sharpe {p['medSharpe']:+.3f})")

    out_path.write_text("\n".join(lines))
    print(f"\nReport: {out_path}", file=sys.stderr)
    print(f"PROMOTE: {len(promotes)} / {len(rows)}", file=sys.stderr)


if __name__ == "__main__":
    main()
