"""
nightly_scan.py -- Main entry point for the nightly interview detection cron.
Runs at 2am PST daily. Scans Gmail, deduplicates, looks up tracker, notifies Cyrus.
"""

import sys
import os
import json
import datetime

# Add pipeline dir to path
sys.path.insert(0, os.path.dirname(__file__))

from gmail_scanner import scan_gmail_inbox, lookup_tracker_role
from calendar_scanner import scan_calendar
from dedup_store import filter_new_signals
from notifier import notify_cyrus
from interviews_tracker import process_signals


def run():
    print(f"[nightly_scan] Starting at {datetime.datetime.now().isoformat()}")

    # 1. Scan Gmail inbox + Calendar
    gmail_signals = scan_gmail_inbox()
    calendar_signals = scan_calendar()
    all_signals = gmail_signals + calendar_signals
    print(f"[nightly_scan] Raw signals: Gmail={len(gmail_signals)}, Calendar={len(calendar_signals)}")

    # 2. Deduplicate against seen signals
    new_signals = filter_new_signals(all_signals)
    print(f"[nightly_scan] New (unseen) signals: {len(new_signals)}")

    if not new_signals:
        print("[nightly_scan] Nothing new — done.")
        return

    # 3. For each signal, look up the tracker
    signals_with_tracker = []
    for sig in new_signals:
        company = sig.get("company_guess")
        role = sig.get("role_guess")
        tr = lookup_tracker_role(company, role)
        signals_with_tracker.append({
            "signal": sig,
            "tracker_row": tr,
        })
        print(f"[nightly_scan] {company!r} / {role!r} -> tracker={'FOUND' if tr else 'NONE'}")

    # 4. Notify Cyrus
    notify_cyrus(signals_with_tracker)

    # 5. Insert into interviews table + re-render XLSX
    inserted = process_signals(signals_with_tracker)
    print(f"[nightly_scan] Done. Notified={len(signals_with_tracker)}, Tracker inserts={inserted}.")


if __name__ == "__main__":
    run()
