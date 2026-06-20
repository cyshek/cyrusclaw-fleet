#!/usr/bin/env python3
"""Per-adapter role-count delta sanity check.

Reads the two most recent `output/*-roles.json` files and computes per-company
(and per-ATS-adapter) role count deltas. If any adapter's aggregate count drops
>THRESHOLD week-over-week, writes `output/_delta-anomalies-<stamp>.md` and
exits 1 so the calling shell script can post a WARN. Otherwise exits 0.

Lookup company → adapter is done via `companies.yaml`.

Run after `run.py` in `weekly_run.sh`.
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

HERE = Path(__file__).parent
OUT_DIR = HERE / "output"
COMPANIES_YAML = HERE / "companies.yaml"

# Threshold: drop must exceed this fraction to fire. 0.50 == 50%.
DROP_THRESHOLD = 0.50
# Don't fire on tiny absolute numbers (e.g. 3 → 1 is 66% but noise).
MIN_BASELINE = 5


def _latest_two_role_jsons() -> tuple[Path | None, Path | None]:
    files = sorted(OUT_DIR.glob("*-roles.json"))
    if len(files) < 2:
        return (files[-1] if files else None, None)
    return files[-1], files[-2]


def _load_company_to_adapter() -> dict[str, str]:
    data = yaml.safe_load(COMPANIES_YAML.read_text())
    out = {}
    for c in data.get("companies", []):
        name = c.get("name")
        adapter = c.get("adapter")
        if name and adapter:
            out[name.lower()] = adapter
    return out


def _counts_by_adapter(roles_json_path: Path, c2a: dict[str, str]) -> dict[str, int]:
    try:
        roles = json.loads(roles_json_path.read_text())
    except Exception:
        return {}
    counts: dict[str, int] = {}
    for r in roles:
        company = (r.get("company") or "").lower()
        adapter = c2a.get(company, "_unmapped")
        counts[adapter] = counts.get(adapter, 0) + 1
    return counts


def main():
    newest, prev = _latest_two_role_jsons()
    if newest is None or prev is None:
        print("delta_check: need at least 2 *-roles.json files; skipping.")
        return 0

    c2a = _load_company_to_adapter()
    cur = _counts_by_adapter(newest, c2a)
    base = _counts_by_adapter(prev, c2a)

    anomalies: list[tuple[str, int, int, float]] = []
    for adapter in sorted(set(cur) | set(base)):
        b = base.get(adapter, 0)
        n = cur.get(adapter, 0)
        if b < MIN_BASELINE:
            continue
        drop = (b - n) / b
        if drop > DROP_THRESHOLD:
            anomalies.append((adapter, b, n, drop))

    print(f"delta_check: cur={newest.name} prev={prev.name}")
    print(f"  per-adapter counts: cur={cur} prev={base}")
    if not anomalies:
        print("  no anomalies (>%.0f%% drop on any adapter)" % (DROP_THRESHOLD * 100))
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    out_path = OUT_DIR / f"_delta-anomalies-{stamp}.md"
    lines = [
        f"# Delta anomalies — {stamp} UTC",
        "",
        f"Compared `{newest.name}` (current) vs `{prev.name}` (previous).",
        f"Threshold: any adapter losing >{int(DROP_THRESHOLD*100)}% of roles week-over-week, baseline >= {MIN_BASELINE}.",
        "",
        "| Adapter | Previous | Current | Drop |",
        "| --- | --- | --- | --- |",
    ]
    for adapter, b, n, drop in anomalies:
        lines.append(f"| {adapter} | {b} | {n} | {drop*100:.0f}% |")
    lines.append("")
    lines.append("Likely causes: adapter shape change, ATS endpoint move, tenant-wide outage, listing churn.")
    lines.append("Action: spot-check one company on the affected adapter manually before next crawl.")
    out_path.write_text("\n".join(lines))
    print(f"  wrote: {out_path}")
    for adapter, b, n, drop in anomalies:
        print(f"  ANOMALY  {adapter:18} {b} -> {n}  (-{drop*100:.0f}%)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
