#!/usr/bin/env python3
"""ADP WFN submit for MedZed 3718 - handles the full wizard flow."""
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _adp_wfn_runner import connect, dump, log, click_text, _wait_for_step, PERSONAL

pw, br = connect()
ctx = br.contexts[0]

page = None
for p in ctx.pages:
    try:
        if 'workforcenow' in p.url or 'adp.com' in p.url:
            page = p
            break
    except Exception:
        pass

if page is None:
    page = ctx.new_page()

print('[adp] URL:', page.url)
addr = PERSONAL['address']
contact = PERSONAL['contact']
resume = str(Path(__file__).parents[1] / 'resume' / 'Cyrus_Shekari_Resume.pdf')

headings = [h.inner_text() for h in page.locator('h1,h2,h3,h4').all()]
print('[adp] Headings:', headings)
btns = [b.inner_text().strip()[:60] for b in page.locator('button').all()[:15]]
print('[adp] Buttons:', btns)

page_body = page.inner_text('body')[:500]
print('[adp] Body start:', page_body[:300])

if 'Complete Your Application' in page_body:
    btn = page.locator('button:has-text("Complete Your Application")').first
    btn.click(timeout=8000)
    page.wait_for_timeout(4000)
    print('[adp] Clicked Complete Your Application')
    print('[adp] URL after:', page.url)

page_body2 = page.inner_text('body')[:1000]
print('[adp] Body2:', page_body2[:400])

# Fill name fields if blank
for sel, val in [('#personalInfomationFirstName', contact.get('first_name', 'Cyrus')),
                 ('#personalInfomationLastName', contact.get('last_name', 'Shekari'))]:
    try:
        el = page.locator(sel).first
        current = el.input_value(timeout=2000)
        if not current.strip():
            el.fill(val, timeout=3000)
            print(f'[adp] filled {sel}={val}')
        else:
            print(f'[adp] {sel} already={current!r}')
    except Exception as e:
        print(f'[adp] name fill err {sel}: {e}')

# Country field
try:
    country_input = page.locator('#PersonalAddress_country').first
    country_input.click(timeout=5000)
    page.wait_for_timeout(800)
    country_input.press('Control+a')
    page.wait_for_timeout(200)
    country_input.type('United States', delay=50)
    page.wait_for_timeout(1500)
    result = page.evaluate("""
        () => {
            const opts = document.querySelectorAll('[role=option]');
            for (const opt of opts) {
                if (opt.textContent.includes('United States')) {
                    opt.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true}));
                    opt.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                    return 'clicked:' + opt.textContent.trim().slice(0,40);
                }
            }
            return 'no-match count=' + opts.length;
        }
    """)
    print(f'[adp] country JS: {result}')
    page.wait_for_timeout(800)
    country_val = country_input.input_value(timeout=2000)
    print(f'[adp] country value: {country_val!r}')
except Exception as e:
    print(f'[adp] country err: {e}')

# Address line 1
try:
    addr_inp = page.locator('#PersonalAddress_address_line1').first
    if addr_inp.count() > 0:
        addr_inp.click(timeout=5000)
        page.wait_for_timeout(400)
        addr_inp.fill(addr['street'], timeout=4000)
        print(f'[adp] addr_line1 filled: {addr["street"]}')
        page.wait_for_timeout(2000)
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)
except Exception as e:
    print(f'[adp] addr_line1 err: {e}')

# City, state, zip
for sel, val in [('#PersonalAddress_city', addr['city']),
                 ('#PersonalAddress_state', addr['state']),
                 ('#PersonalAddress_postalCode', addr['zip'])]:
    try:
        el = page.locator(sel).first
        if el.count() > 0:
            el.click(timeout=3000)
            el.fill(val, timeout=3000)
            print(f'[adp] filled {sel}={val}')
    except Exception as e:
        print(f'[adp] fill err {sel}: {e}')

page.wait_for_timeout(600)

# Next for PI step
if click_text(page, 'Next', 'Continue'):
    print('[adp] Clicked Next (PI step)')
    page.wait_for_timeout(3000)
    headings2 = [h.inner_text() for h in page.locator('h1,h2,h3,h4').all()]
    print('[adp] Headings after PI Next:', headings2)
    btns2 = [b.inner_text().strip()[:60] for b in page.locator('button').all()[:10]]
    print('[adp] Buttons after PI Next:', btns2)
else:
    print('[adp] Next not found')
    dump(page, 'pi-next-fail')
    sys.exit(4)

# Resume Upload
if _wait_for_step(page, r'resume|upload', timeout_s=15):
    print('[adp] On resume step')
