#!/usr/bin/env python3
"""Adapter smoke test (v2: machine-readable + baseline diff).

Hits one known-good company per adapter and verifies:
  - adapter returns >0 roles
  - each role has company / title / url populated
  - for adapters that should expose posted_at, at least one role does

Outputs:
  - stdout: human-readable summary (with newly-broken vs still-broken split)
  - role-discovery/_smoke-results.json: machine-readable current run
  - role-discovery/_smoke-baseline.json: last-known-good per adapter (updated
    only when the current run's status for that adapter is "ok"; Microsoft is
    a special case — see MICROSOFT_EXPECTED_FAIL below).

Exits:
  0 if no newly-broken adapters (still-broken Microsoft = fine)
  1 if one or more adapters newly broke since the last green run

Run weekly (out-of-band from `weekly_run.sh`) to catch adapter rot.
"""
from __future__ import annotations
import dataclasses
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from adapters import apple, ashby, greenhouse, lever, microsoft, smartrecruiters, workday  # noqa
# google + meta are scan-blocked / different shape; we don't smoke-test them.

RESULTS_PATH = HERE / "_smoke-results.json"
BASELINE_PATH = HERE / "_smoke-baseline.json"

# Microsoft has been permanently scan-blocked (anti-bot) for months. We keep
# probing so we know if it ever comes back, but its baseline is locked to
# "fail-expected" and a failing current run for microsoft is NEVER classified
# as "newly broken".
MICROSOFT_EXPECTED_FAIL = True

# Each probe: (label, callable -> list[Role], require_posted_at)
PROBES = [
    ("apple",          lambda: apple.fetch(), True),
    ("greenhouse",     lambda: greenhouse.fetch("Anthropic", "anthropic"), True),
    ("ashby",          lambda: ashby.fetch("OpenAI", "openai"), True),
    ("lever",          lambda: lever.fetch("Spotify", "spotify"), False),
    ("smartrecruiters",lambda: smartrecruiters.fetch("Visa", "Visa"), False),
    ("microsoft",      lambda: microsoft.fetch(), True),
    ("workday",        lambda: workday.fetch("Salesforce", "salesforce",
                                              host="salesforce.wd12.myworkdayjobs.com",
                                              tenant="salesforce",
                                              site="External_Career_Site"), False),
]

OK = "ok"
FAIL = "fail"


def _role_to_sample(r) -> dict | None:
    """Best-effort serialize a Role-like object to a compact sample dict."""
    if r is None:
        return None
    if dataclasses.is_dataclass(r):
        try:
            d = dataclasses.asdict(r)
        except Exception:
            d = {}
    elif hasattr(r, "to_dict") and callable(r.to_dict):
        try:
            d = r.to_dict()
        except Exception:
            d = {}
    else:
        d = {k: getattr(r, k, None) for k in ("company", "title", "url", "location", "posted_at", "exp_required")}
    # keep keys we care about, strip None
    keep = ("company", "title", "url", "location", "posted_at", "exp_required")
    out = {k: d.get(k) for k in keep if k in d}
    return out


def run_one(label, fn, require_posted_at) -> dict:
    t0 = time.time()
    try:
        roles = fn() or []
    except Exception as e:
        return dict(
            status=FAIL,
            role_count=0,
            error=f"{type(e).__name__}: {e}",
            sample_role=None,
            duration_ms=int((time.time() - t0) * 1000),
            traceback=traceback.format_exc(limit=4),
        )
    elapsed = int((time.time() - t0) * 1000)
    if not roles:
        return dict(status=FAIL, role_count=0,
                    error="0 roles returned (endpoint may have changed)",
                    sample_role=None, duration_ms=elapsed)
    bad = []
    for r in roles[:5]:
        if not (getattr(r, "company", "") and getattr(r, "title", "") and getattr(r, "url", "")):
            bad.append(repr(r)[:120])
    if bad:
        return dict(status=FAIL, role_count=len(roles),
                    error=f"missing company/title/url on {len(bad)} sample row(s): {bad[0]}",
                    sample_role=_role_to_sample(roles[0]), duration_ms=elapsed)
    if require_posted_at:
        have_date = sum(1 for r in roles if getattr(r, "posted_at", ""))
        if have_date == 0:
            return dict(status=FAIL, role_count=len(roles),
                        error=f"posted_at empty on ALL {len(roles)} roles (date extraction broke)",
                        sample_role=_role_to_sample(roles[0]), duration_ms=elapsed)
    return dict(status=OK, role_count=len(roles), error=None,
                sample_role=_role_to_sample(roles[0]), duration_ms=elapsed)


