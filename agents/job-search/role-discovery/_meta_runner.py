"""
Meta Careers auto-apply runner.
Confirmed form (2026-06-17 probe, PM role 1238249364564427):
  Resume, Location checkboxes, First/Last/Current-loc, Email, Phone, Website(opt),
  Gender/Race/Veteran/Disability radios (all decline). No work-auth Qs on PM roles.
EXIT: 0=ok 2=auth 3=no-confirm 4=setup 5=error 6=closed 7=already-applied
"""

import json, logging, os, re, sys, time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
logger = logging.getLogger(__name__)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PERSONAL_INFO_PATH = os.path.join(os.path.dirname(_HERE), "personal-info.json")


def _load_personal():
    with open(_PERSONAL_INFO_PATH) as f:
        return json.load(f)


CDP_URL = os.environ.get("META_CDP", os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:19900"))
BASE_URL = "https://www.metacareers.com"
APPLY_URL_TPL = BASE_URL + "/profile/create_application/{job_id}/"
SUCCESS_TEXTS = ['application submitted', 'application was submitted', 'thank you for applying', 'you have applied', 'thanks for applying', 'your application for the', 'has been received']
CLOSED_TEXTS  = ['position not available', 'job is no longer available']
ALREADY_TEXTS = ['already applied', "you've already submitted"]
GENDER_CHOICE = RACE_CHOICE = VETERAN_CHOICE = "I choose not to disclose"
DISABILITY_CHOICE = "I do not want to answer"


def meta_dryrun(url):
    """HTTP dryrun: closed/applied check. No browser."""
    job_id = _extract_job_id(url)
    if not job_id: raise ValueError(f"Cannot extract job_id from: {url}")
    import requests
    r = requests.get(APPLY_URL_TPL.format(job_id=job_id), timeout=15,
                     headers={"User-Agent": "Mozilla/5.0 Chrome/125"}, allow_redirects=True)
    rurl, text = r.url, r.text.lower()
    if "position-not-available" in rurl or "position not available" in text:
        return {"job_id": job_id, "closed": True, "apply_url": url}
    if "already applied" in text:
        return {"job_id": job_id, "already_applied": True, "apply_url": url}
    m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', r.text)
    title = m.group(1).replace(" | Meta Careers", "").strip() if m else ""
    return {"job_id": job_id, "title": title, "apply_url": url,
            "has_work_auth_q": False, "blockers": [], "closed": False}


def _extract_job_id(url):
    m = re.search(r"/(\d{10,})", url)
    return m.group(1) if m else ""


def meta_submit(role_id, plan, resume_path, personal, dry_run=False):
    job_id = plan.get("job_id") or _extract_job_id(plan.get("apply_url", ""))
    if not job_id: logger.error("[meta] no job_id"); return 4
    apply_url = APPLY_URL_TPL.format(job_id=job_id)
    i, c, a = personal.get("identity",{}), personal.get("contact",{}), personal.get("address",{})
    first  = i.get("first_name","")
    last   = i.get("last_name","")
    email  = c.get("email","")
    phone  = re.sub(r"\D","",c.get("phone",""))
    web    = c.get("website_required_fallback", c.get("linkedin",""))
    curloc = a.get("city","Kirkland") + ", " + a.get("state_abbr","WA")
    locpref = plan.get("location_pref","")
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        # Try to reuse an existing page that has already hydrated the Meta SPA.
        # A bare new_context+new_page gets incomplete React hydration on Meta.
        page = None
        ctx_to_close = None
        try:
            for existing_ctx in browser.contexts:
                for existing_page in existing_ctx.pages:
                    if "metacareers.com/profile/create_application" in existing_page.url:
                        page = existing_page
                        logger.info(f"[meta] reusing existing page {existing_page.url[:60]}")
                        break
                if page: break
        except Exception as e:
            logger.warning(f"[meta] page-reuse scan failed: {e}")
        if page is None:
            ctx_to_close = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                )
            )
            page = ctx_to_close.new_page()
        try:
            return _run_apply(page, apply_url, role_id, first, last, email, phone, web, curloc, locpref, resume_path, dry_run)
        except PWTimeoutError as e: logger.error(f"[meta] timeout: {e}"); return 5
        except Exception as e: logger.error(f"[meta] error: {e}", exc_info=True); return 5
        finally:
            if ctx_to_close:
                try: ctx_to_close.close()
                except Exception: pass


