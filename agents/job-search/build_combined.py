#!/usr/bin/env python3
"""Read inline-plan-<slug>.json and emit a single combined JS payload
that does: open-apply -> wait -> fill text -> dropdowns -> phone iti
       -> decline demographics -> gdpr consent -> verify form readback.

Resume upload is still done separately because it needs CDP setInputFiles.

Outputs JSON: {"open_apply_fn": str, "fill_all_fn": str, "attach_fn": str,
               "verify_attach_fn": str, "submit_fn": str,
               "verify_confirm_fn": str,
               "url": str, "pdf_path": str, "filename": str, "slug": str}
"""
import json, sys, re

slug = sys.argv[1]
path = f"role-discovery/output/inline-plan-{slug}.json"
plan = json.load(open(path))

# Extract steps
steps_by_comment = {}
for s in plan['steps']:
    args = s.get('args', {})
    c = args.get('comment', '')
    steps_by_comment[c] = s

def get_fn(comment_substr):
    for c, s in steps_by_comment.items():
        if comment_substr in c:
            return s['args'].get('fn'), s['args'].get('arg')
    return None, None

fill_text_fn, fill_text_arg = get_fn("Fill every text/textarea")
dropdown_fn, dropdown_arg = get_fn("Open each react-select")
phone_fn, phone_arg = get_fn("Phone iti")
decline_fn, decline_arg = get_fn("unset gender/race/ethnicity")
if decline_fn is None:
    decline_fn, decline_arg = get_fn("Decline to self-identify")
gdpr_fn, _ = get_fn("GDPR demographic-data")
attach_fn, attach_arg = get_fn("Click Attach to wake Filestack")
verify_attach_fn, verify_attach_arg = get_fn("Verify the resume actually landed")
verify_fn, _ = get_fn("Read back current state")

# Build combined fill_all_fn that runs text/dropdowns/phone/decline/gdpr sequentially.
combined = f"""
async () => {{
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  await sleep(700);
  const results = {{}};
  // text fields
  try {{
    const fillText = {fill_text_fn};
    results.text = await fillText({json.dumps(fill_text_arg)});
  }} catch (e) {{ results.text_err = String(e); }}
  // dropdowns
  try {{
    const pickDropdowns = {dropdown_fn};
    results.dropdowns = await pickDropdowns({json.dumps(dropdown_arg)});
  }} catch (e) {{ results.dropdowns_err = String(e); }}
  // phone
  try {{
    const fillPhone = {phone_fn};
    results.phone = await fillPhone({json.dumps(phone_arg)});
  }} catch (e) {{ results.phone_err = String(e); }}
  // decline demographics
  try {{
    const decline = {decline_fn};
    results.decline = await decline({json.dumps(decline_arg)});
  }} catch (e) {{ results.decline_err = String(e); }}
  // gdpr
  try {{
    const gdpr = {gdpr_fn};
    results.gdpr = await gdpr();
  }} catch (e) {{ results.gdpr_err = String(e); }}
  return results;
}}
"""

attach_wrapped = f"""
async () => {{
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  await sleep(300);
  const attach = {attach_fn};
  const a = await attach({json.dumps(attach_arg)});
  await sleep(500);
  const verify = {verify_attach_fn};
  const v = await verify({json.dumps(verify_attach_arg)});
  return {{ attach: a, verify: v }};
}}
"""

# Submit fn: bail if visible captcha; otherwise click Submit-like button.
submit_fn = """
async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  // detect visible captcha iframes
  const iframes = [...document.querySelectorAll('iframe')];
  for (const f of iframes) {
    const src = (f.src || '').toLowerCase();
    if (/hcaptcha|recaptcha\\/api2\\/bframe/.test(src)) {
      const r = f.getBoundingClientRect();
      if (r.width > 50 && r.height > 50 && f.offsetParent !== null) {
        return { ok: false, captcha: src };
      }
    }
  }
  // Find Submit button
  const btns = [...document.querySelectorAll('button, input[type=submit]')];
  const submit = btns.find(b => /submit(\\s+application)?/i.test((b.textContent || b.value || '').trim()));
  if (!submit) return { ok: false, err: 'no submit button' };
  submit.scrollIntoView({ block: 'center' });
  await sleep(200);
  submit.click();
  return { ok: true, clicked: (submit.textContent || submit.value || '').trim().slice(0, 40) };
}
"""

verify_confirm_fn = """
() => {
  const url = location.href;
  const body = (document.body && document.body.innerText) || '';
  const confirmed = /thank|confirmation|received your application|application\\s+(was\\s+)?submitted|your application has been/i.test(body) || /confirmation/i.test(url);
  return {
    confirmed,
    url,
    snippet: body.slice(0, 600),
  };
}
"""

out = {
    "slug": slug,
    "url": plan['url'],
    "pdf_path_staged": plan['pdf_path_staged'],
    "filename": plan['pdf_path_staged'].split('/')[-1],
    "open_apply_fn": "() => { const b = [...document.querySelectorAll('button,a')].find(x => /^apply$/i.test((x.textContent || '').trim())); if (b) b.click(); return b ? 'clicked' : 'noop'; }",
    "fill_all_fn": combined,
    "attach_fn": attach_wrapped,
    "submit_fn": submit_fn,
    "verify_confirm_fn": verify_confirm_fn,
    "verify_state_fn": verify_fn,
    "cover_overrides": plan.get('cover_overrides') or [],
    "cover_answers_path": f"applications/queued/{slug}/cover_answers.md",
}

print(json.dumps(out))
