"""
Apply CLI.

Usage:
  python apply.py --url <apply-url> --company <co> --role <role> [--live] [--headless]
  python apply.py --top N [--live]   # apply to top-N from Cyrus_Top_Roles.md (dry-run by default)

Default mode is DRY-RUN: opens browser, fills the form, screenshots, but does NOT submit.
Pass --live to actually submit.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

TOP_MD = Path(r"C:\Users\cyrusshekari\Downloads\Cyrus_Top_Roles.md")


def detect_ats(url: str) -> str:
    u = (url or "").lower()
    if "greenhouse" in u:
        return "greenhouse"
    if "ashbyhq" in u or "ashby.com" in u:
        return "ashby"
    if "lever.co" in u:
        return "lever"
    if "workday" in u or "myworkdayjobs" in u:
        return "workday"
    if "linkedin.com" in u:
        return "linkedin"
    return "unknown"


def parse_top_md(top_n: int) -> List[Tuple[str, str, str, str]]:
    """Returns list of (company, role, ats, url) for the top N entries."""
    if not TOP_MD.exists():
        sys.exit(f"missing {TOP_MD}; run rank_roles.py first")
    rows = []
    for line in TOP_MD.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("| #") or "---" in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 7:
            continue
        # | # | Score | Company (tier) | Role | Loc | ATS | Apply URL |
        try:
            int(cells[0])  # ensure first cell is a row number
        except ValueError:
            continue
        company = re.sub(r"\s*\([^)]*\)\s*$", "", cells[2]).strip()
        role = cells[3]
        ats = cells[5].lower()
        url = cells[6]
        rows.append((company, role, ats, url))
        if len(rows) >= top_n:
            break
    return rows


def make_applier(ats: str, url: str, company: str, role: str, dry_run: bool, headless: bool):
    if ats == "greenhouse":
        from greenhouse import GreenhouseApplier
        return GreenhouseApplier(url=url, company=company, role=role,
                                 dry_run=dry_run, headless=headless)
    if ats == "ashby":
        from ashby import AshbyApplier
        return AshbyApplier(url=url, company=company, role=role,
                            dry_run=dry_run, headless=headless)
    if ats == "lever":
        from lever import LeverApplier
        return LeverApplier(url=url, company=company, role=role,
                            dry_run=dry_run, headless=headless)
    raise NotImplementedError(f"adapter for '{ats}' not built yet (have: greenhouse, ashby, lever). "
                              f"Skipping {company} - {role}.")


def main():
    ap = argparse.ArgumentParser(description="Auto-apply harness")
    ap.add_argument("--url", help="Single role URL to apply to")
    ap.add_argument("--company", default="?", help="Company name (for logging)")
    ap.add_argument("--role", default="?", help="Role title (for logging)")
    ap.add_argument("--top", type=int, help="Apply to top N from Cyrus_Top_Roles.md")
    ap.add_argument("--live", action="store_true", help="Actually submit (default: dry-run)")
    ap.add_argument("--headless", action="store_true", help="Run browser headless")
    ap.add_argument("--prep", action="store_true",
                    help="Fill the form, leave browser open, wait for human to click Submit. "
                         "Defeats reCAPTCHA Enterprise v3 by relying on real human signals.")
    ap.add_argument("--otp", help="Pre-supply the 8-char Greenhouse OTP if you already have one")
    ap.add_argument("--gmail-imap", action="store_true",
                    help="Auto-fetch OTP from Gmail via IMAP (requires assets/.gmail_credentials)")
    args = ap.parse_args()

    if not args.url and not args.top:
        ap.error("must provide --url or --top")

    if args.prep and args.headless:
        ap.error("--prep requires a visible browser; do not pass --headless")

    dry_run = not args.live and not args.prep

    if args.url:
        ats = detect_ats(args.url)
        print(f"Detected ATS: {ats}")
        if ats not in ("greenhouse", "ashby", "lever"):
            print(f"WARNING: only Greenhouse, Ashby, and Lever adapters are built; "
                  f"this URL looks like '{ats}'. Aborting.")
            sys.exit(1)
        applier = make_applier(ats, args.url, args.company, args.role, dry_run, args.headless)
        if args.prep:
            applier.prep_mode = True
        if args.otp:
            applier._otp_provider = lambda _recipient: args.otp
        elif args.gmail_imap:
            try:
                from gmail_otp import GmailOtpPoller
                poller = GmailOtpPoller()
                poller.mark_poll_start()
                applier._otp_provider = poller.fetch_otp
                print("[gmail-imap] poller armed; will auto-fetch OTP from inbox")
            except Exception as e:
                print(f"[gmail-imap] disabled: {e}")
        applier.run()
        return

    rows = parse_top_md(args.top)
    print(f"Loaded top {len(rows)} roles from {TOP_MD.name}")

    # Build set of URLs we've already successfully submitted (avoid duplicates)
    submitted_urls = set()
    runs_dir = Path(__file__).parent / "runs"
    if runs_dir.exists():
        import json as _json
        for run in runs_dir.iterdir():
            rj = run / "result.json"
            if rj.exists():
                try:
                    obj = _json.loads(rj.read_text(encoding="utf-8"))
                    if obj.get("submitted") and obj.get("url"):
                        submitted_urls.add(obj["url"])
                except Exception:
                    pass
    if submitted_urls:
        print(f"  ({len(submitted_urls)} url(s) already submitted in prior runs - will skip)")

    for i, (co, role, ats, url) in enumerate(rows, 1):
        print(f"\n[{i}/{len(rows)}] {co} | {role} | ATS={ats}")
        if url in submitted_urls:
            print(f"  skip: already submitted in a prior run")
            continue
        if ats != "greenhouse" and ats != "ashby" and ats != "lever":
            print(f"  skip: {ats} adapter not built yet")
            continue
        try:
            applier = make_applier(ats, url, co, role, dry_run, args.headless)
            if args.prep:
                applier.prep_mode = True
            if args.otp:
                applier._otp_provider = lambda _recipient, _o=args.otp: _o
            elif args.gmail_imap:
                try:
                    from gmail_otp import GmailOtpPoller
                    poller = GmailOtpPoller()
                    poller.mark_poll_start()
                    applier._otp_provider = poller.fetch_otp
                except Exception as e:
                    print(f"  [gmail-imap] disabled: {e}")
            applier.run()
            # Polite pause between live submissions
            if args.live and i < len(rows):
                import time as _t
                _t.sleep(15)
        except Exception as e:
            print(f"  failed: {e}")


if __name__ == "__main__":
    main()