def _run_apply(page, apply_url, role_id, first, last, email, phone, web, curloc, locpref, resume_path, dry_run):
    logger.info(f"[meta] role={role_id} -> {apply_url}")
    if page.url != apply_url:
        # Only navigate if not already on the right page (avoid beforeunload dialog on reuse)
        page.goto(apply_url, wait_until="domcontentloaded", timeout=25000)
    time.sleep(2)
    body = page.inner_text("body").lower()
    for t in CLOSED_TEXTS:
        if t in body: logger.info("[meta] closed"); return 6
    for t in ALREADY_TEXTS:
        if t in body: logger.info("[meta] already applied"); return 7
    fi = page.query_selector("input[type='file']")
    # Auth gate = no file input AND page contains login prompt (not the optional
    # 'Career Profile account' section which also mentions 'log in').
    if not fi:
        if "log in" in body and "career profile" not in body:
            logger.warning("[meta] auth gate"); return 2
        logger.error("[meta] no file input"); return 4
    fi.set_input_files(resume_path)
    time.sleep(1.5)
    _pick_location(page, locpref)
    time.sleep(0.5)
    # Fill text inputs by label context (some pages have a hidden text input at
    # index 0, shifting the visible fields). Find first+last+email+phone by label.
    _fill_by_label_context(page, "First name", first)
    _fill_by_label_context(page, "Last name", last)
    _fill_by_label_context(page, "Email", email)
    _fill_by_label_context(page, "Phone number", phone)
    if web:
        _fill_by_label_context(page, "Website", web)
    _fill_location_input(page, curloc)
    # Click demographic radios: gender(nth=0), race(nth=1), veteran(nth=2) all "decline"
    for nth, lbl in enumerate([GENDER_CHOICE, RACE_CHOICE, VETERAN_CHOICE]):
        _click_radio_by_label(page, lbl, nth=nth)
    time.sleep(0.5)
    _click_radio_by_label(page, DISABILITY_CHOICE, nth=0)
    if dry_run: logger.info("[meta] dry run"); return 0
    # Find submit button by type=submit or by text; Meta's React SPA sometimes
    # doesn't render button text in headless — use type=submit as primary selector.
    btn = page.query_selector("button[type='submit']") or _find_button(page, "Submit")
    if not btn: logger.error("[meta] no submit btn"); return 4
    # Scroll into view + wait for button to be enabled before clicking
    try: btn.scroll_into_view_if_needed(timeout=3000)
    except Exception: pass
    time.sleep(0.5)
    btn.click(); time.sleep(8)
    furl = page.url; fbody = page.inner_text("body").lower()
    logger.info(f"[meta] post-submit url={furl}")
    logger.info(f"[meta] post-submit body[:600]={fbody[:600]}")
    if "success" in furl: logger.info(f"[meta] SUCCESS {role_id}"); return 0
    for t in SUCCESS_TEXTS:
        if t in fbody: logger.info(f"[meta] SUCCESS {role_id}"); return 0
    for t in CLOSED_TEXTS:
        if t in fbody: return 6
    for t in ALREADY_TEXTS:
        if t in fbody: return 7
    # Check for validation errors that blocked submit — log full body for debug
    if any(err in fbody for err in ["required", "please", "error", "invalid"]):
        logger.warning(f"[meta] validation errors present; body={fbody[:1200]}")
        return 3
    logger.warning(f"[meta] no confirm url={furl} body={fbody[:600]}"); return 3


