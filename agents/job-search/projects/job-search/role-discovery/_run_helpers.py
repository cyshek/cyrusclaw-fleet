#!/usr/bin/env python3
"""Per-app helpers for the agent-driven submit batch (2026-05-08).

Run as e.g.:
  .venv/bin/python _run_helpers.py plan apolloio 5740169004 [--override key=val]
  .venv/bin/python _run_helpers.py imap [--since EPOCH] [--timeout SECS]
  .venv/bin/python _run_helpers.py log_success ORG JID JSON_PAYLOAD_FILE
  .venv/bin/python _run_helpers.py log_failure ORG JID JSON_PAYLOAD_FILE
"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from greenhouse_filler import (build_plan, JS_FILL_TEXT_FIELDS,
                                JS_CLICK_ATTACH, JS_SUBMIT, JS_VERIFY_CONFIRMATION,
                                JS_DETECT_VERIFICATION, JS_SUBMIT_VERIFICATION_CODE,
                                JS_OPEN_APPLY, JS_VERIFY,
                                log_success, log_failure, DRYRUN_DIR)

# Enhanced dropdown picker: each spec is {id, labels:[...]} OR {id, label:'...'}.
# Tries each label in order until one matches an option. Also tolerates whitespace
# differences. Used for both regular dropdowns and declined-demo dropdowns where
# the wording varies per org.
JS_PICK_DROPDOWNS_MULTI = r"""
async (specs) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const fire = (el, type, x, y) => el.dispatchEvent(new MouseEvent(type, {
    bubbles: true, cancelable: true, view: window, button: 0,
    clientX: x, clientY: y,
  }));
  const norm = s => (s || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const out = [];
  for (const spec of specs) {
    const id = spec.id;
    const labels = spec.labels || [spec.label];
    const inp = document.getElementById(id);
    if (!inp) { out.push({ id, err: 'no input' }); continue; }
    const ctrl = inp.closest('.select__control');
    if (!ctrl) { out.push({ id, err: 'no control' }); continue; }
    // Skip if already has a value matching a desired label (multi-select adds a chip).
    const sv0 = ctrl.querySelector('.select__single-value');
    const mv0 = [...ctrl.querySelectorAll('.select__multi-value__label')].map(e => norm(e.textContent));
    if (sv0 && labels.some(l => norm(sv0.textContent) === norm(l))) {
      out.push({ id, want: labels[0], got: sv0.textContent, skipped: 'already_set' });
      continue;
    }
    if (mv0.length && labels.some(l => mv0.includes(norm(l)))) {
      out.push({ id, want: labels[0], got: mv0.join(','), skipped: 'already_set_multi' });
      continue;
    }
    ctrl.scrollIntoView({ block: 'center' });
    await sleep(120);
    const r = ctrl.getBoundingClientRect();
    const cx = r.left + 5, cy = r.top + 5;
    fire(ctrl, 'mousedown', cx, cy);
    fire(ctrl, 'mouseup',   cx, cy);
    fire(ctrl, 'click',     cx, cy);
    await sleep(350);
    const opts = [...document.querySelectorAll(`[id^=react-select-${id}-option]`)];
    let target = null; let chosenLabel = null;
    for (const lbl of labels) {
      target = opts.find(o => norm(o.textContent) === norm(lbl));
      if (target) { chosenLabel = lbl; break; }
    }
    // Fuzzy fallback: substring match on first label
    if (!target && labels[0]) {
      target = opts.find(o => norm(o.textContent).includes(norm(labels[0])));
      if (target) chosenLabel = labels[0] + ' (substr)';
    }
    if (!target) {
      out.push({ id, err: 'no option', wants: labels, available: opts.map(o => o.textContent.trim()) });
      fire(document.body, 'mousedown', 0, 0);
      continue;
    }
    const tr = target.getBoundingClientRect();
    fire(target, 'mousedown', tr.left + 5, tr.top + 5);
    fire(target, 'mouseup',   tr.left + 5, tr.top + 5);
    fire(target, 'click',     tr.left + 5, tr.top + 5);
    await sleep(220);
    const sv = ctrl.querySelector('.select__single-value');
    const mv = [...ctrl.querySelectorAll('.select__multi-value__label')].map(e => e.textContent);
    out.push({ id, want: chosenLabel, got: sv ? sv.textContent : (mv.join(',') || null) });
  }
  return out;
}
"""
from gmail_imap import wait_for_verification_code

# Per-org overrides applied AFTER build_plan. Keys are field ids, values are replacements.
OVERRIDES = {
    "scaleai-4554440005": {"dropdowns_replace": {"question_8384158005": "Yes"}},
    "scaleai-4593571005": {"dropdowns_replace": {"question_8373829005": "Yes"}},
    "scaleai-4663997005": {"dropdowns_replace": {"question_8418368005": "Yes"}},
    "vercel-5979660004": {"dropdowns_replace": {
        "question_17667517004": "Acknowledge/Confirm",
        "question_17667518004": "I have reviewed and confirmed that all the information provided is accurate and complete.",
    }},
    "vercel-5872425004": {"dropdowns_replace_label_match": True},
    "arizeai-5797408004": {"dropdowns_replace": {"question_15368184004": "No"}},
}

def get_plan(org: str, jid: str):
    spec_path = DRYRUN_DIR / f"{org}-{jid}.json"
    spec = json.loads(spec_path.read_text())
    plan = build_plan(spec)
    key = f"{org}-{jid}"
    ov = OVERRIDES.get(key, {})
    if "dropdowns_replace" in ov:
        for d in plan["dropdowns"]:
            if d["id"] in ov["dropdowns_replace"]:
                d["label"] = ov["dropdowns_replace"][d["id"]]
        # If the override field wasn't already a dropdown, add it
        existing = {d["id"] for d in plan["dropdowns"]}
        for fid, lbl in ov["dropdowns_replace"].items():
            if fid not in existing:
                plan["dropdowns"].append({"id": fid, "label": lbl})
    return {"spec_path": str(spec_path), "url": plan["url"], "plan": plan, "title": spec.get("job_title", "")}


def main():
    cmd = sys.argv[1]
    if cmd == "plan":
        org, jid = sys.argv[2], sys.argv[3]
        print(json.dumps(get_plan(org, jid), indent=2))
    elif cmd == "imap":
        since = None; timeout = 180
        for a in sys.argv[2:]:
            if a.startswith("--since="): since = float(a.split("=",1)[1])
            elif a.startswith("--timeout="): timeout = int(a.split("=",1)[1])
        code = wait_for_verification_code(timeout_seconds=timeout, since_epoch=since)
        print(code)
    elif cmd == "log_success":
        org, jid, payload_file = sys.argv[2], sys.argv[3], sys.argv[4]
        payload = json.loads(Path(payload_file).read_text())
        out = log_success(org, jid, payload["url"], payload["plan"], payload["confirmation"], payload.get("screenshot"))
        # Add extras
        d = json.loads(out.read_text())
        d["verification_code_used"] = payload.get("code")
        d["verification_code_source"] = payload.get("code_source", "Gmail IMAP")
        d["confirmation_url"] = payload["confirmation"].get("url")
        d["confirmation_snippet"] = payload["confirmation"].get("snippet", "")[:600]
        out.write_text(json.dumps(d, indent=2))
        print(str(out))
    elif cmd == "log_failure":
        org, jid, payload_file = sys.argv[2], sys.argv[3], sys.argv[4]
        payload = json.loads(Path(payload_file).read_text())
        out = log_failure(org, jid, payload["url"], payload["error"], payload.get("details"), payload.get("screenshot"))
        print(str(out))
    elif cmd == "js":
        # Print named JS snippet
        names = {
            "open_apply": JS_OPEN_APPLY,
            "fill_text": JS_FILL_TEXT_FIELDS,
            "pick_drops": JS_PICK_DROPDOWNS_MULTI,
            "click_attach": JS_CLICK_ATTACH,
            "submit": JS_SUBMIT,
            "verify_conf": JS_VERIFY_CONFIRMATION,
            "detect_verif": JS_DETECT_VERIFICATION,
            "submit_code": JS_SUBMIT_VERIFICATION_CODE,
            "verify": JS_VERIFY,
        }
        print(names[sys.argv[2]])
    else:
        print("unknown cmd", cmd, file=sys.stderr); sys.exit(2)


if __name__ == "__main__":
    main()
