"""
Dry-run sweep for Lever adapter against the 4 known Lever URLs in current discovery.
Reports unanswered required fields per role.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from lever import LeverApplier

# 4 Lever URLs from 20260505-1319-roles.json
URLS = [
    ("Spotify", "Software Engineer (Spotify)",
     "https://jobs.lever.co/spotify/a4a933ce-ab44-4a13-b8ca-8575c97ea40a"),
    ("Palantir", "Palantir role 1",
     "https://jobs.lever.co/palantir/96a0ce26-cf84-4fa8-934b-acc4363620b2"),
    ("Palantir", "Palantir role 2",
     "https://jobs.lever.co/palantir/7eb0dedb-37ee-4175-b29f-10a9e4340076"),
    ("Palantir", "Palantir role 3",
     "https://jobs.lever.co/palantir/bd16f7ad-3bee-48fd-9902-b3ee9698b608"),
]


def main():
    summary = []
    for co, role, url in URLS:
        print("\n" + "=" * 80)
        print(f"{co} — {role}")
        print(url)
        try:
            app = LeverApplier(url=url, company=co, role=role,
                               dry_run=True, headless=True)
            app.run()
            unanswered = []
            for n in app.result.notes:
                if isinstance(n, dict) and "unanswered" in n:
                    unanswered = n["unanswered"]
                    break
            filled = sum(1 for f in app.result.fields if f.success)
            errs = sum(1 for f in app.result.fields if not f.success)
            summary.append({
                "company": co, "role": role, "url": url,
                "filled": filled, "field_errors": errs,
                "unanswered_required": unanswered,
                "fatal": app.result.error,
                "run_dir": str(app.run_dir),
            })
        except Exception as e:
            summary.append({
                "company": co, "role": role, "url": url,
                "fatal": f"{type(e).__name__}: {e}",
            })
    print("\n\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_un = 0
    for s in summary:
        un = s.get("unanswered_required") or []
        total_un += len(un)
        print(f"\n{s['company']} — {s['role']}")
        print(f"  filled OK: {s.get('filled', 0)}  field-errors: {s.get('field_errors', 0)}")
        if s.get("fatal"):
            print(f"  FATAL: {s['fatal']}")
        if un:
            print(f"  UNANSWERED REQUIRED ({len(un)}):")
            for u in un:
                print(f"    - {u}")
        else:
            print(f"  OK no unanswered required fields")
    print(f"\nTOTAL unanswered required across {len(URLS)} roles: {total_un}")


if __name__ == "__main__":
    main()
