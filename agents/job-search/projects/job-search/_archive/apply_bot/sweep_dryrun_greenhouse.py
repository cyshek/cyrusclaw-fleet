"""Quick dry-run sweep of representative Greenhouse URLs.

Picks 6 high-signal Greenhouse roles from the latest discovery to validate
the Greenhouse adapter end-to-end. Mirrors sweep_dryrun.py for Ashby.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

QUEUE = [
    ("Anthropic", "Forward Deployed Engineer Applied AI",
     "https://job-boards.greenhouse.io/anthropic/jobs/4985877008"),
    ("Vercel", "Forward Deployed Engineer v0",
     "https://job-boards.greenhouse.io/vercel/jobs/5872425004"),
    ("Glean", "Forward Deployed Product Manager",
     "https://job-boards.greenhouse.io/gleanwork/jobs/4659409005"),
    ("Scale AI", "Forward Deployed Engineer GenAI",
     "https://job-boards.greenhouse.io/scaleai/jobs/4593571005"),
    ("Robinhood", "Product Manager Money Movement",
     "https://boards.greenhouse.io/robinhood/jobs/7747728"),
    ("Chime", "Product Manager Data Platform",
     "https://boards.greenhouse.io/chime/jobs/8382253002"),
]

RUNS_DIR = Path(__file__).parent / "runs"


def latest_run_dir(company: str, role: str, after_ts: float) -> Path | None:
    slug_co = company.lower().replace(" ", "-")
    slug_role = role.lower().replace(" ", "-").replace(",", "")
    candidates = []
    for d in RUNS_DIR.iterdir():
        if not d.is_dir():
            continue
        if d.stat().st_mtime < after_ts - 5:
            continue
        if slug_co in d.name and slug_role.split("-")[0] in d.name:
            candidates.append(d)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def summarize(rj: Path) -> dict:
    obj = json.loads(rj.read_text(encoding="utf-8"))
    fields = obj.get("fields", [])
    filled = sum(1 for f in fields if f.get("success"))
    total = len(fields)
    notes = obj.get("notes", []) or []
    unanswered = 0
    unhandled_kinds: list[str] = []
    for n in notes:
        if isinstance(n, str):
            if "REFUSING TO SUBMIT" in n and "required" in n:
                for tok in n.replace("\u2014", " ").replace("--", " ").split():
                    if tok.isdigit():
                        unanswered = int(tok)
                        break
        elif isinstance(n, dict):
            for k in n:
                if k.startswith("unhandled"):
                    unhandled_kinds.append(f"{k}:{str(n.get(k, ''))[:50]}")
    return {
        "filled": filled,
        "total": total,
        "submitted": obj.get("submitted", False),
        "unanswered": unanswered,
        "unhandled": unhandled_kinds,
        "error": obj.get("error"),
        "result_path": str(rj),
    }


def main() -> None:
    print(f"Sweeping {len(QUEUE)} Greenhouse URLs in headless dry-run mode...")
    print()
    rows = []
    for i, (co, role, url) in enumerate(QUEUE, 1):
        print(f"[{i}/{len(QUEUE)}] {co} | {role}")
        start_ts = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, "apply.py",
                 "--url", url,
                 "--company", co,
                 "--role", role,
                 "--headless"],
                cwd=str(Path(__file__).parent),
                capture_output=True, text=True, timeout=240,
                encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT")
            rows.append((co, role, "T/O", "T/O", "T/O", [], "timeout"))
            continue
        rd = latest_run_dir(co, role, start_ts)
        if rd is None:
            tail = (proc.stdout or "")[-300:]
            print(f"  no run dir found; stdout tail: {tail}")
            rows.append((co, role, "?", "?", "?", [], "no-rundir"))
            continue
        rj = rd / "result.json"
        if not rj.exists():
            print(f"  result.json missing in {rd.name}")
            rows.append((co, role, "?", "?", "?", [], "no-resultjson"))
            continue
        s = summarize(rj)
        err = s.get("error") or ""
        status = "CLEAN" if s["unanswered"] == 0 and not s["unhandled"] and not err else "ISSUES"
        print(f"  {status}: filled {s['filled']}/{s['total']}, "
              f"unanswered={s['unanswered']}, unhandled={len(s['unhandled'])}, err={err[:60]!r}")
        for u in s["unhandled"]:
            print(f"    - {u}")
        rows.append((co, role, s["filled"], s["total"], s["unanswered"],
                     s["unhandled"], err))

    print()
    print("=" * 78)
    print("GREENHOUSE SWEEP SUMMARY")
    print("=" * 78)
    print(f"{'Co':<12} {'Role':<46} {'Filled':<10} {'Unans':<6} {'Err'}")
    for co, role, filled, total, unans, unh, err in rows:
        role_t = role[:44]
        f = f"{filled}/{total}"
        print(f"{co:<12} {role_t:<46} {f:<10} {str(unans):<6} {err[:30]}")
    clean = sum(1 for r in rows if r[4] == 0 and not r[5] and not r[6])
    print(f"\nCLEAN: {clean}/{len(rows)}")


if __name__ == "__main__":
    main()
