"""Quick dry-run sweep of all queued Ashby URLs.

For each URL, run apply.py headless dry-run, parse result.json, and print:
  - filled/total
  - unanswered_required count
  - any unhandled-radio-group / unhandled-field-type notes (truncated)

Used to validate the radio-group + select handlers cover all queued forms
before any live retry. NOT a replacement for batch_ashby.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

QUEUE = [
    ("Decagon", "Technical Program Manager",
     "https://jobs.ashbyhq.com/decagon/d32da775-c5ea-420d-a07e-13412044c27b"),
    ("OpenAI", "Deployed Product Manager Codex",
     "https://jobs.ashbyhq.com/openai/60d1420a-8aa3-4d87-847e-e7b73d9d9a0c"),
    ("OpenAI", "Product Manager API Infrastructure",
     "https://jobs.ashbyhq.com/openai/7ffa2a14-fa9c-46cb-a30a-1f7a35ae904a"),
    ("Sierra", "Product Manager Agent SDK",
     "https://jobs.ashbyhq.com/sierra/10d2e2f1-6657-40c9-b6fb-6999c76df6cf"),
    ("Harvey", "Employee Experience Program Manager",
     "https://jobs.ashbyhq.com/harvey/da9f2961-fcfd-401f-a86a-9e548290b4a4"),
    ("OpenAI", "Technical Program Manager Adversarial Model Research",
     "https://jobs.ashbyhq.com/openai/65913e57-80e0-4a1a-bbc3-265ae8a1a41b"),
    ("Sierra", "Product Manager Agent Studio",
     "https://jobs.ashbyhq.com/sierra/5aaa2eeb-92bc-4b0a-901e-8e091eff819e"),
    ("OpenAI", "Technical Program Manager Human Data",
     "https://jobs.ashbyhq.com/openai/71004494-9a55-4ed5-b458-2ff475f0d881"),
]

RUNS_DIR = Path(__file__).parent / "runs"


def latest_run_dir(company: str, role: str, after_ts: float) -> Path | None:
    slug_co = company.lower()
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
                # message format: "REFUSING TO SUBMIT — N required field(s) still blank"
                # extract integer
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
        "result_path": str(rj),
    }


def main() -> None:
    print(f"Sweeping {len(QUEUE)} URLs in headless dry-run mode...")
    print()
    rows = []
    for i, (co, role, url) in enumerate(QUEUE, 1):
        print(f"[{i}/{len(QUEUE)}] {co} | {role}")
        start_ts = time.time()
        proc = subprocess.run(
            [sys.executable, "apply.py",
             "--url", url,
             "--company", co,
             "--role", role,
             "--headless"],
            cwd=str(Path(__file__).parent),
            capture_output=True, text=True, timeout=180,
            encoding="utf-8", errors="replace",
        )
        rd = latest_run_dir(co, role, start_ts)
        if rd is None:
            print(f"  no run dir found; stdout tail: {proc.stdout[-200:]}")
            rows.append((co, role, "?", "?", "?", []))
            continue
        rj = rd / "result.json"
        if not rj.exists():
            print(f"  result.json missing in {rd.name}")
            rows.append((co, role, "?", "?", "?", []))
            continue
        s = summarize(rj)
        status = "CLEAN" if s["unanswered"] == 0 and not s["unhandled"] else "ISSUES"
        print(f"  {status}: filled {s['filled']}/{s['total']}, "
              f"unanswered={s['unanswered']}, unhandled={len(s['unhandled'])}")
        for u in s["unhandled"]:
            print(f"    - {u}")
        rows.append((co, role, s["filled"], s["total"], s["unanswered"],
                     s["unhandled"]))

    print()
    print("=" * 70)
    print("SWEEP SUMMARY")
    print("=" * 70)
    print(f"{'Co':<10} {'Role':<50} {'Filled':<10} {'Unans':<6} {'Unh'}")
    for co, role, filled, total, unans, unh in rows:
        role_t = role[:48]
        f = f"{filled}/{total}"
        print(f"{co:<10} {role_t:<50} {f:<10} {str(unans):<6} {len(unh)}")
    clean = sum(1 for r in rows if r[4] == 0 and not r[5])
    print(f"\nCLEAN: {clean}/{len(rows)}")


if __name__ == "__main__":
    main()