def _fill_remote_country(page):
    """After clicking Remote,US, fill country=United States + state=Washington."""
    try:
        time.sleep(0.8)
        country_inp = page.query_selector("input[placeholder='Country']")
        if not country_inp:
            logger.warning("[meta] remote-country input not found (may not be required)")
            return
        country_inp.click()
        country_inp.fill("United States")
        time.sleep(1.5)
        opts = page.query_selector_all("[role='option']")
        for opt in opts:
            if "United States" in opt.inner_text():
                opt.click(); time.sleep(0.8); break
        else:
            if opts: opts[0].click(); time.sleep(0.8)
        logger.info("[meta] remote country filled: United States")
        # Fill State/Province = Washington
        state_inp = page.query_selector("input[placeholder='State/Province']")
        if state_inp:
            state_inp.click(); state_inp.fill("Washington"); time.sleep(1.5)
            opts2 = page.query_selector_all("[role='option']")
            if opts2:
                opts2[0].click(); time.sleep(0.5)
                logger.info("[meta] remote state filled: Washington")
    except Exception as e:
        logger.warning(f"[meta] _fill_remote_country fail: {e}")


def _pick_location(page, locpref):
    """Check a location checkbox via native Playwright click.
    Meta checkboxes respond to native click() — React props approach not needed.
    Prefers Remote, US; falls back to first checkbox.
    """
    try:
        cbs = page.query_selector_all("input[type='checkbox']")
        if not cbs:
            logger.warning("[meta] no location checkboxes found")
            return
        # Build (label_text, cb) pairs using the closest label ancestor
        pairs = []
        for cb in cbs:
            try:
                txt = (cb.evaluate(
                    "el=>{let p=el.closest('label')||el.parentElement;"
                    "return (p?.innerText||'').trim().slice(0,80)}"
                ) or "").lower()
                pairs.append((txt, cb))
            except Exception:
                pairs.append(("", cb))
        target_cb = None
        pl = locpref.lower()
        if pl:
            for txt, cb in pairs:
                if pl in txt:
                    target_cb = cb; break
        if not target_cb:
            for needle in ["remote, us", "remote", "seattle", "bellevue", "menlo park"]:
                for txt, cb in pairs:
                    if needle in txt:
                        target_cb = cb; break
                if target_cb: break
        if not target_cb:
            target_cb = pairs[0][1]
        # Native click — confirmed to commit React state on Meta (2026-06-17 probe)
        target_cb.click()
        time.sleep(0.5)
        logger.info(f"[meta] location checked: aria={target_cb.get_attribute('aria-checked')} checked={target_cb.is_checked()}")
        # If Remote,US was checked, fill the country preference combobox that appears
        checked_txt = target_cb.evaluate("el=>{let p=el.closest('label')||el.parentElement;return (p?.innerText||'').trim().slice(0,40)}")
        if "remote" in checked_txt.lower():
            _fill_remote_country(page)
    except Exception as e:
        logger.warning(f"[meta] _pick_location fail: {e}")


def _fill_input(inputs, n, value):
    if n < len(inputs) and value:
        try: inputs[n].click(); inputs[n].fill(value)
        except Exception as e: logger.warning(f"[meta] input[{n}] fail: {e}")


def _fill_by_label_context(page, label_fragment, value):
    """Fill a text input whose container text contains label_fragment."""
    if not value: return
    try:
        ti = page.query_selector_all("input[type='text']")
        for inp in ti:
            ctx_text = inp.evaluate(
                "el=>{let p=el.parentElement;for(let i=0;i<4&&p;i++,p=p.parentElement){"
                "let t=(p.innerText||'').trim();if(t)return t;}return ''}"
            )
            if label_fragment.lower() in ctx_text.lower():
                inp.click()
                inp.fill(value)
                inp.dispatch_event("input")
                inp.dispatch_event("change")
                logger.info(f"[meta] filled {label_fragment!r}: {value[:30]!r}")
                return
        logger.warning(f"[meta] no text input found for label {label_fragment!r}")
    except Exception as e:
        logger.warning(f"[meta] _fill_by_label_context({label_fragment!r}) fail: {e}")


