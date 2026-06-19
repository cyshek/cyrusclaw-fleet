#!/usr/bin/env python3
"""
_apple_jd_fetch.py — Fetch Apple jobs.apple.com JD text from a RENDERED page.

Apple's JD is JS-rendered: a plain curl/requests fetch returns ONLY EEO
boilerplate (~1700 chars, no Description / Minimum Qualifications). Apple's
JSON API (jobs.apple.com/api/role/detail/<reqid>) rejects tokenless requests.
So the JD MUST be grabbed from a rendered browser page.

This script attaches to the already-running OpenClaw-managed browser over CDP
(default http://127.0.0.1:18800; override via JOBSEARCH_CDP), navigates to the
Apple role URL, waits for the JD container to render, and emits a JD markdown
body to stdout (or to --out <path>).

Apple JD page DOM (stable ids, verified 2026-06-08):
  #jd-job-summary               -> Summary block (incl. Posted / Role Number)
  #jd-description               -> Description
  #jd-key-qualifications        -> Key Qualifications (when present)
  #jd-minimum-qualifications    -> Minimum Qualifications
  #jd-preferred-qualifications  -> Preferred Qualifications
  #jd-education-experience      -> Education & Experience (when present)
  #jd-additional-requirements   -> Additional Requirements (when present)

Apply/SSO is Apple-ID gated (2FA) and NOT IP-walled for JD pages, so no
residential proxy is needed — the standard openclaw browser reaches these
pages fine.

Usage:
  _apple_jd_fetch.py <apple_role_url> [--out <path>] [--cdp <url>] \
      [--timeout-ms 45000] [--settle-ms 3500]

Exit codes:
  0 = JD body written (non-trivial: has a Description or Minimum Qualifications,
      body length over the EEO-boilerplate floor)
  2 = page loaded but JD looked empty / boilerplate-only (treat as fetch-fail)
  3 = could not attach to CDP / navigation failed
  4 = bad usage
"""
from __future__ import annotations

import argparse
import os
import sys

# EEO-only pages render ~1700 chars; a real JD renders ~6k-12k. Require the
# rendered body to clear a floor AND contain a substantive JD section.
_BOILERPLATE_BODY_FLOOR = 2500

_SECTION_SPECS = [
    # (heading, list-of-candidate-selectors)
    ("Summary", ["#jd-job-summary"]),
    ("Description", ["#jd-description"]),
    ("Key Qualifications", ["#jd-key-qualifications"]),
    ("Minimum Qualifications", ["#jd-minimum-qualifications"]),
    ("Preferred Qualifications", ["#jd-preferred-qualifications"]),
    ("Education & Experience", ["#jd-education-experience"]),
    ("Additional Requirements", ["#jd-additional-requirements"]),
]

# JS evaluated in-page: returns a dict of section text + metadata. Kept as a
# single expression so it works through page.evaluate and the browser tool's
# evaluate kind alike.
_EXTRACT_JS = r"""
() => {
  const grab = (sel) => { const el = document.querySelector(sel); return el ? el.innerText.trim() : null; };
  const out = {};
  out.title = (document.querySelector('h1') && document.querySelector('h1').innerText.trim()) || document.title;
  out.summary = grab('#jd-job-summary');
  out.description = grab('#jd-description');
  out.keyQuals = grab('#jd-key-qualifications');
  out.minQuals = grab('#jd-minimum-qualifications');
  out.prefQuals = grab('#jd-preferred-qualifications');
  out.eduExp = grab('#jd-education-experience');
  out.addReq = grab('#jd-additional-requirements');
  out.bodyLen = document.body ? document.body.innerText.length : 0;
  return out;
}
"""

_FIELD_BY_HEADING = {
    "Summary": "summary",
    "Description": "description",
    "Key Qualifications": "keyQuals",
    "Minimum Qualifications": "minQuals",
    "Preferred Qualifications": "prefQuals",
    "Education & Experience": "eduExp",
    "Additional Requirements": "addReq",
}


def _strip_summary_meta(summary: str) -> str:
    """Drop the leading 'Summary / Posted: .. / Role Number: ..' scaffold lines
    so the JD body reads cleanly; keep the prose."""
    if not summary:
        return ""
    lines = summary.splitlines()
    cleaned = []
    skip_next = False
    for ln in lines:
        s = ln.strip()
        if skip_next:
            skip_next = False
            continue
        if s.lower() in ("summary",):
            continue
        if s.lower() in ("posted:", "role number:"):
            # value is on the following line — skip both
            skip_next = True
            continue
        cleaned.append(ln)
    return "\n".join(cleaned).strip()


