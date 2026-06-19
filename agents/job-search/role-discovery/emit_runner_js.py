#!/usr/bin/env python3
"""Take an inline-plan JSON and emit three JS blobs the agent can run via browser.act evaluate.

Outputs JSON: {url, pdf_staged, pre_js, post_js, verify_js, submit_js, dropdowns_review}.

- pre_js: runs steps 1..10 (everything before upload) sequentially, returns aggregated log.
- post_js: runs steps 13..14 (attach + filename verify), returns log.
- verify_js: runs step 15 (verify form), returns form state.
- submit_js: clicks the visible Submit application button. Bails if visible captcha frame present.
"""
import json
import sys
from pathlib import Path


def build_step_call(step):
    """Return a JS expression that invokes the step's fn with its arg (or no arg)."""
    args = step.get('args', {})
    fn = args.get('fn')
    if not fn:
        return None
    fn = fn.strip()
    if 'arg' in args:
        arg_json = json.dumps(args['arg'])
        return f"await (({fn}))({arg_json})"
    return f"await (({fn}))()"


SUBMIT_JS = r"""
async () => {
  // Detect visible captcha iframe / challenge.
  const captchaSel = 'iframe[src*="hcaptcha"], iframe[src*="recaptcha/api2/anchor"], iframe[src*="recaptcha/api2/bframe"], iframe[src*="cloudflare"], iframe[src*="turnstile"]';
  const captchaFrames = [...document.querySelectorAll(captchaSel)];
  const visibleCaptcha = captchaFrames.some(f => {
    const r = f.getBoundingClientRect();
    return r.width > 50 && r.height > 50 && f.offsetParent !== null;
  });
  if (visibleCaptcha) {
    return { ok: false, err: 'visible_captcha', count: captchaFrames.length };
  }
  // Find Submit button.
  const buttons = [...document.querySelectorAll('button, input[type=submit]')];
  const submit = buttons.find(b => /submit application|submit/i.test((b.textContent || b.value || '').trim()))
              || document.querySelector('button[type=submit]');
  if (!submit) return { ok: false, err: 'no_submit_button' };
  if (submit.disabled) return { ok: false, err: 'submit_disabled' };
  submit.scrollIntoView({ block: 'center' });
  submit.click();
  return { ok: true, clicked: true, label: (submit.textContent || submit.value || '').trim().slice(0, 60), url_before: location.href };
}
"""


CONFIRM_JS = r"""
() => {
  const url = location.href;
  const text = (document.body && document.body.innerText || '').slice(0, 800);
  const confirmedByUrl = /confirmation|thank[-_ ]?you|submitted|application[-_]received/i.test(url);
  const confirmedByText = /thank you|application (was )?(submitted|received)|we['']?ve received|successfully (submitted|applied)/i.test(text);
  return { url, confirmed: confirmedByUrl || confirmedByText, snippet: text.slice(0, 400) };
}
"""


def main(plan_path):
    plan = json.loads(Path(plan_path).read_text())
    steps = plan['steps']

    pre_calls = []
    for i, s in enumerate(steps):
        if s.get('tool') == 'browser.upload':
            break
        if s.get('kind') == 'sleep':
            ms = int(s['args'].get('ms', 300))
            pre_calls.append({'i': i, 'sleep': ms})
            continue
        call = build_step_call(s)
        if call is None:
            continue
        pre_calls.append({'i': i, 'call': call})

    # Post-upload steps: from upload+1 to verify (kind=evaluate)
    upload_idx = next(i for i, s in enumerate(steps) if s.get('tool') == 'browser.upload')
    post_calls = []
    verify_call = None
    for j, s in enumerate(steps[upload_idx + 1:], start=upload_idx + 1):
        if s.get('kind') == 'sleep':
            ms = int(s['args'].get('ms', 300))
            post_calls.append({'i': j, 'sleep': ms})
            continue
        call = build_step_call(s)
        if call is None:
            continue
        # The very last evaluate step is the verify (form-state read).
        # Put it in verify_js separately.
        if j == len(steps) - 1:
            verify_call = call
            continue
        post_calls.append({'i': j, 'call': call})

    def wrap(blocks, name):
        body_parts = []
        for b in blocks:
            if 'sleep' in b:
                body_parts.append(f"  await new Promise(r => setTimeout(r, {b['sleep']}));")
            else:
                body_parts.append(f"  out.push({{ step: {b['i']}, result: {b['call']} }});")
        body = "\n".join(body_parts)
        # Emit a function expression (NOT invoked); browser.act evaluate will call it.
        return f"async () => {{\n  const out = [];\n{body}\n  return out;\n}}"

    pre_js = wrap(pre_calls, 'pre')
    post_js = wrap(post_calls, 'post')
    verify_js = f"async () => {verify_call}" if verify_call else "() => ({ verify: 'skipped' })"

    out = {
        'slug': plan['slug'],
        'url': plan['url'],
        'pdf_staged': plan['pdf_path_staged'],
        'pdf_local': plan['pdf_path_local'],
        'pdf_filename': Path(plan['pdf_path_local']).name,
        'pre_js': pre_js,
        'post_js': post_js,
        'verify_js': verify_js,
        'submit_js': SUBMIT_JS.strip(),
        'confirm_js': CONFIRM_JS.strip(),
        'needs_review_dropdowns': plan.get('needs_review_dropdowns', []),
        'wrapper_url': plan.get('wrapper_url'),
    }
    print(json.dumps(out))


if __name__ == '__main__':
    main(sys.argv[1])