def _fill_labeled(page, label_text, value):
    """Fill a text input by finding its label first."""
    if not value: return
    try:
        # Try placeholder or aria-label first
        for sel in [
            f"input[placeholder*='{label_text}']",
            f"input[aria-label*='{label_text}']",
        ]:
            el = page.query_selector(sel)
            if el:
                el.click(); el.fill(value); return
        # Walk labels
        for lbl in page.query_selector_all("label, [class*='label'], [data-testid*='label']"):
            try:
                if label_text.lower() in lbl.inner_text().lower():
                    # Find associated input via for= or sibling
                    for_id = lbl.get_attribute("for")
                    inp = page.query_selector(f"#{for_id}") if for_id else None
                    if not inp:
                        inp = lbl.query_selector("input") or lbl.evaluate_handle(
                            "el=>el.nextElementSibling?.tagName==='INPUT'?el.nextElementSibling:null"
                        ).as_element()
                    if inp:
                        inp.click(); inp.fill(value); return
            except Exception: continue
        # Fallback: find containing generic with matching header text
        js_val = value.replace("'", "\\'").replace('"', '\\"')
        lbl_lc = label_text.lower()
        page.evaluate(f"""
            (function() {{
                var inputs = Array.from(document.querySelectorAll('input[type="text"],input:not([type])'));
                for (var inp of inputs) {{
                    var container = inp.closest('[class]') || inp.parentElement;
                    if (container && container.innerText.toLowerCase().includes('{lbl_lc}')) {{
                        var nativeInput = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
                        nativeInput.set.call(inp, '{js_val}');
                        inp.dispatchEvent(new Event('input', {{bubbles:true}}));
                        inp.dispatchEvent(new Event('change', {{bubbles:true}}));
                        break;
                    }}
                }}
            }})()
        """)
    except Exception as e:
        logger.warning(f"[meta] _fill_labeled({label_text!r}) fail: {e}")


def _fill_location_input(page, curloc):
    """Fill the 'Current location' button[role=combobox] typeahead."""
    try:
        # Meta renders it as: button[role=combobox][aria-label="Current location"]
        btn = page.query_selector("button[aria-label='Current location']")
        if not btn:
            logger.warning("[meta] current-location combobox button not found")
            return
        btn.click(); time.sleep(0.8)
        # Find the search input that appears after clicking the combobox.
        # Meta renders it as input[placeholder='Search'][aria-label='Search']
        inp = page.query_selector("input[aria-label='Search'][placeholder='Search']")
        if not inp:
            inp = page.query_selector("input[role='combobox'], input[aria-autocomplete], input[aria-label*='location' i]")
        if not inp:
            logger.warning("[meta] current-location search input not found")
            page.keyboard.press("Escape")
            return
        # Try progressively shorter search terms to find a match.
        # Filter options to prefer US results (contain ', WA' or ', US' or 'United States').
        city = curloc.split(",")[0].strip()
        candidates = [city, "Seattle, WA", "Bellevue, WA", "Seattle"]
        for term in candidates:
            inp.click(); inp.fill(""); time.sleep(0.3)
            inp.fill(term); time.sleep(2.0)  # wait longer for typeahead
            opts = page.query_selector_all("[role='option']")
            if opts:
                # Prefer US option
                us_opt = None
                for opt in opts:
                    try:
                        txt = opt.inner_text()
                        if any(s in txt for s in [", WA", ", CA", ", NY", ", TX", "United States", ", US"]):
                            us_opt = opt; break
                    except Exception: continue
                chosen = us_opt or opts[0]
                try:
                    chosen.click()
                    logger.info(f"[meta] current-location filled with: {term} (chose {chosen.inner_text()[:40]!r})")
                    return
                except Exception: continue
        # No typeahead match — just close the dropdown and leave blank
        logger.warning(f"[meta] current-location: no typeahead match for {curloc!r}")
        inp.press("Escape")
    except Exception as e:
        logger.warning(f"[meta] _fill_location_input fail: {e}")