def build_jd_markdown(data: dict) -> tuple[str, bool, dict]:
    """Return (jd_markdown, is_substantive, meta).

    is_substantive = body cleared the boilerplate floor AND a Description or
    Minimum Qualifications block is present.
    """
    parts: list[str] = []
    meta = {"title": data.get("title") or "", "bodyLen": int(data.get("bodyLen") or 0)}
    summary = _strip_summary_meta(data.get("summary") or "")
    if summary:
        parts.append("## Summary\n\n" + summary)
    for heading, field in (
        ("Description", "description"),
        ("Key Qualifications", "keyQuals"),
        ("Minimum Qualifications", "minQuals"),
        ("Preferred Qualifications", "prefQuals"),
        ("Education & Experience", "eduExp"),
        ("Additional Requirements", "addReq"),
    ):
        val = (data.get(field) or "").strip()
        if val:
            # The block text already starts with its own heading line (e.g.
            # "Description\n..."); normalize to a markdown header.
            first_nl = val.find("\n")
            if first_nl != -1 and val[:first_nl].strip().lower() == heading.lower():
                val = val[first_nl + 1 :].strip()
            parts.append(f"## {heading}\n\n{val}")
    jd_md = "\n\n".join(parts).strip()
    has_core = bool((data.get("description") or "").strip()) or bool(
        (data.get("minQuals") or "").strip()
    )
    is_substantive = has_core and meta["bodyLen"] >= _BOILERPLATE_BODY_FLOOR and len(jd_md) >= 300
    return jd_md, is_substantive, meta


def fetch_via_cdp(url: str, cdp: str, timeout_ms: int, settle_ms: int) -> dict:
    """Attach to the running browser over CDP and extract JD section data."""
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    try:
        br = pw.chromium.connect_over_cdp(cdp)
        ctx = br.contexts[0] if br.contexts else br.new_context()
        pg = ctx.new_page()
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # JD container hydrates after DOMContentLoaded; wait for a core
            # section or fall back to a fixed settle.
            try:
                pg.wait_for_selector(
                    "#jd-description, #jd-minimum-qualifications",
                    timeout=min(timeout_ms, 20000),
                )
            except Exception:
                pass
            pg.wait_for_timeout(settle_ms)
            data = pg.evaluate(_EXTRACT_JS)
            return data
        finally:
            try:
                pg.close()
            except Exception:
                pass
    finally:
        try:
            pw.stop()
        except Exception:
            pass


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Fetch Apple JD from a rendered page over CDP.")
    ap.add_argument("url", help="Apple role URL (jobs.apple.com/en-us/details/<reqid>/<slug>)")
    ap.add_argument("--out", default=None, help="Write JD markdown to this path (else stdout).")
    ap.add_argument("--cdp", default=os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800"))
    ap.add_argument("--timeout-ms", type=int, default=45000)
    ap.add_argument("--settle-ms", type=int, default=3500)
    ap.add_argument("--meta-out", default=None, help="Optional path to dump extracted-section JSON.")
    args = ap.parse_args(argv)

    if "jobs.apple.com" not in (args.url or ""):
        print("ERROR: not an Apple URL", file=sys.stderr)
        return 4

    try:
        data = fetch_via_cdp(args.url, args.cdp, args.timeout_ms, args.settle_ms)
    except Exception as e:  # noqa: BLE001
        print(f"CDP_FETCH_FAIL: {type(e).__name__}: {e}", file=sys.stderr)
        return 3

    jd_md, substantive, meta = build_jd_markdown(data)

    if args.meta_out:
        import json

        try:
            with open(args.meta_out, "w") as fh:
                json.dump({"meta": meta, "raw": data, "substantive": substantive}, fh, indent=2)
        except Exception as e:  # noqa: BLE001
            print(f"WARN: meta-out write failed: {e}", file=sys.stderr)

    if not substantive:
        print(
            f"NON_SUBSTANTIVE_JD: bodyLen={meta['bodyLen']} jd_md_len={len(jd_md)} "
            f"(EEO/boilerplate-only or unrendered)",
            file=sys.stderr,
        )
        # Still emit whatever we got (caller decides), but signal via exit code.
        if args.out:
            with open(args.out, "w") as fh:
                fh.write(jd_md + ("\n" if jd_md else ""))
        else:
            sys.stdout.write(jd_md)
        return 2

    if args.out:
        with open(args.out, "w") as fh:
            fh.write(jd_md + "\n")
        print(f"OK: wrote {len(jd_md)} chars JD to {args.out} (bodyLen={meta['bodyLen']})", file=sys.stderr)
    else:
        sys.stdout.write(jd_md + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
