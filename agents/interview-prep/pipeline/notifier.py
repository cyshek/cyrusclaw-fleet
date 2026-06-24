"""
notifier.py -- Send interview detection notifications to Cyrus via Discord.
Collapses signals BY COMPANY so Cyrus hears about each company ONCE (not once per
email). Within a company, the strongest/most-recent signal is shown.
"""

import subprocess
import json
import os

DISCORD_CHANNEL_ID = "1513393827904360558"  # #interview-prep channel


def _company_of(item):
    sig = item["signal"]
    try:
        from classifier import canonical_company
        return (canonical_company(sig.get("company_guess"),
                                  sig.get("subject", ""),
                                  sig.get("sender", "")) or "Unknown company")
    except Exception:
        return sig.get("company_guess") or "Unknown company"


def _signal_strength(sig):
    """Score a signal so the strongest one represents the company."""
    try:
        from classifier import classify
        _i, score, _l, _r = classify(sig.get("subject", ""), sig.get("sender", ""),
                                     sig.get("snippet", ""))
        return score
    except Exception:
        return 0


def notify_cyrus(signals_with_tracker):
    """
    signals_with_tracker: list of {signal, tracker_row}.
    Groups by canonical company; emits one block per company.
    """
    if not signals_with_tracker:
        return

    # Group by company.
    groups = {}
    for item in signals_with_tracker:
        co = _company_of(item)
        groups.setdefault(co, []).append(item)

    n_companies = len(groups)
    n_emails = len(signals_with_tracker)
    header = (f"🔔 **Interview activity** — {n_companies} "
              f"{'company' if n_companies == 1 else 'companies'}"
              f" ({n_emails} new email{'s' if n_emails != 1 else ''}):\n")
    lines = [header]

    # Sort companies by their strongest signal's recency (latest first).
    def _group_sort_key(kv):
        items = kv[1]
        latest = max((it["signal"].get("date", "") for it in items), default="")
        return latest
    for company, items in sorted(groups.items(), key=_group_sort_key, reverse=True):
        # Pick the strongest signal to headline the company.
        best = max(items, key=lambda it: _signal_strength(it["signal"]))
        sig = best["signal"]
        tr = best.get("tracker_row")

        role = sig.get("role_guess") or (tr.get("role") if tr else None) or "role TBD"
        subject = sig.get("subject", "")
        date = sig.get("date", "")[:10]
        n = len(items)
        more = f"  (+{n-1} more email{'s' if n-1 != 1 else ''})" if n > 1 else ""

        lines.append(f"**{company}** — {role}{more}")
        lines.append(f"  ↗️ `{subject[:80]}`" + (f" · {date}" if date else ""))

        if tr:
            matched_role = tr.get("role", "")
            jd_url = tr.get("jd_url") or ""
            prep_path = tr.get("prep_path") or ""
            if tr.get("_ambiguous"):
                n_roles = len(tr.get('_all_matches', []))
                # Only trust the guessed role if the email actually hinted a role;
                # otherwise say it's ambiguous rather than asserting a wrong one.
                if sig.get("role_guess"):
                    lines.append(f"  ⚠️ {n_roles} roles on file — best guess **{matched_role}** (confirm)")
                else:
                    lines.append(f"  ⚠️ {n_roles} roles on file for this company — tell me which when you build")
            else:
                lines.append(f"  ✅ Tracker: **{matched_role}**")
            if prep_path:
                lines.append(f"  📁 `{prep_path}`")
            if jd_url and not tr.get("_ambiguous"):
                lines.append(f"  JD: {jd_url}")
        else:
            lines.append("  ❌ no tracker match — master resume")
        lines.append("")

    lines.append("Reply **`build [company]`** to trigger a bundle.")

    message = "\n".join(lines)
    print(f"[notifier] Sending notification ({len(message)} chars, {n_companies} companies)")
    print(message)

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
