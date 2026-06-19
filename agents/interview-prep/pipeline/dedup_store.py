"""
dedup_store.py -- Simple JSON-based dedup store to avoid re-notifying for the same signal.
Keyed by (source, subject_hash, company_guess).
"""

import json
import hashlib
import os
from pathlib import Path

STORE_PATH = Path(__file__).parent / "seen_signals.json"


def _signal_key(signal):
    subject = signal.get("subject", "")
    company = signal.get("company_guess") or ""
    source = signal.get("source", "")
    raw = f"{source}::{company}::{subject}"
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
