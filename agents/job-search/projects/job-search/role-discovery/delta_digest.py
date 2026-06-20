"""Delta digest: report NEW roles added since the previous crawl.

Compares the two most recent `*-roles.json` files in output/ and prints:
  - NEW roles (company, title, location) present in latest but not in prior
  - REMOVED roles (gone from latest)
  - Per-company net new count
  - Markdown summary written to output/{stamp}-delta.md

Usage:
  python delta_digest.py            # latest vs previous
  python delta_digest.py FILE1 FILE2 # explicit paths (FILE1 = older, FILE2 = newer)
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"


def latest_two() -> Tuple[Path, Path]:
    files = sorted(OUTPUT.glob("*-roles.json"))
    if len(files) < 2:
        raise SystemExit(f"Need at least 2 roles.json files in {OUTPUT}, found {len(files)}")
    return files[-2], files[-1]


def role_key(r: dict) -> Tuple[str, str, str]:
    return (
        (r.get("company") or "").strip(),
        (r.get("title") or "").strip(),
        (r.get("location") or "").strip(),
    )


def role_url(r: dict) -> str:
    return r.get("url") or ""


def load_roles(path: Path) -> List[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if len(sys.argv) == 3:
        prev_path = Path(sys.argv[1])
        curr_path = Path(sys.argv[2])
    else:
        prev_path, curr_path = latest_two()

    prev = load_roles(prev_path)
    curr = load_roles(curr_path)

    prev_keys: Set[Tuple[str, str, str]] = {role_key(r) for r in prev}
    curr_keys: Set[Tuple[str, str, str]] = {role_key(r) for r in curr}

    new_keys = curr_keys - prev_keys
    removed_keys = prev_keys - curr_keys

    new_roles = [r for r in curr if role_key(r) in new_keys]
    new_roles.sort(key=lambda r: (r.get("company", ""), r.get("title", "")))

    by_company: Dict[str, List[dict]] = defaultdict(list)
    for r in new_roles:
        by_company[r.get("company", "")].append(r)

    print(f"\n=== Delta: {prev_path.name} -> {curr_path.name} ===")
    print(f"Previous: {len(prev)} roles  |  Current: {len(curr)} roles")
    print(f"NEW: {len(new_roles)}   REMOVED: {len(removed_keys)}   Net: {len(curr) - len(prev):+d}")
    print()

    if new_roles:
        print(f"NEW ROLES ({len(new_roles)}):")
        for company in sorted(by_company):
            roles = by_company[company]
            print(f"\n  {company} ({len(roles)})")
            for r in roles:
                title = r.get("title", "")
                loc = r.get("location", "")
                src = r.get("source", "")
                print(f"    - {title}  [{loc}]  ({src})")
    else:
        print("No new roles.")

    # Companies that lost a lot of postings — sometimes signals API or filter regression
    if removed_keys:
        removed_by_company = Counter(k[0] for k in removed_keys)
        big_drops = [(c, n) for c, n in removed_by_company.most_common() if n >= 3]
        if big_drops:
            print(f"\nNotable drops (>=3 removed):")
            for c, n in big_drops:
                print(f"  - {c}: -{n}")

    # Markdown summary file
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    md = OUTPUT / f"{stamp}-delta.md"
    lines = [
        f"# Delta digest — {curr_path.stem} vs {prev_path.stem}",
        "",
        f"- Previous: **{len(prev)}** roles",
        f"- Current: **{len(curr)}** roles",
        f"- New: **{len(new_roles)}**",
        f"- Removed: **{len(removed_keys)}**",
        f"- Net: **{len(curr) - len(prev):+d}**",
        "",
    ]
    if new_roles:
        lines.append("## New roles")
        for company in sorted(by_company):
            roles = by_company[company]
            lines.append(f"\n### {company} ({len(roles)})\n")
            for r in roles:
                title = r.get("title", "")
                loc = r.get("location", "")
                url = role_url(r)
                if url:
                    lines.append(f"- [{title}]({url}) — {loc}")
                else:
                    lines.append(f"- {title} — {loc}")
    md.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nMarkdown summary: {md}")


if __name__ == "__main__":
    main()
