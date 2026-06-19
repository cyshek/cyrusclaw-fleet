"""
notifier.py -- Send interview detection notifications to Cyrus via Discord
"""

import subprocess
import json
import os

DISCORD_CHANNEL_ID = "1513393827904360558"  # #interview-agent channel


def notify_cyrus(signals_with_tracker):
    """
    signals_with_tracker: list of dicts, each with:
      - signal: the raw email/calendar signal
      - tracker_row: the matched tracker row (or None)
    """
    if not signals_with_tracker:
        return

    lines = [f"🔔 **Interview signals detected** — {len(signals_with_tracker)} new:\n"]

    for item in signals_with_tracker:
        sig = item["signal"]
        tr = item.get("tracker_row")

        company = sig.get("company_guess") or "Unknown company"
        role = sig.get("role_guess") or (tr.get("role") if tr else None) or "Unknown role"
        source = sig.get("source", "email")
        subject = sig.get("subject", "")
        date = sig.get("date", "")

        lines.append(f"**{company}** — {role}")
        lines.append(f"  Source: {source} | `{subject[:80]}`")
        if date:
            lines.append(f"  Date: {date}")

        if tr:
            ambiguous = tr.get("_ambiguous", False)
            prep_path = tr.get("prep_path") or ""
            jd_url = tr.get("jd_url") or ""
            matched_role = tr.get("role", "")

            if ambiguous:
                all_matches = tr.get("_all_matches", [])
                lines.append(f"  ⚠️ Ambiguous: {len(all_matches)} roles on file for {company}:")
                for m in all_matches[:3]:
                    lines.append(f"    - {m['role']} (applied {m['applied_on']})")
                lines.append(f"  Using most recent: **{matched_role}**")
            else:
                lines.append(f"  ✅ Tracker match: **{matched_role}**")

            if prep_path:
                lines.append(f"  Resume folder: `{prep_path}`")
            if jd_url:
                lines.append(f"  JD: {jd_url}")
        else:
            lines.append(f"  ❌ No tracker match found — will use master resume")

        lines.append("")  # blank line between signals

    lines.append("Reply with **`build [company]`** to trigger a full bundle, or I'll build all automatically in 30 min if you don't respond.")

    message = "\n".join(lines)
    print(f"[notifier] Sending notification ({len(message)} chars)")
    print(message)

    # Use openclaw CLI to send to the channel
    result = subprocess.run(
        ["openclaw", "message", "send",
         "--channel", "discord",
         "-t", f"channel:{DISCORD_CHANNEL_ID}",
         "-m", message],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"[notifier] CLI send failed: {result.stderr}")
    else:
        print("[notifier] Notification sent OK")


if __name__ == "__main__":
    # Test notification
    test_signals = [{
        "signal": {
            "source": "email",
            "subject": "Interview with Acme Corp for TPM role",
            "sender": "recruiter@acme.com",
            "date": "Sun, 14 Jun 2026 10:00:00 -0700",
            "company_guess": "Acme",
            "role_guess": "Technical Program Manager",
            "snippet": "Hi Cyrus, we'd love to schedule an interview...",
        },
        "tracker_row": None,
    }]
    notify_cyrus(test_signals)
