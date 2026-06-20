"""Dry-run sweep of one role per UNTOUCHED Ashby tenant.

Validates the adapter on tenants we have zero history with, surfacing
new field-shapes / unhandled radios before any live submit.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

QUEUE = [
    ("Ramp", "Product Manager Generalist",
     "https://jobs.ashbyhq.com/ramp/9972df9e-4133-4e2c-9305-49c285b76506"),
    ("Plaid", "Product Manager",
     "https://jobs.ashbyhq.com/plaid/64642463-8ee8-4453-b166-449711f61cd0"),
    ("ElevenLabs", "Enterprise Solutions Engineer",
     "https://jobs.ashbyhq.com/elevenlabs/275f43d0-b62d-401d-830c-7c1ac0e688aa"),
    ("LangChain", "Product Manager LangSmith",
     "https://jobs.ashbyhq.com/langchain/27af5f96-b287-4bcc-8679-f96686dc7c8d"),
    ("Bland", "Customer Engineer",
     "https://jobs.ashbyhq.com/bland/804fbd27-027e-4de5-8a6f-77241a65e599"),
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
    refused = False
    for n in notes:
        if isinstance(n, str):
            if "REFUSING TO SUBMIT" in n and "required" in n:
                refused = True
                for tok in n.replace("\u2014", " ").replace("--", " ").split():
                    if tok.isdigit():
                        unanswered = int(tok)
                        break
        elif isinstance(n, dict):
            for k in n:
                if k.startswith("unhandled"):
                    unhandled_kinds.append(f"{k}:{str(n.get(k, ''))[:80]}")
    return {
        "filled": filled,
        "total": total,
        "submitted": obj.get("submitted", False),
        "unanswered": unanswered,
        "unhandled": unhandled_kinds,
        "refused": refused,
        "result_path": str(rj),
    }


def main() -> None:
    print(f"Sweeping {len(QUEUE)} fresh-tenant URLs in headless dry-run mode...")
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
            print(f"  TIMEOUT after 240s")
            rows.append((co, role, "?", "?", "TIMEOUT", []))
            continue
        rd = latest_run_dir(co, role, start_ts)
        if rd is None:
            tail = (proc.stdout or "")[-300:]
            print(f"  NO RUN DIR; stdout tail: {tail!r}")
            rows.append((co, role, "?", "?", "NO_DIR", []))
            continue
        rj = rd / "result.json"
        if not rj.exists():
            print(f"  result.json missing in {rd.name}")
            rows.append((co, role, "?", "?", "NO_RESULT", []))
            continue
        s = summarize(rj)
        status = "CLEAN" if s["unanswered"] == 0 and not s["unhandled"] else "ISSUES"
        print(f"  {status}: filled {s['filled']}/{s['total']}, "
              f"unanswered={s['unanswered']}, unhandled={len(s['unhandled'])}, "
              f"submitted={s['submitted']}")
        for u in s["unhandled"]:
            print(f"    - {u}")
        rows.append((co, role, s["filled"], s["total"], s["unanswered"],
                     s["unhandled"]))

    print()
    print("=" * 78)
    print("FRESH-TENANT SWEEP SUMMARY")
    print("=" * 78)
    print(f"{'Co':<12} {'Role':<42} {'Filled':<10} {'Unans':<6} {'Unh'}")
    for co, role, filled, total, unans, unh in rows:
        role_t = role[:40]
        f = f"{filled}/{total}"
        unh_n = len(unh) if isinstance(unh, list) else "?"
        print(f"{co:<12} {role_t:<42} {f:<10} {str(unans):<6} {unh_n}")
    clean = sum(1 for r in rows
                if isinstance(r[5], list) and r[4] == 0 and not r[5])
    print(f"\nCLEAN (0-unanswered, 0-unhandled): {clean}/{len(rows)}")


if __name__ == "__main__":
    main()