def _fill_phone(page, phone):
    """Fill the phone number text input (skip the country-code combobox)."""
    if not phone: return
    try:
        # The phone input has a sibling country-code combobox — target the text input
        # by aria-label or by finding the input inside the phone number container
        inp = page.query_selector("input[type='tel'], input[aria-label*='phone' i], input[placeholder*='phone' i]")
        if not inp:
            # Find by container label
            for lbl in page.query_selector_all("*"):
                try:
                    if "phone number" in (lbl.inner_text() or "").lower() and len(lbl.inner_text()) < 30:
                        inp = lbl.query_selector("input[type='text']") or lbl.evaluate_handle(
                            "el=>el.parentElement?.querySelector('input[type=text]')"
                        ).as_element()
                        if inp: break
                except Exception: continue
        if inp:
            inp.click(); inp.fill(phone)
        else:
            logger.warning("[meta] phone input not found")
    except Exception as e:
        logger.warning(f"[meta] _fill_phone fail: {e}")


def _click_radio_by_label(page, label_text, nth=0):
    """Click the nth radio (0-indexed) whose container text contains label_text.
    Use nth to distinguish duplicate labels (e.g. 'I choose not to disclose' appears
    3 times for gender / race / veteran — pass nth=0,1,2 for each group)."""
    JS = """
        (function(args) { var labelText = args[0]; var nth = args[1];
            var radios = document.querySelectorAll('input[type="radio"]');
            var hits = [];
            for (var i = 0; i < radios.length; i++) {
                var r = radios[i];
                var container = r.closest('label') || r.parentElement;
                var txt = container ? (container.innerText || '') : '';
                if (txt.toLowerCase().indexOf(labelText.toLowerCase()) !== -1) {
                    hits.push(r);
                }
            }
            var r = hits[nth] || hits[0];
            if (!r) return null;
            var pk = Object.keys(r).find(function(k) {
                return k.startsWith('__reactProps');
            });
            if (pk && r[pk] && r[pk].onChange) {
                r[pk].onChange({target: {checked: true, value: r.value},
                                bubbles: true, currentTarget: r});
                var container = r.closest('label') || r.parentElement;
                return 'react:' + (container ? container.innerText.trim().slice(0, 40) : r.value);
            }
            r.click();
            var container2 = r.closest('label') || r.parentElement;
            return 'click:' + (container2 ? container2.innerText.trim().slice(0, 40) : r.value);
        })
    """
    try:
        result = page.evaluate(JS, [label_text, nth])
        if result:
            logger.info(f"[meta] radio picked (nth={nth}): {result}")
        else:
            logger.warning(f"[meta] radio not found: {label_text!r} nth={nth}")
    except Exception as e:
        logger.warning(f"[meta] _click_radio_by_label({label_text!r}) fail: {e}")


def _find_button(page, text):
    for sel in ['button', "div[role='button']"]:
        for el in page.query_selector_all(sel):
            try:
                if el.inner_text().strip() == text: return el
            except Exception: continue
    return None


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Meta Careers auto-apply runner")
    ap.add_argument("url")
    ap.add_argument("--role-id", default="0")
    ap.add_argument("--resume", required=False)
    ap.add_argument("--location-pref", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dryrun-only", action="store_true")
    args = ap.parse_args()
    personal = _load_personal()
    if args.dryrun_only:
        print(json.dumps(meta_dryrun(args.url), indent=2)); sys.exit(0)
    if not args.resume: print("ERROR: --resume required"); sys.exit(4)
    plan = {"job_id": _extract_job_id(args.url), "apply_url": args.url,
            "location_pref": args.location_pref}
    code = meta_submit(args.role_id, plan, args.resume, personal, dry_run=args.dry_run)
    print(f"EXIT {code}"); sys.exit(code)
