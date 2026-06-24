"""
dedup_store.py -- Simple JSON-based dedup store to avoid re-notifying for the same signal.
Keyed by (source, subject_hash, company_guess).
"""

import json
import hashlib
import os
import re
from pathlib import Path

STORE_PATH = Path(__file__).parent / "seen_signals.json"


def _signal_key(signal):
    subject = signal.get("subject", "") or ""
    source = signal.get("source", "")
    # Canonicalize company so "Datadoghq"/"Datadog" dedup together.
    try:
        from classifier import canonical_company
        company = canonical_company(signal.get("company_guess"), subject,
                                    signal.get("sender", "")) or ""
    except Exception:
        company = signal.get("company_guess") or ""
    # Normalize subject: strip Re:/Fwd: prefixes + collapse whitespace so reply
    # chains and trivial variants don't re-notify.
    norm = re.sub(r"^(?:re|fwd|fw)\s*:\s*", "", subject.strip(), flags=re.I)
    norm = re.sub(r"\s+", " ", norm).lower()[:120]
    raw = f"{source}::{company}::{norm}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_seen():
    if STORE_PATH.exists():
        try:
            return json.loads(STORE_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_seen(seen):
    STORE_PATH.write_text(json.dumps(seen, indent=2))


def filter_new_signals(signals):
    """Return only signals not seen before, and update the store."""
    seen = load_seen()
    new_signals = []
    for sig in signals:
        key = _signal_key(sig)
        if key not in seen:
            new_signals.append(sig)
            seen[key] = sig.get("date", "unknown")
    save_seen(seen)
    return new_signals
