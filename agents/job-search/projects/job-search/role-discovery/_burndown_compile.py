#!/usr/bin/env python3
"""Combine all browser.act.evaluate steps for a plan into a single async IIFE.

Skips browser.open / sleep / browser.upload (those must run as separate tool
calls because they need browser-tool primitives the agent must dispatch).

Emits two chunks:
  - "form_fill"  = steps 1..(before resume upload), inlined into one IIFE.
  - "after_upload" = steps after the upload+sleep, inlined into one IIFE.

That way the agent only needs to issue 3 calls per plan after navigate:
  1. evaluate(form_fill)
  2. upload + sleep
  3. evaluate(after_upload)
  4. evaluate(JS_SUBMIT) + verify

The IIFE awaits each step and returns an ordered list of results.
"""
import json, sys

def main():
    plan_path = sys.argv[1]
    d = json.load(open(plan_path))
    steps = d['steps']

    # Find the upload step index
    upload_idx = None
    for i, s in enumerate(steps):
        if s.get('tool') == 'browser.upload':
            upload_idx = i
            break

    def build_chunk(step_range, label):
        pieces = []
        pieces.append("(async () => {")
        pieces.append("  const _sleep = (ms) => new Promise(r => setTimeout(r, ms));")
        pieces.append("  const _results = [];")
        for i in step_range:
            s = steps[i]
            tool = s.get('tool')
            args = s.get('args', {})
            if tool == 'sleep':
                ms = args.get('ms', 500)
                pieces.append(f"  await _sleep({ms});")
                pieces.append(f"  _results.push({{step: {i}, kind: 'sleep', ms: {ms}}});")
            elif tool == 'browser.act.evaluate':
                fn = args['fn'].strip()
                cmt = (args.get('comment') or '').replace('*/', '* /')[:80]
                arg = args.get('arg')
                arg_js = json.dumps(arg) if arg is not None else "undefined"
                pieces.append(f"  /* step {i}: {cmt} */")
                pieces.append(f"  _results.push({{step: {i}, r: await ({fn})({arg_js})}});")
            elif tool == 'browser.open':
                # ignore; navigate is a separate step
                pass
            elif tool == 'browser.upload':
                pass
            elif tool == 'ashby.maybe_solve_recaptcha_v3':
                # FIX 5: captcha solve cannot run inside the in-browser IIFE
                # (needs Python + network round-trip to CapSolver). The chain
                # worker MUST dispatch this step separately via
                # `_burndown_step.py <plan> <idx>` which expands it into a
                # detect/solve/inject macro. Drop a marker comment so the
                # generated IIFE makes clear something was skipped here.
                pieces.append(
                    f"  /* step {i}: SKIPPED in IIFE — captcha solve must be "
                    f"run out-of-band via _burndown_step.py {i} */"
                )
                pieces.append(
                    f"  _results.push({{step: {i}, kind: 'captcha_skipped_in_iife'}});"
                )
        pieces.append("  return _results;")
        pieces.append("})()")
        return "\n".join(pieces)

    out = {
        "slug": d.get("slug"),
        "url": d.get("url"),
        "pdf_staged": d.get("pdf_path_staged"),
        "pdf_filename": d.get("pdf_path_staged", "").split("/")[-1] if d.get("pdf_path_staged") else None,
        "needs_review_dropdowns": d.get("needs_review_dropdowns", []),
    }
    if upload_idx is None:
        out["form_fill"] = build_chunk(range(1, len(steps)), "all")
        out["after_upload"] = None
    else:
        out["form_fill"] = build_chunk(range(1, upload_idx), "pre-upload")
        # after upload starts at upload_idx + 1 (the sleep is included)
        out["after_upload"] = build_chunk(range(upload_idx + 1, len(steps)), "post-upload")

    print(json.dumps(out, indent=2))

if __name__ == '__main__':
    main()