else:
    print('[adp] Resume step not detected; proceeding')

try:
    file_inputs = page.locator('input[type=file]').all()
    uploaded = False
    for fi in file_inputs:
        try:
            fi.set_input_files(resume, timeout=10000)
            uploaded = True
            print('[adp] resume uploaded')
            break
        except Exception as fie:
            print(f'[adp] file input err: {fie}')
    if not uploaded:
        print('[adp] no file input found')
except Exception as e:
    print(f'[adp] resume upload err: {e}')

page.wait_for_timeout(2000)
dump(page, 'after-resume')

if click_text(page, 'Next', 'Continue'):
    print('[adp] Clicked Next (resume step)')
    page.wait_for_timeout(3000)
else:
    print('[adp] Resume Next not found')
    btns3 = [b.inner_text().strip()[:60] for b in page.locator('button').all()[:10]]
    print('[adp] Buttons:', btns3)

# Walk remaining wizard steps
max_steps = 10
for step_i in range(max_steps):
    page.wait_for_timeout(1500)
    heading_texts = [h.inner_text() for h in page.locator('h1,h2,h3,h4').all()]
    btns_cur = [b.inner_text().strip()[:60] for b in page.locator('button').all()[:10]]
    body_text = page.inner_text('body')[:3000]
    print(f'[adp] step {step_i}: headings={heading_texts} buttons={btns_cur}')

    combined = ' '.join(heading_texts + btns_cur).lower()

    # Check for confirmation
    if any(kw in body_text.lower() for kw in ('thank you for applying', 'application submitted',
                                                'application received', 'successfully submitted',
                                                'you have applied')):
        print('[adp] CONFIRMATION DETECTED!')
        print('[adp] Confirmation text:', body_text[:500])
        sys.exit(0)

    # Self-attest step
    if any(kw in combined for kw in ('self-attest', 'attest', 'signature', 'certify')):
        print('[adp] Self-attest step detected')
        try:
            result = page.evaluate("""
                () => {
                    if (typeof onSignatureInput === 'function') {
                        onSignatureInput('Cyrus Shekari');
                        return 'called onSignatureInput';
                    }
                    return 'onSignatureInput not found';
                }
            """)
            print(f'[adp] onSignatureInput: {result}')
        except Exception as e:
            print(f'[adp] onSignatureInput err: {e}')
        try:
            js_chk = page.evaluate("""
                () => {
                    if (typeof checkBoxStatus === 'function') {
                        checkBoxStatus(true);
                        return 'called checkBoxStatus';
                    }
                    return 'checkBoxStatus not found';
                }
            """)
            print(f'[adp] checkBoxStatus: {js_chk}')
        except Exception as e:
            print(f'[adp] checkBoxStatus err: {e}')
        try:
            chk = page.locator('input[type=checkbox]').first
            if chk.count() > 0 and not chk.is_checked():
                chk.check()
                print('[adp] checked self-attest checkbox')
        except Exception as e:
            print(f'[adp] checkbox err: {e}')
        page.wait_for_timeout(500)

    # Look for Submit button
    submit_btn = page.locator('button:has-text("Submit"), button:has-text("Submit Application")').first
    if submit_btn.count() > 0:
        print('[adp] Found Submit button!')
        submit_btn.click(timeout=8000)
        page.wait_for_timeout(5000)
        body_after = page.inner_text('body')[:2000]
        url_after = page.url
        print('[adp] Post-submit URL:', url_after)
        print('[adp] Post-submit body:', body_after[:600])
        if any(kw in body_after.lower() for kw in ('thank you', 'submitted', 'received', 'applied')):
            print('[adp] SUBMITTED confirmed!')
            sys.exit(0)
        sys.exit(3)

    # Voluntary Self-ID
    if 'voluntary' in combined or 'self-id' in combined or 'self id' in combined:
        print('[adp] Voluntary self-ID step - skipping')
        if click_text(page, 'Next', 'Continue', 'Skip'):
            print('[adp] Skipped voluntary self-ID')
            page.wait_for_timeout(2000)
            continue

    # Advance to next step
    if click_text(page, 'Next', 'Continue'):
        print(f'[adp] Clicked Next (step {step_i})')
        page.wait_for_timeout(3000)
    else:
        print(f'[adp] No Next found at step {step_i}')
        errors = page.locator('[class*=error i], [aria-invalid=true]').all()
        for err in errors[:5]:
            try:
                print(f'[adp] Error: {err.inner_text()[:100]}')
            except Exception:
                pass
        dump(page, f'stuck-step-{step_i}')
        sys.exit(5)

print('[adp] Max steps without confirmation')
sys.exit(3)
