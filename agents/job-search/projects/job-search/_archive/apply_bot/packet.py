"""
Packet mode: generate a copy-paste-ready application packet for a role.

The bot dry-runs the form (no submit) to scrape every question and the answer
it would have used. We render that as a markdown packet so YOU can fill the
form in your own browser. Zero submit-side anti-bot risk — the bot never
clicks anything you can't see.

Workflow:
  1. python packet.py --url <apply-url>
  2. Bot scrapes the form (dry-run) and writes packet.md
  3. Packet opens in your default editor; URL opens in your default browser
  4. Copy-paste from packet, drag-drop the resume, click Submit yourself

Usage:
  python packet.py --url <apply-url> [--company <co>] [--role <role>] [--no-open]
  python packet.py --top N            # generate packets for top-N from Cyrus_Top_Roles.md
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import webbrowser
from pathlib import Path
from typing import Any, Dict

from apply import detect_ats, make_applier, parse_top_md
from base import RESUME, PROFILE


METHOD_ICONS = {
    "type": "⌨️ text",
    "fill": "⌨️ text",
    "typeahead": "🔍 typeahead",
    "select": "📋 dropdown",
    "radio": "🔘 radio",
    "checkbox": "☑️ checkbox",
    "upload": "📎 upload",
    "click": "🖱️ click",
}


def render_packet(result: Dict[str, Any], personal: Dict[str, Any], packet_path: Path) -> None:
    co = result.get("company") or "?"
    role = result.get("role") or "?"
    url = result.get("url") or ""
    ats = result.get("ats") or "?"

    contact = personal.get("contact") or {}
    ident = personal.get("identity") or {}
    addr = personal.get("address") or {}

    lines = []
    lines.append(f"# Application Packet — {co} · {role}")
    lines.append("")
    lines.append(f"**ATS:** `{ats}`  ")
    lines.append(f"**Apply URL:** {url}  ")
    lines.append("")
    lines.append("> ⚠️ **Open the URL in your normal Chrome** (real profile, real cookies, real history).")
    lines.append("> Do NOT use the bot's browser. Copy-paste from this packet, drag-drop the resume, click Submit yourself.")
    lines.append("")

    lines.append("## Quick Reference")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"| --- | --- |")
    lines.append(f"| Name | {ident.get('first_name','?')} {ident.get('last_name','?')} |")
    lines.append(f"| Email | `{contact.get('email','?')}` |")
    lines.append(f"| Phone | `{contact.get('phone','?')}` |")
    lines.append(f"| LinkedIn | {contact.get('linkedin','?')} |")
    lines.append(f"| GitHub | {contact.get('github','?')} |")
    lines.append(f"| Location | {addr.get('city','?')}, {addr.get('state','?')} {addr.get('zip','?')} |")
    lines.append(f"| Resume file | `{RESUME}` |")
    lines.append("")

    fields = result.get("fields") or []
    if not fields:
        lines.append("## Form Fields")
        lines.append("")
        lines.append("_Bot did not detect any fields. Open the URL and fill manually._")
    else:
        lines.append(f"## Form Fields — {len(fields)} detected")
        lines.append("")
        for i, f in enumerate(fields, 1):
            label = f.get("label") or f.get("selector") or f"Field {i}"
            value = f.get("value") or ""
            method = (f.get("method") or "type").lower()
            success = f.get("success", True)
            icon = METHOD_ICONS.get(method, f"❓ {method}")
            warn = "" if success else "  ⚠️ (bot couldn't fill — manual entry needed)"

            lines.append(f"### {i}. {label}")
            lines.append(f"_{icon}_{warn}")
            lines.append("")
            if method == "upload":
                lines.append(f"📎 Upload file:")
                lines.append(f"`{value}`")
            elif method in ("radio", "select", "checkbox"):
                lines.append(f"Select / pick: **{value}**")
            elif method == "typeahead":
                lines.append("Type, then pick from suggestions:")
                lines.append("")
                lines.append("```")
                lines.append(str(value))
                lines.append("```")
            else:
                lines.append("```")
                lines.append(str(value))
                lines.append("```")
            lines.append("")

    notes = result.get("notes") or []
    if notes:
        lines.append("## Bot Scrape Notes")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("**When done, mark this role applied:** record in your tracker so we don't packet it twice.")
    lines.append("")

    packet_path.write_text("\n".join(lines), encoding="utf-8")


def build_packet(url: str, company: str, role: str, personal: Dict[str, Any],
                 headless: bool = True) -> Path | None:
    ats = detect_ats(url)
    if ats not in ("greenhouse", "ashby", "lever"):
        print(f"  [skip] adapter not built for '{ats}' (have: greenhouse, ashby, lever)")
        return None

    print(f"  [scrape] ATS={ats} → dry-run scraping form...")
    applier = make_applier(ats, url, company, role, dry_run=True, headless=headless)
    try:
        applier.run()
    except Exception as e:
        print(f"  [error] dry-run failed: {e}")
        return None

    result_path = applier.run_dir / "result.json"
    if not result_path.exists():
        print(f"  [error] no result.json at {result_path}")
        return None

    result = json.loads(result_path.read_text(encoding="utf-8"))
    packet_path = applier.run_dir / "packet.md"
    render_packet(result, personal, packet_path)
    n_fields = len(result.get("fields") or [])
    print(f"  [ok] {n_fields} fields scraped → {packet_path}")
    return packet_path


def main():
    ap = argparse.ArgumentParser(description="Generate application packet (no submit)")
    ap.add_argument("--url", help="Single role URL")
    ap.add_argument("--company", default="?")
    ap.add_argument("--role", default="?")
    ap.add_argument("--top", type=int, help="Generate packets for top-N from Cyrus_Top_Roles.md")
    ap.add_argument("--no-open", action="store_true",
                    help="Don't auto-open the packet/URL after building")
    ap.add_argument("--no-headless", action="store_true",
                    help="Show the bot's scraping browser (default: headless)")
    args = ap.parse_args()

    if not args.url and not args.top:
        ap.error("must provide --url or --top")

    if not PROFILE.exists():
        sys.exit(f"missing {PROFILE}")
    personal = json.loads(PROFILE.read_text(encoding="utf-8"))
    if not RESUME.exists():
        sys.exit(f"missing resume at {RESUME}")

    headless = not args.no_headless

    if args.url:
        print(f"[packet] {args.company} | {args.role}")
        packet_path = build_packet(args.url, args.company, args.role, personal, headless)
        if packet_path and not args.no_open:
            print("[packet] opening packet + URL...")
            try:
                os.startfile(str(packet_path))
            except Exception as e:
                print(f"  [warn] could not auto-open packet: {e}")
            try:
                webbrowser.open(args.url)
            except Exception as e:
                print(f"  [warn] could not auto-open URL: {e}")
        return

    rows = parse_top_md(args.top)
    print(f"[packet] generating packets for {len(rows)} roles")
    built = []
    for i, (co, role, ats, url) in enumerate(rows, 1):
        print(f"\n[{i}/{len(rows)}] {co} | {role} | ATS={ats}")
        packet_path = build_packet(url, co, role, personal, headless)
        if packet_path:
            built.append((co, role, url, packet_path))
    print(f"\n[packet] built {len(built)} packets:")
    for co, role, url, p in built:
        print(f"  - {co} · {role}\n      packet: {p}\n      url:    {url}")


if __name__ == "__main__":
    main()
