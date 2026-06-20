#!/usr/bin/env python3
"""Shared debug-screenshot lifecycle: capture step shots during a run, then PRUNE
them on clean success while ALWAYS preserving confirmation/proof shots.

Pattern (Cyrus 2026-06-02): take debug screenshots during the run so a stuck/failed
runner is fully diagnosable, but on a clean success delete the step-N clutter — keep
only the submit-evidence (confirmation) shot. Best of both: full trail exactly when
something breaks, zero accumulation when everything works. (Was: 1299 PNGs / 187MB of
write-only step shots that nobody ever read after the run.)

Usage in a runner:
    from debug_shots import prune_step_shots_on_success
    ...
    rc = run(args)
    prune_step_shots_on_success(debug_dir, tenant_or_slug, rc, success_codes=(0,))

KEEP rules (never deleted):
  - any filename containing 'confirmation' (the proof-of-submit shot)
  - any filename containing 'proof' or 'submit' (evidence trail)
On NON-success rc: nothing is deleted (full debug trail retained for diagnosis).
"""
import os
import glob

# substrings that mark a screenshot as EVIDENCE — never pruned even on success
_KEEP_SUBSTR = ("confirmation", "proof", "submit")


def _is_evidence(path: str) -> bool:
    name = os.path.basename(path).lower()
    return any(s in name for s in _KEEP_SUBSTR)


def prune_step_shots_on_success(debug_dir, prefix, rc, success_codes=(0,), patterns=None):
    """If rc is a success code, delete step/debug PNGs in `debug_dir`, preserving any
    evidence (confirmation/proof/submit) shot. NEVER raises.

    Matching: pass explicit `patterns` (list of glob patterns relative to debug_dir)
    for runners whose shots aren't `<prefix>-*.png`. If `patterns` is omitted, derive
    from `prefix`: "<prefix>-*.png" when prefix is truthy, else all "*.png" in the dir.

    Returns (deleted_count, kept_count). On non-success rc returns (0, kept) and
    deletes nothing.
    """
    try:
        if not debug_dir or not os.path.isdir(debug_dir):
            return (0, 0)
        if patterns:
            pats = [os.path.join(debug_dir, p) for p in patterns]
        elif prefix:
            pats = [os.path.join(debug_dir, f"{prefix}-*.png")]
        else:
            pats = [os.path.join(debug_dir, "*.png")]
        shots = []
        for p in pats:
            shots.extend(glob.glob(p))
        shots = sorted(set(shots))
        if rc not in success_codes:
            # keep everything for diagnosis
            return (0, len(shots))
        deleted = kept = 0
        for s in shots:
            if _is_evidence(s):
                kept += 1
                continue
            try:
                os.remove(s)
                deleted += 1
            except Exception:
                pass
        if deleted:
            print(f"[debug_shots] success (rc={rc}) -> pruned {deleted} step shot(s), kept {kept} evidence shot(s)")
        return (deleted, kept)
    except Exception as e:
        print(f"[debug_shots] prune skipped (non-fatal): {e}")
        return (0, 0)