def _load_baseline() -> dict:
    if BASELINE_PATH.exists():
        try:
            return json.loads(BASELINE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, default=str))


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"=== adapter smoke test ({now}) ===\n")

    baseline = _load_baseline()
    baseline_adapters = baseline.get("adapters", {}) if isinstance(baseline, dict) else {}

    current = {"ts": now, "adapters": {}}

    for label, fn, req_date in PROBES:
        print(f"[{label}] probing...", flush=True)
        res = run_one(label, fn, req_date)
        current["adapters"][label] = res
        marker = "✓" if res["status"] == OK else "✗"
        err = res.get("error") or ""
        print(f"  {marker} {res['status']:4} n={res['role_count']:>4}  {res['duration_ms']:>5}ms  {err}", flush=True)

    # Classify newly-broken vs still-broken
    newly_broken: list[str] = []
    still_broken: list[str] = []
    recovered: list[str] = []
    for label, res in current["adapters"].items():
        prev = baseline_adapters.get(label, {})
        prev_status = prev.get("status")
        if res["status"] == FAIL:
            if label == "microsoft" and MICROSOFT_EXPECTED_FAIL:
                still_broken.append(label)
                continue
            if prev_status == OK:
                newly_broken.append(label)
            else:
                still_broken.append(label)
        else:
            if prev_status and prev_status != OK and label != "microsoft":
                recovered.append(label)

    # Update baseline: overwrite an adapter entry only if current run is OK.
    # Also seed: if no baseline exists for an adapter at all, take the current
    # snapshot regardless of status (otherwise first run could never compute
    # "newly broken" — which is the desired conservative behavior, so we only
    # seed on OK, leaving permanently-broken adapters as "no baseline yet" =
    # still-broken).
    new_baseline_adapters = dict(baseline_adapters)
    for label, res in current["adapters"].items():
        if res["status"] == OK:
            new_baseline_adapters[label] = {
                "status": OK,
                "role_count": res["role_count"],
                "sample_role": res["sample_role"],
                "last_ok_ts": now,
            }
    # Pin microsoft baseline.
    if MICROSOFT_EXPECTED_FAIL:
        new_baseline_adapters["microsoft"] = {
            "status": "fail-expected",
            "role_count": 0,
            "sample_role": None,
            "note": "permanently scan-blocked; failures are expected and not 'newly broken'",
        }

    new_baseline = {"updated_ts": now, "adapters": new_baseline_adapters}

    _save_json(RESULTS_PATH, current)
    _save_json(BASELINE_PATH, new_baseline)

    total = len(current["adapters"])
    n_ok = sum(1 for r in current["adapters"].values() if r["status"] == OK)
    print()
    print(f"=== SUMMARY: {n_ok}/{total} pass ===")
    for label, res in current["adapters"].items():
        marker = "✓" if res["status"] == OK else "✗"
        suffix = ""
        if label in newly_broken:
            suffix = "  [NEWLY BROKEN]"
        elif label in still_broken:
            suffix = "  [still-broken]"
        elif label in recovered:
            suffix = "  [recovered]"
        err = res.get("error") or ""
        print(f"  {marker} {label:18} n={res['role_count']:>4}  {err}{suffix}")

    if newly_broken:
        print()
        print("NEWLY BROKEN — auto-repair loop should fire:")
        for label in newly_broken:
            res = current["adapters"][label]
            print(f"  - {label}: {res.get('error')}")
    if still_broken:
        print()
        print("Still-broken (no action — baseline already FAIL or expected):")
        for label in still_broken:
            print(f"  - {label}")
    if recovered:
        print()
        print("Recovered since last run:")
        for label in recovered:
            print(f"  - {label}")

    print(f"\nWrote: {RESULTS_PATH}")
    print(f"Wrote: {BASELINE_PATH}")

    # Return value also available to programmatic callers
    summary = {
        "ts": now,
        "total": total,
        "ok": n_ok,
        "newly_broken": newly_broken,
        "still_broken": still_broken,
        "recovered": recovered,
    }
    if newly_broken:
        sys.exit(1)
    sys.exit(0)
    return summary  # unreachable; kept for clarity if imported


if __name__ == "__main__":
    main()
