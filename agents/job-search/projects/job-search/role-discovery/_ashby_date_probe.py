"""Standalone --no-submit DOM probe for the Ashby Date-widget runner fix.

Connects to a CLEAN anonymous Chrome (NOT the resi-profile), loads the OpenAI
2549 Ashby form, locates the Date field ("When can you start a new role?"),
drives it through _ashby_runner.commit_ashby_date_fields (the NEW date path),
then reads back the committed state and proves it stuck. STOPS before submit.

Run: .venv/bin/python _ashby_date_probe.py
"""
import os
import sys
import json
import re

sys.path.insert(0, os.path.dirname(__file__))

from playwright.sync_api import sync_playwright
import _ashby_runner as R

CDP = "http://127.0.0.1:19250"
URL = "https://jobs.ashbyhq.com/openai/1778fbc9-b9c5-4ea5-a1d3-aa7bea0be272/application"

# Probe DOM: enumerate all inputs and find the date-ish field + its container
# data-field-path. We do NOT rely on the plan here -- we discover the live id so
# the probe is self-contained and proves the runner helper against the REAL DOM.
DISCOVER_JS = r"""() => {
  const out = [];
  const inputs = [...document.querySelectorAll('input, textarea')];
  for (const e of inputs) {
    const cont = e.closest('[data-field-path]');
    const fp = cont ? cont.getAttribute('data-field-path') : null;
    // find a nearby label text
    let lbl = '';
    if (e.id) { const l = document.querySelector(`label[for="${e.id}"]`); if (l) lbl = (l.textContent||'').trim(); }
    if (!lbl && cont) { const l = cont.querySelector('label'); if (l) lbl = (l.textContent||'').trim(); }
    out.push({id: e.id || null, name: e.name || null, type: e.type || e.tagName,
              fp, label: lbl.slice(0,80), value: e.value});
  }
  return out;
}"""


def main():
    pw = sync_playwright().start()
    browser = pw.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    report = {"url": URL}
    try:
        page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(3500)
        # dismiss any cookie banner that might overlay
        try:
            page.wait_for_timeout(500)
        except Exception:
            pass
        fields = page.evaluate(DISCOVER_JS)
        report["all_fields"] = fields
        # Find the date field: label mentions 'start', or a native date input.
        date_fields = [f for f in fields
                       if (f.get("type") == "date")
                       or re.search(r"start a new role|when can you start|start date",
                                    (f.get("label") or ""), re.I)]
        report["date_candidates"] = date_fields
        if not date_fields:
            report["verdict"] = "NO_DATE_FIELD_FOUND"
            print(json.dumps(report, indent=2, default=str))
            return
        target = date_fields[0]
        # Build the plan-style fid: prefer the data-field-path (that is what the
        # plan id is for nameless inputs), else the input id.
        fid = target.get("fp") or target.get("id") or ""
        iso = "2026-06-23"  # today+14d class value (matches dryrun normalization window)
        report["target"] = target
        report["fid_used"] = fid
        report["iso_used"] = iso

        # ---- PRE: read the field's value + whether it is empty ----
        pre = page.evaluate(
            "(fp) => { const c = document.querySelector(`[data-field-path=\"${fp}\"]`);"
            " const e = c ? c.querySelector('input,textarea') : null;"
            " return e ? {value: e.value, type: e.type} : {value: null, type: null}; }",
            target.get("fp"))
        report["pre_value"] = pre

        # ---- DRIVE via the NEW runner date path ----
        date_results = R.commit_ashby_date_fields(page, [{"fid": fid, "iso": iso}])
        report["commit_ashby_date_fields"] = date_results

        page.wait_for_timeout(600)

        # ---- POST: read back el.value AND probe React commit ----
        post = page.evaluate(
            "(fp) => {\n"
            "  const c = document.querySelector(`[data-field-path=\"${fp}\"]`);\n"
            "  const e = c ? c.querySelector('input,textarea') : null;\n"
            "  if (!e) return {found:false};\n"
            "  let tracked = null;\n"
            "  try { tracked = e._valueTracker ? e._valueTracker.getValue() : null; } catch(_){}\n"
            "  return {found:true, value:e.value, type:e.type, tracked, hasValue: !!e.value};\n"
            "}",
            target.get("fp"))
        report["post_value"] = post

        # ---- PRE-SUBMIT EMPTY-REQUIRED SCAN: emulate what the form serializer
        # would flag. A required Ashby field is "empty" if it is required AND the
        # input value is blank. We check the target's container specifically.
        empty_scan = page.evaluate(
            "(fp) => {\n"
            "  const c = document.querySelector(`[data-field-path=\"${fp}\"]`);\n"
            "  if (!c) return {found:false};\n"
            "  const e = c.querySelector('input,textarea');\n"
            "  const lbl = (c.querySelector('label')||{}).textContent || '';\n"
            "  const required = !!c.querySelector('[aria-required=\"true\"]')\n"
            "    || /\\*/.test(lbl)\n"
            "    || (e && e.getAttribute('aria-required')==='true');\n"
            "  const val = e ? e.value : '';\n"
            "  return {found:true, required: !!required, value: val, empty: !val,\n"
            "          flaggedMissing: !!(required && !val)};\n"
            "}",
            target.get("fp"))
        report["empty_required_scan"] = empty_scan

        # ---- VERDICT ----
        committed = bool(date_results and date_results[0].get("committed"))
        has_val = bool(post.get("hasValue"))
        flagged = bool(empty_scan.get("flaggedMissing"))
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", iso)
        yr, mon, day = (m.group(1), m.group(2), m.group(3)) if m else ("", "", "")
        val_matches = bool(post.get("value") and yr in post["value"]
                           and mon in post["value"] and day in post["value"])
        report["verdict"] = {
            "committed_flag": committed,
            "el_value_has_date": val_matches,
            "el_value": post.get("value"),
            "still_flagged_missing": flagged,
            "PASS": bool(committed and has_val and val_matches and not flagged),
        }
        # Screenshot proof (no submit).
        shot = os.path.join(os.path.dirname(__file__), "ashby_date_probe.png")
        try:
            page.screenshot(path=shot, full_page=False)
            report["screenshot"] = shot
        except Exception as e:
            report["screenshot_err"] = str(e)

        print(json.dumps(report, indent=2, default=str))
    finally:
        try: page.wait_for_timeout(300)
        except Exception: pass
        try: page.close()
        except Exception: pass
        try: browser.close()
        except Exception: pass
        pw.stop()


if __name__ == "__main__":
    main()
