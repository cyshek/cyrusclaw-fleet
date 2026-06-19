#!/usr/bin/env python3
"""
proof_capture.py — inline pre-submit screenshot helper.

Called by submit runners IMMEDIATELY BEFORE the real submit click. If this role
is flagged for a screenshot (every Nth submission, per outputs/proof/screenshot_queue.json)
it screenshots the filled form into the role's proof dir and marks the queue
entry done. The REAL submit proceeds normally either way.

Design:
  - This is the INLINE approach (Cyrus 2026-06-02): the screenshot is of the exact
    filled form that is about to be submitted for real — no throwaway second pass,
    no "never-submit" dummy run. The submit happens right after this returns.
  - Totally best-effort + swallow-all-errors: a screenshot failure must NEVER
    interfere with the actual submission. Any exception -> log + return False.
  - Idempotent: only captures roles still 'pending' in the queue; marks 'done'.

Usage from a runner (Playwright `page` in scope, role id known):
    from proof_capture import maybe_capture_presubmit
    maybe_capture_presubmit(page, role_id=ROLE_ID, company=COMPANY)
    # ... then the runner does its real submit click ...
"""
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
PROOF_DIR = os.path.abspath(os.path.join(PROJ, "..", "..", "outputs", "proof"))
QUEUE = os.path.join(PROOF_DIR, "screenshot_queue.json")


def _load_queue():
    try:
        return json.load(open(QUEUE))
    except Exception:
        return []


def _save_queue(q):
    try:
        tmp = QUEUE + ".tmp"
        json.dump(q, open(tmp, "w"), indent=2)
        os.replace(tmp, QUEUE)
    except Exception:
        pass


def is_flagged(role_id) -> bool:
    """True if this role is queued for a pre-submit screenshot and not yet done."""
    try:
        rid = int(role_id)
    except Exception:
        return False
    for e in _load_queue():
        if e.get("roleid") == rid and e.get("status") not in ("done", "skipped"):
            return True
    return False


def _mark(role_id, status, **extra):
    q = _load_queue()
    changed = False
    for e in q:
        if e.get("roleid") == role_id:
            e["status"] = status
            e["captured_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            e.update(extra)
            changed = True
    if changed:
        _save_queue(q)


def _roleid_from_slug(slug):
    """Plan slugs look like '<company>-<roleid>' (trailing int = role id)."""
    import re
    if not slug:
        return None
    m = re.search(r"(\d+)\s*$", str(slug))
    return int(m.group(1)) if m else None


def maybe_capture_by_slug(page, slug) -> bool:
    """Slug-keyed wrapper for runners (like _gh_submit) that carry a plan slug
    instead of an explicit role id."""
    rid = _roleid_from_slug(slug)
    if rid is None:
        return False
    return maybe_capture_presubmit(page, rid)


def maybe_capture_presubmit(page, role_id, company=None) -> bool:
    """If role_id is flagged, screenshot the current (filled) page into its proof
    dir. Returns True if a screenshot was saved. NEVER raises — the caller's
    real submit must proceed regardless.

    `page` is a Playwright Page (sync API), as used by _gh_submit / _ashby_runner.
    """
    try:
        rid = int(role_id)
    except Exception:
        return False
    if not is_flagged(rid):
        return False
    try:
        # find this role's proof dir (written by proof_archiver.py)
        entry = next((e for e in _load_queue() if e.get("roleid") == rid), None)
        dirname = entry.get("dir") if entry else None
        dest_dir = os.path.join(PROOF_DIR, dirname) if dirname else PROOF_DIR
        os.makedirs(dest_dir, exist_ok=True)
        out = os.path.join(dest_dir, "filled-form-presubmit.png")
        # full_page so the whole filled form is captured, not just viewport
        page.screenshot(path=out, full_page=True)
        if os.path.exists(out) and os.path.getsize(out) > 0:
            _mark(rid, "done", screenshot_path=out)
            print(f"[proof_capture] saved pre-submit screenshot: {out}")
            return True
        _mark(rid, "skipped", reason="screenshot empty")
        return False
    except Exception as e:
        # absolutely never block the real submit
        try:
            _mark(rid, "skipped", reason=f"capture-error: {type(e).__name__}: {e}")
        except Exception:
            pass
        print(f"[proof_capture] screenshot failed (submit continues): {e}")
        return False
