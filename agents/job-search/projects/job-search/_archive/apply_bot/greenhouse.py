"""
Greenhouse adapter v2.

Handles:
  - Classic Greenhouse forms (boards.greenhouse.io)
  - Formik-wrapped forms (job-boards.greenhouse.io) — uses press_sequentially
    so React onChange fires correctly
  - React-select dropdowns (Country, AI Policy, Sponsorship, etc.) — click input,
    type query, press Enter
  - Common yes/no custom questions via keyword map + profile data
  - Refuses to submit if any REQUIRED essay/textarea is still blank
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List

from playwright.sync_api import Page, TimeoutError as PWTimeout

from base import BaseApplier, RESUME


class GreenhouseApplier(BaseApplier):
    ATS_NAME = "greenhouse"

    YES_NO_RULES = [
        (r"sponsorship|visa.*sponsor|sponsor.*visa",  "No"),
        (r"authorized.*work|legally.*work|work.*authoriz|right to work|eligible.*work|"
         r"authoriz(ation|ed)?\s*to\s*work", "Yes"),
        (r"open to relocat|willing to relocat|able to relocat", "Yes"),
        (r"open.*work.*in[- ]?person|on[- ]?site.*office|in.office.*time|hybrid|25%|"
         r"willing to work from the office|come into the office", "Yes"),
        (r"willing to travel", "Yes"),
        (r"previously.*(applied|employed|worked)|interview.*at .* before|applied to .* before|"
         r"interviewed at|have you ever worked (for|at)", "No"),
        (r"background check", "Yes"),
        (r"agree.*(privacy|terms|policy)|acknowledge.*(read|understand|notice|policy)|"
         r"have read and understand|by submitting.*acknowledge|"
         r"double[- ]?check|ensuring accuracy", "Yes"),
        (r"ai policy|use of ai|generative ai", "Yes"),
        # Non-compete / restrictive agreements
        (r"non[- ]?compete|restrictive (agreement|covenant)|bound by (any )?agreement|non[- ]?disclosure|"
         r"currently subject to any agreement", "No"),
        # Security clearance
        (r"security clearance|active clearance|hold.*clearance", "No"),
        (r"open to obtaining|willing to obtain.*clearance", "No"),
        # Knowing employees / referrals (no by default — referrals are explicit elsewhere)
        (r"do you know anyone (currently )?(at|working at)|"
         r"any current employees|know any.*employees", "No"),
        # Robinhood-style compound conflict-of-interest questions
        (r"personal/familial relationships|outside business activities|"
         r"investment.*(shares|company)|intellectual property ownership|"
         r"conflict of interest", "No"),
        # Government-official / bribery/corruption screens
        (r"government official|bribery|corruption|public function", "No"),
        # Geo restriction screens
        # "Are you currently based in any of these countries? [US accepting]" → Yes (US)
        (r"are you (currently )?based in.*(countries|country)|"
         r"only countries where we are accepting", "Yes"),
        # "Do you live in [restrictive states list]?" → No (Cyrus is in WA, not in lists)
        (r"do you live in one of the following states", "No"),
    ]

    DEMO_RULES = [
        (r"^gender$|gender identity|i identify my gender", "Decline To Self Identify"),
        (r"race|ethnic|hispanic|i identify my race",       "Decline To Self Identify"),
        (r"veteran",                                       "I don't wish to answer"),
        (r"disability",                                    "I don't wish to answer"),
        (r"sexual orientation|i identify my sexual",       "Decline To Self Identify"),
        (r"military status",                               "I don't wish to answer"),
        # Catch-all "I identify as:" (race/ethnicity variant) — keep last so
        # specific identity rules above win.
        (r"^i identify as",                                "Decline To Self Identify"),
    ]

    # Fallback strings tried in order if the canonical answer doesn't match a
    # react-select option. Useful for "Decline / I don't wish / I do not want"
    # variants across ATS tenants.
    ANSWER_FALLBACKS: Dict[str, List[str]] = {
        "I don't wish to answer": [
            "I do not want to answer",
            "I prefer not to answer",
            "I don't want to answer",
            "Decline to answer",
            "Prefer not to say",
            "Decline To Self Identify",
        ],
        "Decline To Self Identify": [
            "Decline to self-identify",
            "I don't wish to answer",
            "I do not want to answer",
            "Prefer not to say",
        ],
        "Yes": [
            "I agree", "I confirm", "Confirmed", "Acknowledge",
            # Work-authorization "yes" variants
            "U.S. Citizen", "US Citizen", "Citizen",
            "Authorized to work without sponsorship",
            "I am authorized to work without sponsorship",
            "Yes - U.S. Citizen or Permanent Resident",
        ],
        "No":  [
            "I disagree", "Decline",
            "No, I have not", "Never", "I have not",
        ],
    }

    COUNTRY_DEFAULT = "United States"

    def apply(self, page: Page, profile: Dict[str, Any]) -> None:
        page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        self.screenshot(page, "01-landed")

        self._click_apply_if_present(page)
        time.sleep(2)
        self.screenshot(page, "02-form")

        try:
            page.wait_for_selector(
                "input[id^='first_name'], input[name='job_application[first_name]'], #first_name",
                timeout=15000,
            )
        except PWTimeout:
            self.note("first-name field not found; form layout may be unusual")

        self._type_first(page, profile["identity"]["first_name"], [
            "input[id^='first_name']",
            "input[name='job_application[first_name]']",
            "input[autocomplete='given-name']",
            "#first_name",
        ], "first_name")
        self._type_first(page, profile["identity"]["last_name"], [
            "input[id^='last_name']",
            "input[name='job_application[last_name]']",
            "input[autocomplete='family-name']",
            "#last_name",
        ], "last_name")

        self._type_first(page, profile["contact"]["email"], [
            "#email",
            "input[autocomplete='email']",
            "input[name='job_application[email]']",
            "input[type='email']",
        ], "email")

        self._type_first(page, profile["contact"]["phone"], [
            "#phone",
            "input[type='tel']",
            "input[autocomplete='tel']",
            "input[name='job_application[phone]']",
        ], "phone")

        # Top-level LinkedIn / website (rare on Greenhouse; ignore if absent —
        # custom-question handler will catch the LinkedIn Profile field
        # commonly added by employers).
        self._type_first(page, profile["contact"]["linkedin"], [
            "input[id*='linkedin' i]",
            "input[name*='linkedin' i]",
            "input[id*='website' i]",
            "input[name*='website' i]",
        ], "linkedin/website", silent_if_missing=True)

        self._type_first(page,
                         f"{profile['address']['city']}, {profile['address']['state']}",
                         [
                             "input[id*='location' i]",
                             "input[id*='city' i]",
                             "input[name*='location' i]",
                             "input[autocomplete='address-level2']",
                             "input[placeholder*='city' i]",
                             "input[placeholder*='location' i]",
                             "input[aria-label*='location' i]",
                             "input[aria-label*='city' i]",
                         ], "location",
                         silent_if_missing=True)

        self._upload_resume(page)

        # Country react-select (Anthropic uses id='country')
        self._react_select(page, "country", self.COUNTRY_DEFAULT, "country")

        self._answer_custom_questions(page, profile)

        self.screenshot(page, "03-filled")
        unanswered = self._unanswered_required(page)
        if unanswered:
            self.note(f"REFUSING TO SUBMIT — {len(unanswered)} required field(s) still blank")
            self.result.notes.append({"unanswered": unanswered})
            return

        if self.dry_run:
            self.note("dry-run: stopping before submit")
            return

        if self.prep_mode:
            self.note("prep mode: form is filled. NOT clicking submit. "
                      "Click Submit yourself in the browser window.")
            return

        # Match Submit application FIRST (the form's actual submit), not the
        # top-of-page Apply button which we already clicked to expand the form.
        submit = page.locator(
            "button:has-text('Submit application'), button:has-text('Submit Application'), "
            "input[type='submit'][value*='Submit' i]"
        ).first
        if submit.count() == 0:
            # last-resort fallback
            submit = page.locator("button[type='submit']").last
        if submit.count() == 0:
            self.note("submit button not found")
            return
        submit.scroll_into_view_if_needed()
        # Notify the OTP poller (if any) of submit timestamp so it ignores older mail
        if hasattr(self, "_otp_provider") and self._otp_provider:
            poller = getattr(self._otp_provider, "__self__", None)
            if poller is not None and hasattr(poller, "mark_poll_start"):
                poller.mark_poll_start()
        submit.click()
        # Wait up to 15s for either confirmation OR the OTP fallback UI to render.
        otp_appeared = False
        for _ in range(15):
            time.sleep(1)
            try:
                body_now = page.locator("body").inner_text(timeout=2000).lower()
            except Exception:
                continue
            if "verification code was sent" in body_now or "security code" in body_now:
                otp_appeared = True
                break
            if any(k in body_now for k in ("thank you for applying", "we've received your application",
                                           "application received", "successfully submitted")):
                break
        self.screenshot(page, "04-after-submit")

        # Check for the email-OTP fallback that Greenhouse shows when
        # reCAPTCHA Enterprise scores us as a bot (which is always for headless).
        if otp_appeared and self._handle_otp_challenge(page):
            time.sleep(5)
            self.screenshot(page, "06-after-otp-submit")

        body = page.locator("body").inner_text(timeout=5000).lower()
        if any(k in body for k in ("thank you", "we've received", "application received",
                                   "successfully submitted", "application was submitted",
                                   "your application has been")):
            self.result.submitted = True
            self.note("submission confirmed")
        else:
            self.note("submit clicked but no confirmation matched; review screenshots")

    def _handle_otp_challenge(self, page: Page) -> bool:
        """If Greenhouse shows the 'enter 8-char security code' fallback,
        prompt the user for the code (via stdin), fill it, and re-submit.
        Returns True iff we attempted the OTP path."""
        try:
            body = page.locator("body").inner_text(timeout=3000)
        except Exception:
            return False
        if "verification code was sent" not in body.lower() and "security code" not in body.lower():
            return False

        # Find the recipient email if shown
        m = re.search(r"sent to\s+([^\s.]+@[^\s.]+(?:\.[^\s.]+)+)", body, re.I)
        recipient = m.group(1) if m else "(unknown email)"

        self.note(f"reCAPTCHA failed -> Greenhouse sent OTP to {recipient}")
        self.screenshot(page, "05-otp-prompt")

        # Find the security-code input
        code_input = page.locator(
            "input[name*='security' i], input[id*='security' i], "
            "input[name*='code' i], input[id*='code' i], input[autocomplete='one-time-code']"
        ).first
        if code_input.count() == 0:
            self.note("OTP input field not found on page")
            return True

        # If running with otp_provider, use it; else prompt stdin (only if interactive
        # AND not explicitly told to skip via APPLY_OTP_NONINTERACTIVE=1).
        otp = None
        if hasattr(self, "_otp_provider") and self._otp_provider:
            otp = self._otp_provider(recipient)
        else:
            import os as _os, sys as _sys
            non_interactive = _os.environ.get("APPLY_OTP_NONINTERACTIVE") == "1"
            if non_interactive:
                self.note(f"OTP required at {recipient}; APPLY_OTP_NONINTERACTIVE=1 set, "
                          f"exiting with otp-pending status. Re-run with --otp <code>.")
                self.result.notes.append({"otp_pending": True, "recipient": recipient})
                return True
            if _sys.stdin and _sys.stdin.isatty():
                print(f"\n[ACTION REQUIRED] Greenhouse sent an 8-character security code to {recipient}.")
                print("Open your inbox, find the email from Greenhouse, and paste the code here.")
                try:
                    otp = input("Security code (8 chars): ").strip()
                except EOFError:
                    self.note("EOF reading OTP; aborting")
                    return True
            else:
                self.note(f"OTP required at {recipient} but stdin is not interactive. "
                          "Re-run with --prep, or supply --otp <code>, or run from a terminal.")
                return True

        if not otp:
            self.note("empty OTP provided; aborting")
            return True

        code_input.click()
        code_input.fill("")
        code_input.press_sequentially(otp, delay=30)
        time.sleep(0.5)

        # Click Submit application again
        final_submit = page.locator(
            "button:has-text('Submit application'), button:has-text('Submit Application'), "
            "button[type='submit']"
        ).last
        if final_submit.count() > 0:
            final_submit.scroll_into_view_if_needed()
            final_submit.click()
            time.sleep(5)
            self.note("OTP submitted")
        return True

    # ---------------- helpers ----------------

    def _click_apply_if_present(self, page: Page) -> None:
        for sel in [
            "a:has-text('Apply for this job')",
            "button:has-text('Apply for this job')",
            "a:has-text('Apply')",
            "button:has-text('Apply')",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.count() and btn.is_visible():
                    btn.click()
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    self.note(f"clicked apply via {sel}")
                    return
            except Exception:
                continue

    def _type_first(self, page: Page, value: str, selectors: List[str], label: str,
                    silent_if_missing: bool = False) -> bool:
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() == 0:
                    continue
                loc.scroll_into_view_if_needed(timeout=3000)
                loc.click(timeout=3000)
                try:
                    loc.fill("", timeout=2000)
                except Exception:
                    pass
                loc.press_sequentially(value, delay=10, timeout=15000)
                page.keyboard.press("Tab")
                self.record_fill(sel, label, value, "type", success=True)
                return True
            except Exception:
                continue
        if not silent_if_missing:
            self.record_fill(",".join(selectors)[:120], label, value, "type",
                             success=False, error="no-selector-matched")
            self.note(f"could not fill {label}")
        return False

    def _upload_resume(self, page: Page) -> None:
        if not RESUME.exists():
            return
        for sel in [
            "input[type='file'][name*='resume' i]",
            "input[type='file'][id*='resume' i]",
            "input[type='file']",
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() == 0:
                    continue
                loc.set_input_files(str(RESUME), timeout=10000)
                self.record_fill(sel, "resume", str(RESUME), "upload", success=True)
                time.sleep(2)
                return
            except Exception:
                continue
        self.record_fill("input[type='file']", "resume", str(RESUME), "upload",
                         success=False, error="no-file-input-matched")

    def _react_select(self, page: Page, input_id_substr: str, value: str, label: str) -> bool:
        candidates = [value] + self.ANSWER_FALLBACKS.get(value, [])
        last_err = None
        for cand in candidates:
            try:
                inp = page.locator(f"input[id='{input_id_substr}'], input[id*='{input_id_substr}']").first
                if inp.count() == 0:
                    return False
                inp.scroll_into_view_if_needed(timeout=2000)
                inp.click(timeout=2000)
                time.sleep(0.2)
                # Clear any previous typing first
                page.keyboard.press("Control+A")
                page.keyboard.press("Delete")
                inp.press_sequentially(cand, delay=15, timeout=8000)
                time.sleep(0.6)
                # If "no options" message appears, try next candidate
                no_opt = page.locator("div[class*='noOptions' i], div[class*='no-options' i]").first
                if no_opt.count() and no_opt.is_visible():
                    last_err = f"no match for '{cand}'"
                    page.keyboard.press("Escape")
                    continue
                option = page.locator("div[class*='option']:not([class*='disabled' i])").first
                if option.count():
                    option.click(timeout=3000)
                else:
                    page.keyboard.press("Enter")
                self.record_fill(f"react-select#{input_id_substr}", label, cand, "react-select", True)
                return True
            except Exception as e:
                last_err = str(e)[:200]
                continue
        self.record_fill(f"react-select#{input_id_substr}", label, value, "react-select",
                         False, last_err or "no candidate matched")
        return False

    def _answer_custom_questions(self, page: Page, profile: Dict[str, Any]) -> None:
        labels = page.locator("label").all()
        for label_el in labels[:300]:
            try:
                text = (label_el.inner_text(timeout=800) or "").strip()
            except Exception:
                continue
            if not text or len(text) > 1000:
                continue
            answer = self._resolve_answer(text, profile)
            if answer is None:
                continue
            self._set_answer(page, label_el, text, answer)

    def _resolve_answer(self, label_text: str, profile: Dict[str, Any]) -> str | None:
        for rx, ans in self.DEMO_RULES:
            if re.search(rx, label_text, re.I):
                return ans
        for rx, ans in self.YES_NO_RULES:
            if re.search(rx, label_text, re.I):
                return ans
        if re.search(r"how did you hear|where did you (first )?hear", label_text, re.I):
            return profile["common_form_answers"]["how_did_you_hear_about_us"]
        if re.search(r"\bcountry\b", label_text, re.I):
            return self.COUNTRY_DEFAULT
        if re.search(r"linkedin", label_text, re.I):
            return profile["contact"]["linkedin"]
        if re.search(r"^(personal )?(website|portfolio|github)", label_text, re.I):
            return profile["contact"].get("github") or profile["contact"]["linkedin"]
        # Preferred / nickname first name
        if re.search(r"preferred (first )?name|nickname", label_text, re.I):
            return profile["identity"].get("preferred_name") or profile["identity"]["first_name"]
        # Custom-question Location / City field (Robinhood, etc.)
        if re.search(r"^location\b|location.*\(city\)|^city\b", label_text, re.I):
            return f"{profile['address']['city']}, {profile['address']['state']}"
        # Years of experience
        if re.search(r"(total |minimum |years? of )?experience.*(years?|relevant)|"
                     r"years? of (relevant )?experience|"
                     r"how many years", label_text, re.I):
            return (profile.get("experience_summary", {})
                    .get("answer_for_years_of_experience_field") or "3")
        return None

    def _set_answer(self, page: Page, label_el, label_text: str, answer: str) -> None:
        try:
            for_id = label_el.get_attribute("for")
        except Exception:
            for_id = None

        if for_id:
            try:
                ctrl = page.locator(f"#{for_id}").first
                if ctrl.count():
                    if self._set_via_control(page, ctrl, for_id, answer, label_text):
                        return
            except Exception:
                pass

        try:
            container = label_el.locator(
                "xpath=ancestor::*[contains(@class,'select') or self::div][1]"
            )
            rs_input = container.locator("input[role='combobox'], input[id]").first
            if rs_input.count():
                rs_id = rs_input.get_attribute("id") or ""
                if rs_id and self._react_select(page, rs_id, answer, label_text):
                    return
        except Exception:
            pass

    def _set_via_control(self, page: Page, ctrl, ctrl_id: str, answer: str, label_text: str) -> bool:
        try:
            tag = ctrl.evaluate("el => el.tagName.toLowerCase()")
            ctype = (ctrl.get_attribute("type") or "").lower()
            role = (ctrl.get_attribute("role") or "").lower()
            cls = (ctrl.evaluate("el => el.className") or "")

            if role == "combobox" or "select__input" in cls or "select-input" in cls:
                return self._react_select(page, ctrl_id, answer, label_text)

            if tag == "select":
                try:
                    ctrl.select_option(label=answer, timeout=2000)
                except Exception:
                    try:
                        ctrl.select_option(value=answer.lower(), timeout=2000)
                    except Exception:
                        return False
                self.record_fill(f"#{ctrl_id}", label_text, answer, "select", True)
                return True

            if tag == "textarea" or (tag == "input" and ctype in ("text", "")):
                ctrl.click(timeout=2000)
                ctrl.fill("", timeout=2000)
                ctrl.press_sequentially(answer, delay=10, timeout=8000)
                page.keyboard.press("Tab")
                self.record_fill(f"#{ctrl_id}", label_text, answer, "type", True)
                return True

            if ctype in ("radio", "checkbox"):
                container = ctrl.locator(
                    "xpath=ancestor::*[self::fieldset or self::div][1]"
                )
                target = container.locator(f"label:has-text('{answer}')").first
                if target.count():
                    target.click()
                    self.record_fill(f"#{ctrl_id}", label_text, answer, "click", True)
                    return True
                return False
        except Exception as e:
            self.record_fill(f"#{ctrl_id}", label_text, answer, "auto", False, str(e)[:150])
            return False
        return False

    def _unanswered_required(self, page: Page) -> List[str]:
        """Detect required fields that are still blank.

        React-Select inputs are skipped — their <input> is just a search box and
        always reads as empty after selection; the chosen value lives in a
        sibling <div class='select__single-value'>. We confirm those via that
        div instead.
        """
        unanswered = []
        controls = page.locator(
            "input[aria-required='true'], textarea[aria-required='true'], "
            "input[required], textarea[required]"
        ).all()
        seen = set()
        for c in controls:
            try:
                if not c.is_visible():
                    continue
                ctype = (c.get_attribute("type") or "").lower()
                if ctype in ("file",):
                    continue
                role = (c.get_attribute("role") or "").lower()
                cls = c.evaluate("el => el.className") or ""
                is_react_select = (
                    role == "combobox"
                    or "select__input" in cls
                    or "select-input" in cls
                )
                if is_react_select:
                    # Verify a value was selected (look for sibling single-value)
                    try:
                        container = c.locator(
                            "xpath=ancestor::*[contains(@class,'select__control')][1]"
                        )
                        sv = container.locator(
                            ".select__single-value, [class*='singleValue']"
                        ).first
                        if sv.count() and (sv.inner_text(timeout=500) or "").strip():
                            continue  # value selected, fine
                    except Exception:
                        pass
                else:
                    val = c.input_value() if ctype not in ("submit", "button") else ""
                    if val and val.strip():
                        continue

                cid = c.get_attribute("id") or ""
                # Skip irrelevant infrastructure inputs
                if cid.startswith("iti-"):  # phone country flag picker
                    continue
                lbl_text = ""
                if cid:
                    lbl = page.locator(f"label[for='{cid}']").first
                    if lbl.count():
                        try:
                            lbl_text = lbl.inner_text(timeout=500).strip()
                        except Exception:
                            pass
                if not lbl_text:
                    # Fallback: ancestor label, aria-label, placeholder, or
                    # preceding heading. This eliminates "unknown" entries.
                    for getter in (
                        lambda: c.evaluate(
                            "el => el.closest('label')?.innerText || ''"),
                        lambda: c.get_attribute("aria-label") or "",
                        lambda: c.get_attribute("placeholder") or "",
                        lambda: c.evaluate(
                            "el => { const f = el.closest('fieldset,div,section'); "
                            "if (!f) return ''; "
                            "const lg = f.querySelector('legend,h2,h3,h4,label,.application-question'); "
                            "return lg ? lg.innerText : ''; }"),
                    ):
                        try:
                            v = (getter() or "").strip()
                            if v:
                                lbl_text = v
                                break
                        except Exception:
                            continue
                key = lbl_text or cid or "unknown"
                if key in seen:
                    continue
                seen.add(key)
                unanswered.append(key)
            except Exception:
                continue
        return unanswered
