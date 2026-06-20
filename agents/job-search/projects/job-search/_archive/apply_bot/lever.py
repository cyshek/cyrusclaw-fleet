"""
Lever ATS adapter.

Lever forms (jobs.lever.co/{company}/{job-id}/apply) have a well-known schema:
  - input[name=name] (single full-name field, not first/last)
  - input[name=email], input[name=phone]
  - input[name=location] + hidden input[name=selectedLocation] (typeahead)
  - input[name=org] (current company)
  - input[name=urls[LinkedIn|GitHub|Portfolio|Other]]
  - input[type=file][name=resume]
  - input[name=pronouns] (checkboxes; "Use name only" is a clean opt-out)
  - input[name="cards[<uuid>][...]"] for custom employer questions
  - input[name="surveysResponses[<uuid>][...]"] for EEO/demographic surveys
  - <li class="application-question"> wraps each question; "custom-question"
    modifier marks employer-added questions
  - Required questions show ✱ in their label
  - Submit: <button type="button"> with text "SUBMIT APPLICATION"
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List

from playwright.sync_api import Page, TimeoutError as PWTimeout

from base import BaseApplier, RESUME


class LeverApplier(BaseApplier):
    ATS_NAME = "lever"

    YES_NO_RULES = [
        (r"sponsorship|visa.*sponsor|sponsor.*visa", "No"),
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
         r"have read and understand|by submitting.*acknowledge|consent.*contact", "Yes"),
        # AI notetaker / recording consent
        (r"ai notetaker|notetaker|transcribe.*conversation|"
         r"record.*(interview|meeting|conversation)|consent.*(record|transcrib|ai)",
         "Yes"),
        (r"ai policy|use of ai|generative ai", "Yes"),
        (r"non[- ]?compete|restrictive (agreement|covenant)|bound by (any )?agreement|"
         r"non[- ]?disclosure|currently subject to any agreement", "No"),
        (r"security clearance|active clearance|hold.*clearance", "No"),
        (r"open to obtaining|willing to obtain.*clearance", "No"),
        (r"do you know anyone (currently )?(at|working at)|"
         r"any current employees|know any.*employees", "No"),
        (r"personal/familial relationships|outside business activities|"
         r"investment.*(shares|company)|intellectual property ownership|"
         r"conflict of interest", "No"),
        (r"government official|bribery|corruption|public function", "No"),
    ]

    DEMO_DECLINE_VARIANTS = [
        "Prefer not to disclose",
        "I prefer not to say",
        "Prefer not to say",
        "Decline to self-identify",
        "Choose not to disclose",
        "I don't wish to answer",
        "I do not want to answer",
        "Decline to answer",
    ]

    DEMO_KEYWORDS = (
        "gender", "ethnic", "race", "hispanic", "veteran", "disability",
        "sexual orientation", "lgbt", "i identify",
    )

    def apply(self, page: Page, profile: Dict[str, Any]) -> None:
        # Lever URLs may be the listing or the /apply form. Normalize to /apply.
        url = self.url
        if "/apply" not in url.rstrip("/").split("/")[-1]:
            url = url.rstrip("/") + "/apply"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        self.screenshot(page, "01-landed")

        self._dismiss_cookie_banner(page)

        try:
            page.wait_for_selector(
                "input[name='name'], input[name='email'], input[type='file'][name='resume']",
                timeout=15000,
            )
        except PWTimeout:
            self.note("form fields not found; URL may not be a Lever apply page")
            return

        # Resume FIRST — Lever sometimes parses it and prefills name/email.
        self._upload_resume(page)
        time.sleep(2)

        ident = profile["identity"]
        contact = profile["contact"]
        addr = profile["address"]
        full_name = f"{ident['first_name']} {ident['last_name']}"

        self._type_named(page, "name", full_name, "name")
        self._type_named(page, "email", contact["email"], "email")
        self._type_named(page, "phone", contact["phone"], "phone")
        self._fill_location(page, f"{addr['city']}, {addr['state']}")

        # Current company / org
        current_emp = (profile.get("experience_summary", {})
                       .get("current_employer") or "")
        if current_emp:
            self._type_named(page, "org", current_emp, "org",
                             silent_if_missing=True)

        self._type_named(page, "urls[LinkedIn]", contact.get("linkedin", ""),
                         "linkedin", silent_if_missing=True)
        self._type_named(page, "urls[GitHub]", contact.get("github", ""),
                         "github", silent_if_missing=True)
        self._type_named(page, "urls[Portfolio]",
                         contact.get("portfolio_url") or contact.get("github", ""),
                         "portfolio", silent_if_missing=True)
        self._type_named(page, "urls[Other]", contact.get("linkedin", ""),
                         "other", silent_if_missing=True)

        # Pronouns: prefer "Use name only" (clean opt-out, doesn't disclose).
        self._set_pronouns_use_name_only(page)

        # Custom employer questions and EEO surveys
        self._answer_application_questions(page, profile)

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
                      "Click SUBMIT APPLICATION yourself in the browser.")
            return

        # Submit
        submit = page.locator(
            "button:has-text('SUBMIT APPLICATION'), "
            "button:has-text('Submit application'), "
            "button:has-text('Submit Application')"
        ).first
        if submit.count() == 0:
            self.note("submit button not found")
            return
        submit.scroll_into_view_if_needed()
        submit.click()
        time.sleep(8)
        self.screenshot(page, "04-after-submit")

        # Lever redirects to /thanks on success; also shows "Application submitted"
        body = ""
        try:
            body = page.locator("body").inner_text(timeout=5000).lower()
        except Exception:
            pass
        post_url = page.url
        if ("/thanks" in post_url
                or "application submitted" in body
                or "thank you for applying" in body
                or "we have received your application" in body):
            self.result.submitted = True
            self.note("submission confirmed")
        else:
            self.note("submit clicked but no confirmation matched; review screenshots")

    # ---------------- helpers ----------------

    def _dismiss_cookie_banner(self, page: Page) -> None:
        for sel in [
            "button:has-text('Deny')",
            "button:has-text('deny')",
            "button:has-text('Reject all')",
            "button:has-text('Accept')",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.count() and btn.is_visible():
                    btn.click(timeout=2000)
                    self.note(f"dismissed cookie banner via {sel}")
                    time.sleep(0.5)
                    return
            except Exception:
                continue

    def _upload_resume(self, page: Page) -> None:
        if not RESUME.exists():
            return
        for sel in [
            "input[type='file'][name='resume']",
            "input#resume-upload-input",
            "input[type='file']",
        ]:
            try:
                loc = page.locator(sel).first
                if loc.count() == 0:
                    continue
                loc.set_input_files(str(RESUME), timeout=10000)
                self.record_fill(sel, "resume", str(RESUME), "upload", success=True)
                return
            except Exception:
                continue
        self.record_fill("input[type=file]", "resume", str(RESUME), "upload",
                         success=False, error="no-file-input-matched")

    def _type_named(self, page: Page, field_name: str, value: str, label: str,
                    silent_if_missing: bool = False) -> bool:
        if not value:
            return False
        # name=foo or name="foo[bar]" — escape brackets for CSS attribute selector
        safe = field_name.replace("[", "\\[").replace("]", "\\]")
        sel = f"input[name='{field_name}'], input[name={safe}]"
        try:
            loc = page.locator(f"input[name='{field_name}']").first
            if loc.count() == 0:
                if not silent_if_missing:
                    self.record_fill(sel, label, value, "type",
                                     success=False, error="not-found")
                return False
            try:
                loc.scroll_into_view_if_needed(timeout=2000)
            except Exception:
                pass
            # Use fill() directly — works whether or not the field is clickable
            try:
                loc.fill(value, timeout=5000)
                self.record_fill(sel, label, value, "fill", success=True)
                return True
            except Exception:
                # Fallback: focus + type
                try:
                    loc.focus(timeout=2000)
                    loc.press_sequentially(value, delay=10, timeout=10000)
                    self.record_fill(sel, label, value, "type", success=True)
                    return True
                except Exception as e2:
                    if not silent_if_missing:
                        self.record_fill(sel, label, value, "type",
                                         success=False, error=str(e2)[:200])
                    return False
        except Exception as e:
            if not silent_if_missing:
                self.record_fill(sel, label, value, "type",
                                 success=False, error=str(e)[:200])
            return False

    def _fill_location(self, page: Page, value: str) -> bool:
        """Lever uses a typeahead. Type, wait for suggestions, click first."""
        try:
            loc = page.locator("input[name='location']").first
            if loc.count() == 0:
                self.record_fill("input[name=location]", "location", value,
                                 "typeahead", success=False, error="not-found")
                return False
            loc.scroll_into_view_if_needed(timeout=3000)
            loc.click(timeout=3000)
            try:
                loc.fill("", timeout=2000)
            except Exception:
                pass
            loc.press_sequentially(value, delay=15, timeout=10000)
            time.sleep(1.2)  # let suggestions render
            for opt_sel in [
                "div.dropdown-results .dropdown-result",
                "ul.dropdown-list li",
                "div[class*='dropdown'] [role='option']",
                "li[role='option']",
            ]:
                try:
                    opt = page.locator(opt_sel).first
                    if opt.count() and opt.is_visible():
                        opt.click(timeout=2000)
                        self.record_fill("input[name=location]", "location", value,
                                         "typeahead", success=True)
                        return True
                except Exception:
                    continue
            # Fallback: leave typed value AND set hidden selectedLocation so
            # Lever's validator doesn't flag it unanswered
            page.keyboard.press("Tab")
            try:
                page.evaluate("""(v) => {
                    const h = document.querySelector("input[name='selectedLocation']");
                    if (h) {
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        setter.call(h, v);
                        h.dispatchEvent(new Event('input', {bubbles:true}));
                        h.dispatchEvent(new Event('change', {bubbles:true}));
                    }
                    const t = document.querySelector("input[name='location']");
                    if (t) {
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                        setter.call(t, v);
                        t.dispatchEvent(new Event('input', {bubbles:true}));
                        t.dispatchEvent(new Event('change', {bubbles:true}));
                    }
                }""", value)
            except Exception:
                pass
            self.record_fill("input[name=location]", "location", value,
                             "typeahead", success=True,
                             error="no dropdown option clicked; left typed value")
            return True
        except Exception as e:
            self.record_fill("input[name=location]", "location", value,
                             "typeahead", success=False, error=str(e)[:200])
            return False

    def _set_pronouns_use_name_only(self, page: Page) -> None:
        """Click 'Use name only' if present — preserves privacy without
        leaving the question blank."""
        try:
            cb = page.locator("input#useNameOnlyPronounsOption, "
                              "input[name='pronouns'][value='__useNameOnly__']").first
            if cb.count():
                cb.scroll_into_view_if_needed(timeout=2000)
                cb.check(timeout=2000)
                self.record_fill("input#useNameOnlyPronounsOption", "pronouns",
                                 "Use name only", "click", success=True)
        except Exception:
            pass

    def _answer_application_questions(self, page: Page, profile: Dict[str, Any]) -> None:
        """Walk each <li class='application-question'> and answer custom
        employer questions + EEO surveys."""
        items = page.locator("li.application-question").all()
        for li in items:
            try:
                self._answer_one_question(page, li, profile)
            except Exception as e:
                self.note(f"question handler error: {str(e)[:150]}")

    def _answer_one_question(self, page: Page, li, profile: Dict[str, Any]) -> None:
        # Skip standard top-of-form fields (already handled)
        try:
            cls = li.get_attribute("class") or ""
        except Exception:
            cls = ""
        # Get the question heading text — prefer .application-label (Lever's
        # question heading) over <label> which Lever uses for OPTION labels
        # inside multi-choice groups (would otherwise return e.g. "English (ENG)").
        try:
            label = li.locator(".application-label").first
            if label.count() == 0:
                label = li.locator("legend, h3, h4, label").first
            qtext = (label.inner_text(timeout=600) or "").strip() if label.count() else ""
        except Exception:
            qtext = ""
        if not qtext:
            return
        qtext_clean = qtext.replace("✱", "").strip()
        qlow = qtext_clean.lower()

        # Skip if this is a standard field we already filled at top
        if any(s in qlow for s in (
            "full name", "email address", "phone number",
            "linkedin url", "github url", "portfolio url", "other website",
            "resume/cv", "attach resume",
        )):
            return

        # Custom "Current location" / "City" question: it usually wraps the same
        # input[name=location] that the top-level handler already filled. If
        # that fill didn't stick (React typeahead can wipe value when no dropdown
        # match), re-run the typeahead-aware filler.
        if re.search(r"^current location|^location|^city\b|^current city",
                     qtext_clean, re.I):
            addr = profile.get("address", {})
            city_state = f"{addr.get('city', '')}, {addr.get('state', '')}".strip(", ")
            # If LI contains the top-level location input, only retry typeahead
            # if its current value is empty (top-level call may already have
            # filled it; avoid duplicate click-timeout)
            has_loc_input = li.locator("input[name='location']").count() > 0
            if has_loc_input and city_state:
                cur = li.evaluate("el => { const i = el.querySelector(\"input[name='location']\"); return i ? (i.value || '') : ''; }")
                if not cur.strip():
                    self._fill_location(page, city_state)
                return
            if city_state and self._fill_text_in(li, city_state):
                self.record_fill(f"li[{qtext_clean[:40]}]", qtext_clean,
                                 city_state, "type", success=True)
                return

        # EEO/demographic survey question: pick "Prefer not to disclose" variant
        is_demo = any(k in qlow for k in self.DEMO_KEYWORDS)
        if is_demo or "surveysresponses" in (
            li.evaluate("el => Array.from(el.querySelectorAll('input')).map(i => i.name).join(',')") or ""
        ).lower():
            for variant in self.DEMO_DECLINE_VARIANTS:
                if self._click_radio_or_checkbox_in(li, variant):
                    self.record_fill(f"li.application-question[{qtext_clean[:40]}]",
                                     qtext_clean, variant, "click", success=True)
                    return
            # Fall through to YES_NO matching as a last resort

        # Custom question with Yes/No / acknowledge semantics
        for rx, ans in self.YES_NO_RULES:
            if re.search(rx, qtext_clean, re.I):
                if self._click_radio_or_checkbox_in(li, ans):
                    self.record_fill(f"li.application-question[{qtext_clean[:40]}]",
                                     qtext_clean, ans, "click", success=True)
                    return
                # Try common variants
                fallbacks = (["Yes", "Yes, I consent", "Yes, I agree", "I agree",
                              "I confirm", "I acknowledge", "Acknowledge"]
                             if ans == "Yes"
                             else ["No", "No, I do not consent", "No, I do not agree",
                                   "I disagree", "Decline"])
                for fb in fallbacks:
                    if self._click_radio_or_checkbox_in(li, fb):
                        self.record_fill(f"li.application-question[{qtext_clean[:40]}]",
                                         qtext_clean, fb, "click", success=True)
                        return
                break  # matched a rule but couldn't click — move on

        # Free-text question fallbacks
        if re.search(r"how did you hear|how you heard|where did you (first )?hear|"
                     r"how (you|did you) find|tell us how you heard", qtext_clean, re.I):
            ans_text = profile["common_form_answers"]["how_did_you_hear_about_us"]
            # Prefer dropdown selection if this question is a <select>
            if self._select_option_in(li, ans_text, fallbacks=[
                "LinkedIn", "Job Board", "Indeed", "Glassdoor", "Other",
            ]):
                self.record_fill(f"li[{qtext_clean[:40]}]", qtext_clean,
                                 ans_text, "select", success=True)
                return
            if self._fill_text_in(li, ans_text):
                self.record_fill(f"li[{qtext_clean[:40]}]", qtext_clean,
                                 ans_text, "type", success=True)
                return
        if re.search(r"years? of (relevant )?experience|how many years|"
                     r"total years of experience", qtext_clean, re.I):
            ans = (profile.get("experience_summary", {})
                   .get("answer_for_years_of_experience_field") or "3")
            if self._fill_text_in(li, ans):
                self.record_fill(f"li[{qtext_clean[:40]}]", qtext_clean,
                                 ans, "type", success=True)
                return

        # Multi-checkbox: language skills — pick English (most candidates' primary)
        if re.search(r"language\s*(skill|proficien|spoken|fluent|speak)",
                     qtext_clean, re.I):
            for variant in ["English (ENG)", "English"]:
                if self._click_radio_or_checkbox_in(li, variant):
                    self.record_fill(f"li[{qtext_clean[:40]}]", qtext_clean,
                                     variant, "click", success=True)
                    return

        # University / school question — Lever uses a <select> dropdown
        if re.search(r"(which )?(university|school|college).*attend|"
                     r"institution you (currently|last) attended|"
                     r"highest level of education", qtext_clean, re.I):
            edu = profile.get("education", [])
            uni = ""
            if edu:
                first = edu[0] if isinstance(edu, list) else edu
                uni = first.get("school") or first.get("university") or ""
            if uni:
                # Try select first (most common on Lever)
                if self._select_option_in(li, uni, fallbacks=[
                    "Other (School Not Listed)", "Other", "Not Listed",
                ]):
                    # If we picked an "Other" fallback, fill the freetext input
                    self._fill_text_in(li, uni)
                    self.record_fill(f"li[{qtext_clean[:40]}]", qtext_clean,
                                     uni, "select", success=True)
                    return
                # Fallback: radio/label or freetext
                if self._click_radio_or_checkbox_in(li, uni):
                    self.record_fill(f"li[{qtext_clean[:40]}]", qtext_clean,
                                     uni, "click", success=True)
                    return
                if self._fill_text_in(li, uni):
                    self.record_fill(f"li[{qtext_clean[:40]}]", qtext_clean,
                                     uni, "type", success=True)
                    return

        # Open-ended essays / "Why X?" / "favorite project"
        if re.search(r"why (do you want|are you interested|do you want to work)|"
                     r"favorite project|proudest accomplishment|"
                     r"tell us about|describe.*experience|"
                     r"what (excites|interests|motivates) you|"
                     r"what (would|do) you (bring|hope)", qtext_clean, re.I):
            essay = self._boilerplate_essay(qtext_clean, profile)
            if self._fill_text_in(li, essay):
                self.record_fill(f"li[{qtext_clean[:40]}]", qtext_clean,
                                 f"[essay {len(essay)} chars]", "type", success=True)
                return

    def _select_option_in(self, li, target_text: str,
                          fallbacks: List[str] = None) -> bool:
        """Find a <select> in the li and choose the option whose visible text
        matches target_text (case-insensitive contains). If no match, try each
        fallback in order. Returns True if any option was selected."""
        try:
            sel = li.locator("select").first
            if sel.count() == 0:
                return False
            try:
                sel.scroll_into_view_if_needed(timeout=1500)
            except Exception:
                pass
            opts = sel.evaluate("""el => Array.from(el.options).map(o => ({
                value: o.value, text: (o.text || '').trim()
            }))""")
            candidates = [target_text] + (fallbacks or [])
            for cand in candidates:
                cand_low = cand.lower()
                # exact text match first
                for o in opts:
                    if o["text"].lower() == cand_low:
                        try:
                            sel.select_option(value=o["value"], timeout=2000)
                            return True
                        except Exception:
                            try:
                                sel.select_option(label=o["text"], timeout=2000)
                                return True
                            except Exception:
                                pass
                # then contains match
                for o in opts:
                    if cand_low in o["text"].lower() and o["text"]:
                        try:
                            sel.select_option(value=o["value"], timeout=2000)
                            return True
                        except Exception:
                            try:
                                sel.select_option(label=o["text"], timeout=2000)
                                return True
                            except Exception:
                                pass
            return False
        except Exception:
            return False

    def _click_radio_or_checkbox_in(self, li, label_text: str) -> bool:
        """Find a radio/checkbox inside the question whose accessible label
        matches label_text. Tries JS-direct check by value attribute first
        (most reliable for Lever's React-managed forms), then falls back to
        Playwright's getByLabel + label-text matching."""
        # Strategy 0: JS-direct by value attribute (Lever wraps unlabeled
        # inputs in <label> with <span>text</span>; .value attr matches text).
        try:
            ok = li.evaluate(f"""(el) => {{
                const ins = Array.from(el.querySelectorAll('input[type=radio], input[type=checkbox]'));
                let target = ins.find(i => i.value === {label_text!r});
                if (!target) {{
                    target = ins.find(i => (i.value || '').toLowerCase() === {label_text.lower()!r});
                }}
                if (!target) {{
                    target = ins.find(i => (i.value || '').toLowerCase().includes({label_text.lower()!r}));
                }}
                if (!target) return false;
                if (!target.checked) {{
                    target.click();
                }}
                return target.checked;
            }}""")
            if ok:
                return True
        except Exception:
            pass
        # Strategy 1: Playwright's accessible-name resolution
        try:
            target = li.get_by_label(label_text, exact=True).first
            if target.count() > 0:
                try:
                    target.scroll_into_view_if_needed(timeout=1500)
                except Exception:
                    pass
                try:
                    target.check(timeout=2000)
                    return True
                except Exception:
                    # Some labels obscure the input — click the label itself
                    try:
                        target.click(timeout=2000, force=True)
                        return True
                    except Exception:
                        pass
        except Exception:
            pass
        # Strategy 2: case-insensitive exact label text match
        try:
            esc = re.escape(label_text)
            lab = li.locator("label").filter(
                has_text=re.compile(rf"^\s*{esc}\s*$", re.I)
            ).first
            if lab.count() > 0:
                try:
                    lab.scroll_into_view_if_needed(timeout=1500)
                except Exception:
                    pass
                lab.click(timeout=2000, force=True)
                return True
        except Exception:
            pass
        # Strategy 3: substring match on label
        try:
            lab = li.locator(f"label:has-text('{label_text}')").first
            if lab.count() > 0:
                try:
                    lab.scroll_into_view_if_needed(timeout=1500)
                except Exception:
                    pass
                lab.click(timeout=2000, force=True)
                return True
        except Exception:
            pass
        # Strategy 4: input by value attribute via Playwright (catches inputs
        # not yet handled by the JS-direct path due to scoping issues)
        try:
            esc_val = label_text.replace("'", "\\'")
            inp = li.locator(f"input[type='checkbox'][value='{esc_val}'], "
                             f"input[type='radio'][value='{esc_val}']").first
            if inp.count() > 0:
                wrap = inp.locator("xpath=ancestor::label[1]").first
                if wrap.count() > 0:
                    try:
                        wrap.scroll_into_view_if_needed(timeout=1500)
                    except Exception:
                        pass
                    try:
                        wrap.click(timeout=2000, force=True)
                        return True
                    except Exception:
                        pass
                try:
                    inp.evaluate("el => { el.checked = true; "
                                 "el.dispatchEvent(new Event('change', {bubbles:true})); "
                                 "el.dispatchEvent(new Event('click', {bubbles:true})); }")
                    return True
                except Exception:
                    pass
        except Exception:
            pass
        return False

    def _boilerplate_essay(self, qtext: str, profile: Dict[str, Any]) -> str:
        """Generic short paragraph for open-ended essays. PLACEHOLDER —
        upgrade to LLM-generated answers in lever-essay-llm todo."""
        first = profile.get("identity", {}).get("first_name", "")
        cur_title = (profile.get("experience_summary", {})
                     .get("current_title") or "")
        cur_emp = (profile.get("experience_summary", {})
                   .get("current_employer") or "")
        return (
            f"As {cur_title} at {cur_emp}, I have built and shipped products "
            f"that reach millions of users, working closely with engineering, "
            f"design, and research partners. I am drawn to this team's mission "
            f"and would value the chance to contribute to work that meaningfully "
            f"shapes how people interact with technology."
        )

    def _fill_text_in(self, li, value: str) -> bool:
        try:
            inp = li.locator("textarea, input[type='text']").first
            if inp.count() == 0:
                return False
            try:
                inp.scroll_into_view_if_needed(timeout=1500)
            except Exception:
                pass
            try:
                inp.fill(value, timeout=3000)
                return True
            except Exception:
                pass
            try:
                inp.focus(timeout=1500)
                inp.press_sequentially(value, delay=8, timeout=8000)
                return True
            except Exception:
                return False
        except Exception:
            return False

    def _unanswered_required(self, page: Page) -> List[str]:
        """A Lever question is required if its label contains ✱.
        Find each li.application-question whose label has ✱, then check that at
        least one of its inputs has a value or is checked."""
        unanswered: List[str] = []
        items = page.locator("li.application-question").all()
        for li in items:
            try:
                lbl = li.locator(".application-label").first
                if lbl.count() == 0:
                    lbl = li.locator("legend, h3, h4, label").first
                if lbl.count() == 0:
                    continue
                lbl_text = (lbl.inner_text(timeout=400) or "").strip()
                if "✱" not in lbl_text and "*" not in lbl_text:
                    continue
                clean = lbl_text.replace("✱", "").strip()
                # Skip if it's the resume field (we've already uploaded)
                if "resume" in clean.lower() and "attach" in clean.lower():
                    continue
                # Check whether any input under this li has a value / is checked
                has_value = li.evaluate("""el => {
                    const ins = el.querySelectorAll('input, textarea, select');
                    for (const i of ins) {
                        if (i.type === 'hidden') {
                            if (i.value && i.value.trim() && i.value !== '__none__') return true;
                            continue;
                        }
                        if (i.tagName === 'SELECT') {
                            if (i.value && i.value.trim() && !/^select|^choose|^click here/i.test(i.value) &&
                                (i.selectedIndex === undefined || i.selectedIndex > 0)) {
                                return true;
                            }
                            continue;
                        }
                        if (i.type === 'radio' || i.type === 'checkbox') {
                            if (i.checked) return true;
                        } else {
                            if (i.value && i.value.trim()) return true;
                        }
                    }
                    return false;
                }""")
                if not has_value:
                    unanswered.append(clean[:120] or "unknown")
            except Exception:
                continue
        # de-dupe preserving order
        seen = set()
        out = []
        for u in unanswered:
            if u in seen:
                continue
            seen.add(u)
            out.append(u)
        return out
