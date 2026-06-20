"""
Ashby adapter (jobs.ashbyhq.com).

Form structure (learned from Decagon + OpenAI scouts):
  - Click "Apply for this job" navigates to /<jobId>/application and renders
    the form inline (no modal).
  - Each question is wrapped in
      <div class="_fieldEntry_..." data-field-path="<UUID|_systemfield_X>">
        <label class="... _required_..." for="<UUID|_systemfield_X>">QUESTION</label>
        <input|textarea|button(s)|file ...>
      </div>
  - System fields use stable IDs:
      _systemfield_name      (single combined Name; not split into first/last)
      _systemfield_email
      _systemfield_resume    (file input)
      _systemfield_location  (typeahead with role='combobox')
      _systemfield_eeoc_gender / _eeoc_race / _eeoc_veteran_status / _eeoc_disability_status  (radio groups)
  - Custom fields use UUIDs.
  - Yes/No questions render two <button>Yes</button><button>No</button> siblings
    inside a div with class "_yesno_*" plus a hidden checkbox with name=<UUID>.
  - Acknowledgment checkboxes have id ending in "-labeled-checkbox-N" with
    aria-label = the agreement text.
  - EEOC questions are <input type="radio"> with id ending in "-labeled-radio-N".
  - Date pickers are react-datepicker inputs (placeholder "Pick date...");
    typing "MM/DD/YYYY" works.
  - Submit button: button:has-text('Submit Application').

Strategy:
  Iterate every <div class="_fieldEntry_..." data-field-path="..."> on the page,
  grab the label text, dispatch to a handler based on the inner widget type.
  Refuse to submit if any required field is left blank.
"""
from __future__ import annotations

import random
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from playwright.sync_api import Page, TimeoutError as PWTimeout, Locator

from base import BaseApplier, RESUME


class AshbyApplier(BaseApplier):
    ATS_NAME = "ashby"

    # Question-keyword -> Yes/No answer (mirrors greenhouse rules)
    YES_NO_RULES: List[Tuple[str, str]] = [
        (r"sponsorship|visa.*sponsor|sponsor.*visa", "No"),
        (r"authorized.*work|legally.*work|work.*authoriz|right to work|eligible.*work", "Yes"),
        (r"open to relocat|willing to relocat|able to relocat", "Yes"),
        (r"open.*work.*in[- ]?person|on[- ]?site.*office|in.office|in.our.*office|"
         r"office .*(days|three|3|four|4|five|5)|"
         r"hybrid|excited to work in.?office", "Yes"),
        # Location/onsite-availability questions ("Are you able to work from
        # San Francisco?", "Currently based in NYC?"). Default Yes — user is
        # willing to relocate; Strategy 2 in _handle_radio_group picks the
        # "Yes, willing to relocate" option when present.
        (r"able to work from|able to work in|work in[- ]?person from|"
         r"based in .*(san francisco|nyc|new york|seattle|sf|bay area|"
         r"london|toronto|austin|boston|chicago|los angeles|la)|"
         r"currently based in|currently located in|located in", "Yes"),
        (r"previously.*(applied|employed|worked)|interview.*at .* before|"
         r"applied to .* before|interviewed at", "No"),
        (r"background check", "Yes"),
        (r"agree.*(privacy|terms|policy)", "Yes"),
        (r"ai policy|use of ai|generative ai", "Yes"),
        # AI notetaking / transcription consent (Metaview, Otter, Fireflies, etc.)
        (r"ai\s+notetak|notetak|metaview|\botter\b|fireflies|"
         r"ai.*(recording|transcrib)|silently records|transcribe.*interview", "Yes"),
        (r"non[- ]?compete|restrictive (agreement|covenant)|bound by (any )?agreement|"
         r"non[- ]?disclosure", "No"),
        (r"security clearance|active clearance|hold.*clearance", "No"),
        (r"open to obtaining|willing to obtain.*clearance", "No"),
        # Catch-all for "are you over 18", "are you 18 or older"
        (r"\b18\b|over 18|age of majority", "Yes"),
    ]

    # Acknowledgement keywords -> always check the box
    ACK_KEYWORDS = re.compile(
        r"acknowledg|i confirm|i certify|i agree|i hereby|read and understood|"
        r"true and correct|opt[- ]?in|terms",
        re.I,
    )

    # EEOC name-suffix -> default selection text (from profile)
    EEOC_DEFAULTS = {
        "gender": ["Decline to self-identify", "Decline To Self Identify",
                   "I do not want to answer", "Prefer not to say"],
        "race":   ["Decline to self-identify", "Decline To Self Identify",
                   "I do not want to answer"],
        "veteran_status": ["I decline to self-identify for protected veteran status",
                           "Decline to self-identify",
                           "I don't wish to answer"],
        "disability_status": ["I do not want to answer", "I don't wish to answer",
                              "Decline to self-identify"],
    }

    def apply(self, page: Page, profile: Dict[str, Any]) -> None:
        # Track field-paths we successfully answered (DOM probing isn't reliable
        # for React-state widgets like the Yes/No buttons whose hidden checkbox
        # doesn't actually toggle).
        self._answered_paths: set = set()

        page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        self.screenshot(page, "01-landed")

        self._click_apply_if_present(page)
        time.sleep(3)

        # Wait for the application form to render
        try:
            page.wait_for_selector("div[data-field-path], input#_systemfield_name",
                                   timeout=15000)
        except PWTimeout:
            self.note("application form did not render after Apply click")
            self.screenshot(page, "02-no-form")
            return

        self.screenshot(page, "02-form")

        # Iterate each field entry and dispatch
        entries = page.locator("div[data-field-path]").all()
        self.note(f"found {len(entries)} field entries")

        # "Read time" before starting to fill — a real user would scan the
        # form for ~3-8s. Going straight to typing is a strong bot signal.
        time.sleep(random.uniform(3.0, 7.5))

        for idx, entry in enumerate(entries):
            try:
                # Scroll the entry naturally into view before touching it.
                try:
                    entry.scroll_into_view_if_needed(timeout=2000)
                except Exception:
                    pass
                # Brief "look at this question" pause before answering.
                time.sleep(random.uniform(0.5, 1.4))

                self._handle_entry(page, entry, profile)

                # Human-like pause between fields (longer than before to
                # avoid Ashby's anti-spam detection that flagged the
                # 2026-05-04 batch). Real users avg 5-15s/field.
                time.sleep(random.uniform(1.6, 3.6))

                # Occasional "re-read / think" pause every few fields.
                if idx > 0 and random.random() < 0.18:
                    time.sleep(random.uniform(2.0, 5.0))
            except Exception as e:
                # Don't let one bad field abort the whole form
                self.note(f"field handler error: {type(e).__name__}: {e}")

        # Post-fill review pause — real users scroll back up and re-check
        # before submitting.
        time.sleep(random.uniform(2.5, 5.0))

        self.screenshot(page, "03-filled")

        # Refuse to submit if any required field still blank
        unanswered = self._unanswered_required(page)
        if unanswered:
            self.note(f"REFUSING TO SUBMIT — {len(unanswered)} required field(s) still blank")
            self.result.notes.append({"unanswered": unanswered})
            return

        if self.dry_run:
            self.note("dry-run: stopping before submit")
            return

        if self.prep_mode:
            self.note("prep mode: form is filled. NOT clicking submit.")
            return

        # Submit
        submit = page.locator(
            "button:has-text('Submit Application'), button:has-text('Submit application')"
        ).first
        if submit.count() == 0:
            submit = page.locator("button[type='submit']").last
        if submit.count() == 0:
            self.note("submit button not found")
            return
        submit.scroll_into_view_if_needed()
        # Human-like pre-submit: pause, jitter mouse, then click
        time.sleep(random.uniform(2.5, 4.0))
        try:
            box = submit.bounding_box()
            if box:
                # Wander the mouse to the button instead of teleporting
                page.mouse.move(
                    box["x"] + random.uniform(0, box["width"]),
                    box["y"] - random.uniform(80, 200),
                    steps=15,
                )
                time.sleep(random.uniform(0.2, 0.5))
                page.mouse.move(
                    box["x"] + box["width"] / 2 + random.uniform(-10, 10),
                    box["y"] + box["height"] / 2 + random.uniform(-3, 3),
                    steps=10,
                )
                time.sleep(random.uniform(0.3, 0.7))
        except Exception:
            pass
        pre_submit_url = page.url
        submit.click()
        time.sleep(5)
        self.screenshot(page, "04-after-submit")

        self._classify_submission(page, pre_submit_url)

    # ---------------- entry dispatch ----------------

    def _handle_entry(self, page: Page, entry: Locator, profile: Dict[str, Any]) -> None:
        """Dispatch one <div data-field-path=...> based on its inner widget."""
        path = entry.get_attribute("data-field-path") or ""
        # Get the question label (first <label> in the entry)
        try:
            lbl_loc = entry.locator("label").first
            if lbl_loc.count() == 0:
                # No label — could be a nested container; skip.
                return
            label = lbl_loc.inner_text(timeout=1000).strip().rstrip("*").strip()
        except Exception:
            label = path

        def _mark_answered(ok: bool) -> None:
            if ok and path:
                self._answered_paths.add(path)

        # 1. System fields by stable path
        if path == "_systemfield_name":
            full_name = f"{profile['identity']['first_name']} {profile['identity']['last_name']}"
            _mark_answered(self._fill_input(entry.locator("input"), full_name, "name"))
            return

        if path == "_systemfield_email":
            _mark_answered(self._fill_input(entry.locator("input"), profile["contact"]["email"], "email"))
            return

        if path == "_systemfield_resume":
            _mark_answered(self._upload_in_entry(entry, RESUME, "resume"))
            return

        if path == "_systemfield_location":
            loc_str = f"{profile['address']['city']}, {profile['address']['state']}"
            _mark_answered(self._fill_typeahead(page, entry, loc_str, "location"))
            return

        # EEOC radio groups (path is _systemfield_eeoc_gender, ..._race, etc.)
        if path.startswith("_systemfield_eeoc_"):
            suffix = path.replace("_systemfield_eeoc_", "")
            _mark_answered(self._select_eeoc_radio(entry, suffix, label))
            return

        # 2. Phone (custom UUID but type=tel)
        tel = entry.locator("input[type='tel']").first
        if tel.count():
            _mark_answered(self._fill_input(tel, profile["contact"]["phone"], f"phone({label})"))
            return

        # 3. Yes/No buttons
        yes_no_div = entry.locator("div[class*='_yesno_']").first
        if yes_no_div.count():
            answer = self._yes_no_answer(label)
            if answer is None:
                self.note(f"no Yes/No rule for: {label!r}")
                self.record_fill(path, label, "(unanswered)", "yesno",
                                 success=False, error="no-rule")
                return
            _mark_answered(self._click_yes_no(yes_no_div, answer, label))
            return

        # 4. Acknowledgement / labeled checkboxes
        ack_cb = entry.locator("input[type='checkbox'][id*='-labeled-checkbox-']").first
        if ack_cb.count():
            _mark_answered(self._check_ack(entry, label))
            return

        # 5. Date picker (react-datepicker)
        dp = entry.locator(".react-datepicker__input-container input, input[placeholder='Pick date...']").first
        if dp.count():
            _mark_answered(self._fill_date(dp, label))
            return

        # 6. Plain text input
        text_inp = entry.locator("input[type='text'], input[type='email'], input[type='url']").first
        if text_inp.count():
            value = self._answer_text_question(label, profile)
            if value is None:
                self.note(f"no text rule for: {label!r}")
                self.record_fill(path, label, "(skipped)", "text",
                                 success=False, error="no-rule")
                return
            _mark_answered(self._fill_input(text_inp, value, label))
            return

        # 7. Textarea (long-form essay)
        ta = entry.locator("textarea:not([name='g-recaptcha-response'])").first
        if ta.count():
            # We don't have an LLM essay generator wired up; only fill if
            # not required so we don't fabricate answers.
            if self._entry_is_required(entry):
                self.note(f"required textarea unfilled (no LLM yet): {label!r}")
                self.record_fill(path, label, "(blank)", "textarea",
                                 success=False, error="required-essay-needs-llm")
            else:
                self.note(f"optional textarea skipped: {label!r}")
            return

        # 8. File input (non-resume)
        f = entry.locator("input[type='file']").first
        if f.count():
            self.note(f"non-resume file input skipped: {label!r}")
            return

        # 9. Combobox (other typeaheads)
        cb = entry.locator("[role='combobox']").first
        if cb.count():
            value = self._answer_text_question(label, profile)
            if value:
                _mark_answered(self._fill_typeahead(page, entry, value, label))
            else:
                self.note(f"unhandled combobox: {label!r}")
            return

        # 10. Native <select> dropdown
        sel = entry.locator("select").first
        if sel.count():
            answer = self._answer_text_question(label, profile)
            if answer is None:
                answer = self._select_dropdown_default(sel, label)
            if answer:
                _mark_answered(self._fill_select(sel, answer, label))
            else:
                self.note(f"no select rule for: {label!r}")
                self.record_fill(path, label, "(unanswered)", "select",
                                 success=False, error="no-rule")
            return

        # 11. Generic Yes/No fallback — entries that render two plain
        # <button>Yes</button><button>No</button> without the _yesno_ wrapper.
        # Strict: require exactly two visible buttons whose normalized texts
        # are exactly "Yes" and "No".
        yn_buttons = self._collect_yes_no_buttons(entry)
        if yn_buttons is not None:
            answer = self._yes_no_answer(label)
            if answer is None:
                self.note(f"no Yes/No rule for: {label!r}")
                self.record_fill(path, label, "(unanswered)", "yesno-fallback",
                                 success=False, error="no-rule")
                return
            target = yn_buttons[answer]
            try:
                target.scroll_into_view_if_needed(timeout=2000)
                target.click(timeout=3000)
                self.record_fill(label, label, answer, "yesno-fallback", success=True)
                _mark_answered(True)
                time.sleep(0.2)
            except Exception as e:
                self.record_fill(label, label, answer, "yesno-fallback",
                                 success=False, error=str(e)[:200])
            return

        # 12. Generic radio-group fallback. Ashby renders many questions
        # (Yes/No, "How did you hear", demographics) as fieldsets with
        # <input type="radio" id="...-labeled-radio-N"> + sibling labels.
        radios = entry.locator("input[type='radio'][id*='-labeled-radio-']").all()
        if radios:
            answered = self._handle_radio_group(entry, label, radios, profile)
            if answered:
                _mark_answered(True)
            else:
                # Demographic / age questions are usually optional. If the
                # entry isn't required, skip silently (not a failure).
                if not self._entry_is_required(entry):
                    self.note(f"optional radio-group skipped: {label!r}")
                else:
                    options = [self._radio_label_text(entry, r) for r in radios]
                    self.note({"unhandled-radio-group": label, "path": path,
                               "options": options[:8]})
                    self.record_fill(path, label, "(unanswered)", "radio-group",
                                     success=False, error="no-rule")
            return

        # Unhandled — capture targeted diagnostics so future iterations can
        # extend coverage without re-scouting the live form.
        diag = self._diagnose_entry(entry)
        self.note({"unhandled": label, "path": path, "diag": diag})

    # ---------------- field-type handlers ----------------

    def _fill_input(self, loc: Locator, value: str, label: str) -> bool:
        try:
            loc.scroll_into_view_if_needed(timeout=3000)
            loc.click(timeout=3000)
            try:
                loc.fill("", timeout=2000)
            except Exception:
                pass
            loc.press_sequentially(value, delay=70, timeout=20000)
            self.record_fill(label, label, value, "type", success=True)
            return True
        except Exception as e:
            self.record_fill(label, label, value, "type",
                             success=False, error=str(e)[:200])
            return False

    def _upload_in_entry(self, entry: Locator, file_path, label: str) -> bool:
        # Ashby has both visible label-button and hidden <input type=file>.
        # The id=_systemfield_resume is on the hidden file input.
        try:
            f = entry.locator("input[type='file']").first
            if f.count() == 0:
                self.record_fill(label, label, str(file_path), "upload",
                                 success=False, error="no-file-input")
                return False
            f.set_input_files(str(file_path), timeout=10000)
            self.record_fill(label, label, str(file_path), "upload", success=True)
            time.sleep(2)
            return True
        except Exception as e:
            self.record_fill(label, label, str(file_path), "upload",
                             success=False, error=str(e)[:200])
            return False

    def _fill_typeahead(self, page: Page, entry: Locator, value: str, label: str) -> bool:
        """Type a value into a combobox-style typeahead and pick the top option."""
        try:
            inp = entry.locator("input[role='combobox'], input").first
            inp.scroll_into_view_if_needed(timeout=3000)
            inp.click(timeout=3000)
            time.sleep(0.2)
            try:
                inp.fill("", timeout=1500)
            except Exception:
                pass
            inp.press_sequentially(value, delay=80, timeout=12000)
            time.sleep(1.0)
            # Listbox option (Ashby renders options in a popup attached to body)
            option = page.locator("[role='option']").first
            if option.count() and option.is_visible():
                option.click(timeout=3000)
                self.record_fill(label, label, value, "typeahead", success=True)
                return True
            # Fallback: press Enter to commit
            inp.press("Enter")
            self.record_fill(label, label, value, "typeahead-enter", success=True)
            return True
        except Exception as e:
            self.record_fill(label, label, value, "typeahead",
                             success=False, error=str(e)[:200])
            return False

    def _click_yes_no(self, yes_no_div: Locator, answer: str, label: str) -> bool:
        """Click the Yes or No <button> inside a _yesno_* div."""
        try:
            btn = yes_no_div.locator(f"button:has-text('{answer}')").first
            if btn.count() == 0:
                # Some renderings only have one button if pre-selected; bail
                self.record_fill(label, label, answer, "yesno",
                                 success=False, error=f"no-button-{answer}")
                return False
            btn.scroll_into_view_if_needed(timeout=2000)
            btn.click(timeout=3000)
            self.record_fill(label, label, answer, "yesno", success=True)
            time.sleep(0.2)
            return True
        except Exception as e:
            self.record_fill(label, label, answer, "yesno",
                             success=False, error=str(e)[:200])
            return False

    def _check_ack(self, entry: Locator, label: str) -> bool:
        """Check the acknowledgment checkbox (after verifying it's an ack/agreement)."""
        # Be conservative: only auto-check if the label looks like an ack
        # (acknowledgment, certify, agree, etc.). Otherwise leave it.
        full_text = ""
        try:
            full_text = entry.inner_text(timeout=1000)
        except Exception:
            full_text = label
        if not self.ACK_KEYWORDS.search(full_text):
            self.note(f"checkbox doesn't look like an acknowledgement; skipping: {label!r}")
            self.record_fill(label, label, "(unchecked)", "checkbox",
                             success=False, error="not-an-ack")
            return False
        try:
            cb = entry.locator("input[type='checkbox']").first
            cb.scroll_into_view_if_needed(timeout=2000)
            # Click the label or the checkbox itself (label is more reliable)
            lab = entry.locator("label[for*='-labeled-checkbox-']").first
            target = lab if lab.count() else cb
            if not cb.is_checked():
                target.click(timeout=3000)
            self.record_fill(label, label, "checked", "checkbox", success=True)
            return True
        except Exception as e:
            self.record_fill(label, label, "(unchecked)", "checkbox",
                             success=False, error=str(e)[:200])
            return False

    def _fill_date(self, dp: Locator, label: str) -> bool:
        """Fill a react-datepicker text input with a date string."""
        # Default: 2 weeks out
        target = (datetime.now() + timedelta(days=14)).strftime("%m/%d/%Y")
        try:
            dp.scroll_into_view_if_needed(timeout=3000)
            dp.click(timeout=3000)
            try:
                dp.fill("", timeout=1500)
            except Exception:
                pass
            dp.press_sequentially(target, delay=80, timeout=10000)
            dp.press("Escape")  # close the datepicker popup
            self.record_fill(label, label, target, "date", success=True)
            return True
        except Exception as e:
            self.record_fill(label, label, target, "date",
                             success=False, error=str(e)[:200])
            return False

    def _select_eeoc_radio(self, entry: Locator, suffix: str, label: str) -> bool:
        """Select 'Decline to self-identify' (or equivalent) for an EEOC group."""
        candidates = self.EEOC_DEFAULTS.get(suffix, ["Decline to self-identify"])
        radios = entry.locator("input[type='radio']").all()
        # Build label-text -> radio map by walking each radio's <label>
        radio_pairs = []
        for r in radios:
            try:
                rid = r.get_attribute("id") or ""
                lab_text = ""
                if rid:
                    lab = entry.locator(f"label[for='{rid}']").first
                    if lab.count():
                        try:
                            lab_text = lab.inner_text(timeout=500)
                        except Exception:
                            pass
                radio_pairs.append((rid, lab_text, r))
            except Exception:
                continue
        for cand in candidates:
            for rid, lab_text, r in radio_pairs:
                if cand.lower() in (lab_text or "").lower():
                    try:
                        # Click the label rather than the (often hidden) radio
                        if rid:
                            entry.locator(f"label[for='{rid}']").first.click(timeout=3000)
                        else:
                            r.click(timeout=3000)
                        self.record_fill(label, label, cand, "radio", success=True)
                        return True
                    except Exception as e:
                        self.note(f"radio click failed for {cand!r}: {e}")
                        continue
        self.record_fill(label, label, "(unanswered)", "radio",
                         success=False, error="no-decline-option")
        return False

    # ---------------- answer derivation ----------------

    def _yes_no_answer(self, label: str) -> Optional[str]:
        for pat, ans in self.YES_NO_RULES:
            if re.search(pat, label, re.I):
                return ans
        return None

    def _answer_text_question(self, label: str, profile: Dict[str, Any]) -> Optional[str]:
        """Map a free-text question label to a value from the profile."""
        L = label.lower()
        if "linkedin" in L:
            return profile["contact"]["linkedin"]
        if "github" in L:
            return profile["contact"].get("github")
        if "portfolio" in L or "website" in L or "personal site" in L:
            return profile["contact"].get("portfolio_url") or profile["contact"]["linkedin"]
        if "where did you go for college" in L or ("college" in L and "where" in L) \
                or "school" in L or "university" in L or "education" in L:
            return profile["education"]["school"]
        if "currently located" in L or "current location" in L or "where are you located" in L:
            return f"{profile['address']['city']}, {profile['address']['state']}"
        if "phone" in L:
            return profile["contact"]["phone"]
        if "first name" in L:
            return profile["identity"]["first_name"]
        if "last name" in L:
            return profile["identity"]["last_name"]
        if L.strip() == "name" or "full name" in L:
            return f"{profile['identity']['first_name']} {profile['identity']['last_name']}"
        if "how did you hear" in L or "how did you find out" in L or "referral" in L:
            return "LinkedIn"
        if "current company" in L or "current employer" in L \
                or "most recent employer" in L or "previous employer" in L \
                or "recent employer" in L \
                or ("employer" in L and ("current" in L or "recent" in L)):
            return profile["experience_summary"]["current_employer"]
        if "current title" in L or "current role" in L:
            return profile["experience_summary"]["current_title"]
        if "years of experience" in L or "years experience" in L:
            return profile["experience_summary"]["answer_for_years_of_experience_field"]
        if "salary" in L or "compensation" in L:
            return "Open to discuss"
        if "start date" in L or "when can you start" in L or "earliest start" in L:
            return "Two weeks from offer"
        if "preferred name" in L or "go by" in L:
            return profile["identity"]["preferred_name"]
        if "pronoun" in L:
            return ""  # leave blank if the field expects free text
        # Conditional "If you selected Other, please specify / provide
        # additional details" follow-ups. We never select 'Other' in the
        # primary question, so the right value here is N/A. This silences
        # the "no text rule for" note and keeps the form clean.
        if (("if you" in L or "if selected" in L) and
                ("other" in L or "yes" in L or "additional details" in L)
                and ("please" in L or "specify" in L or "details" in L
                     or "explain" in L or "provide" in L or "elaborat" in L)):
            return "N/A"
        return None

    # ---------------- structural helpers ----------------

    def _click_apply_if_present(self, page: Page) -> None:
        for sel in [
            "button:has-text('Apply for this job')",
            "a:has-text('Apply for this job')",
            "button:has-text('Apply')",
            "a:has-text('Apply')",
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

    def _entry_is_required(self, entry: Locator) -> bool:
        """An Ashby field is required if its label has the _required_ class."""
        try:
            lab = entry.locator("label").first
            if lab.count() == 0:
                return False
            cls = lab.get_attribute("class") or ""
            return "_required_" in cls
        except Exception:
            return False

    def _entry_label(self, entry: Locator) -> str:
        try:
            return entry.locator("label").first.inner_text(timeout=500).strip().rstrip("*").strip()
        except Exception:
            return entry.get_attribute("data-field-path") or ""

    def _entry_has_value(self, entry: Locator) -> bool:
        """True if the entry's main widget appears to have a value/selection."""
        try:
            # Text/email/tel/url inputs, plus typeahead inputs
            for inp in entry.locator(
                "input[type='text'], input[type='email'], input[type='tel'], "
                "input[type='url'], input[role='combobox']"
            ).all():
                v = (inp.input_value(timeout=500) or "").strip()
                if v:
                    return True
            # File input — Ashby renders the chosen filename inside the entry
            for f in entry.locator("input[type='file']").all():
                # Look for a filename element rendered after upload (e.g. _filename_)
                pass
            try:
                etext = entry.inner_text(timeout=500)
                if re.search(r"\.(pdf|docx?|odt|rtf)\b", etext, re.I):
                    return True
            except Exception:
                pass
            # Yes/No: hidden checkbox flips to checked when an answer is selected
            for cb in entry.locator("input[type='checkbox']").all():
                try:
                    if cb.is_checked():
                        return True
                except Exception:
                    pass
            # Radio: any radio in the group checked
            for r in entry.locator("input[type='radio']").all():
                try:
                    if r.is_checked():
                        return True
                except Exception:
                    pass
            # Textarea
            for ta in entry.locator("textarea:not([name='g-recaptcha-response'])").all():
                v = (ta.input_value(timeout=500) or "").strip()
                if v:
                    return True
            return False
        except Exception:
            return False

    def _unanswered_required(self, page: Page) -> List[str]:
        unanswered = []
        for entry in page.locator("div[data-field-path]").all():
            try:
                if not self._entry_is_required(entry):
                    continue
                path = entry.get_attribute("data-field-path") or ""
                # Trust our internal "answered" set first (DOM probing isn't
                # reliable for React-state widgets like Yes/No buttons).
                if path in self._answered_paths:
                    continue
                if self._entry_has_value(entry):
                    continue
                unanswered.append(self._entry_label(entry))
            except Exception:
                continue
        return unanswered

    # ---------------- new fallbacks (verification-first) ----------------

    def _collect_yes_no_buttons(self, entry: Locator) -> Optional[Dict[str, Locator]]:
        """Return {'Yes': loc, 'No': loc} only if entry has exactly two
        visible buttons whose normalized texts are exactly Yes/No.
        Returns None otherwise (so caller can fall through to "unhandled")."""
        try:
            buttons = entry.locator("button").all()
            yes_btns: List[Locator] = []
            no_btns: List[Locator] = []
            other_visible = 0
            for b in buttons:
                try:
                    if not b.is_visible():
                        continue
                    txt = (b.text_content() or "").strip().lower()
                    if txt == "yes":
                        yes_btns.append(b)
                    elif txt == "no":
                        no_btns.append(b)
                    else:
                        other_visible += 1
                except Exception:
                    continue
            # Require exactly one visible Yes, one visible No, no other visible
            # buttons in the entry. This avoids false-positives on entries that
            # contain auxiliary buttons (eg "Choose file", "Add another").
            if len(yes_btns) == 1 and len(no_btns) == 1 and other_visible == 0:
                return {"Yes": yes_btns[0], "No": no_btns[0]}
            return None
        except Exception:
            return None

    def _select_dropdown_default(self, sel: Locator, label: str) -> Optional[str]:
        """Pick a sensible default for a native <select>. For demographic
        questions return a Decline/Prefer-not option if present; otherwise
        return None so the caller marks it unanswered (don't pick arbitrary)."""
        L = label.lower()
        is_demographic = bool(re.search(
            r"gender|transgender|sexual orientation|orientation|"
            r"race|ethnic|hispanic|latino|veteran|disability|"
            r"\bage\b|date of birth|dob",
            L,
        ))
        try:
            opts = sel.locator("option").all()
            opt_texts: List[str] = []
            for o in opts:
                try:
                    t = (o.text_content() or "").strip()
                    v = o.get_attribute("value") or ""
                    if t and v:
                        opt_texts.append(t)
                except Exception:
                    continue
        except Exception:
            opt_texts = []
        if is_demographic:
            for cand in (
                "Decline to self-identify",
                "Decline To Self Identify",
                "I do not want to answer",
                "I don't wish to answer",
                "Prefer not to say",
                "Prefer Not To Say",
                "Prefer not to disclose",
                "Decline to answer",
            ):
                for t in opt_texts:
                    if cand.lower() in t.lower():
                        return t
            return None
        return None

    def _fill_select(self, sel: Locator, value: str, label: str) -> bool:
        """Select an option in a native <select>. Verify postcondition
        (input_value() returns a non-empty value matching the label or value).
        Returns False on any verification failure."""
        try:
            sel.scroll_into_view_if_needed(timeout=3000)
            try:
                sel.select_option(label=value, timeout=3000)
            except Exception:
                # Retry: try matching by visible text in option list
                opts = sel.locator("option").all()
                matched_value: Optional[str] = None
                for o in opts:
                    try:
                        t = (o.text_content() or "").strip()
                        if t.lower() == value.lower() or value.lower() in t.lower():
                            matched_value = o.get_attribute("value")
                            if matched_value:
                                break
                    except Exception:
                        continue
                if matched_value is None:
                    self.record_fill(label, label, value, "select",
                                     success=False, error="no-matching-option")
                    return False
                sel.select_option(value=matched_value, timeout=3000)
            # Verify postcondition
            try:
                cur = (sel.input_value(timeout=1000) or "").strip()
            except Exception:
                cur = ""
            if not cur:
                self.record_fill(label, label, value, "select",
                                 success=False, error="select-postcheck-empty")
                return False
            self.record_fill(label, label, value, "select", success=True)
            return True
        except Exception as e:
            self.record_fill(label, label, value, "select",
                             success=False, error=str(e)[:200])
            return False

    # ---------------- generic radio-group handler ----------------

    def _radio_pairs(self, entry: Locator,
                     radios: List[Locator]) -> List[Tuple[str, str, Locator]]:
        """Build (radio_id, label_text, locator) tuples for a radio group."""
        pairs: List[Tuple[str, str, Locator]] = []
        for r in radios:
            try:
                rid = r.get_attribute("id") or ""
                lab_text = ""
                if rid:
                    lab = entry.locator(f"label[for='{rid}']").first
                    if lab.count():
                        try:
                            lab_text = (lab.inner_text(timeout=500) or "").strip()
                        except Exception:
                            lab_text = ""
                pairs.append((rid, lab_text, r))
            except Exception:
                continue
        return pairs

    def _radio_label_text(self, entry: Locator, r: Locator) -> str:
        try:
            rid = r.get_attribute("id") or ""
            if rid:
                lab = entry.locator(f"label[for='{rid}']").first
                if lab.count():
                    return (lab.inner_text(timeout=500) or "").strip()
        except Exception:
            pass
        return ""

    def _click_radio_by_id(self, entry: Locator, rid: str,
                           label: str, value_for_log: str) -> bool:
        """Click the <label for=rid> and verify the radio is checked.
        Returns False on any verification failure."""
        if not rid:
            return False
        try:
            lab = entry.locator(f"label[for='{rid}']").first
            if lab.count() == 0:
                self.record_fill(label, label, value_for_log, "radio",
                                 success=False, error="no-label-for-rid")
                return False
            lab.click(timeout=3000)
            time.sleep(0.15)
            radio = entry.locator(f"input[type='radio'][id='{rid}']").first
            try:
                if radio.count() and radio.is_checked():
                    self.record_fill(label, label, value_for_log, "radio",
                                     success=True)
                    return True
            except Exception:
                pass
            # is_checked may return False for hidden/styled radios that DO
            # carry state via a parent class. As a soft check, see if any
            # radio in the group is now checked AND it has the same id.
            try:
                if radio.count():
                    state = radio.evaluate("el => el.checked")
                    if state:
                        self.record_fill(label, label, value_for_log, "radio",
                                         success=True)
                        return True
            except Exception:
                pass
            self.record_fill(label, label, value_for_log, "radio",
                             success=False, error="not-checked-after-click")
            return False
        except Exception as e:
            self.record_fill(label, label, value_for_log, "radio",
                             success=False, error=str(e)[:200])
            return False

    def _handle_radio_group(self, entry: Locator, label: str,
                            radios: List[Locator],
                            profile: Dict[str, Any]) -> bool:
        """Generic radio-group answerer. Returns True iff a radio was clicked
        AND verified checked. Strategies tried in order:
          1. Pure Yes/No (exactly two options)
          2. Yes/No with prefixed options (eg "Yes, and I currently...")
          3. Text answer derived from profile (fuzzy match against options)
          4. Demographic decline option (if label is demographic-flavored)
        """
        pairs = self._radio_pairs(entry, radios)
        if not pairs:
            return False
        L = label.lower()
        texts_lc = [(p[1] or "").strip().lower() for p in pairs]

        # Strategy 1: exact Yes/No (2 options)
        if (len(pairs) == 2
                and "yes" in texts_lc and "no" in texts_lc):
            ans = self._yes_no_answer(label)
            if ans:
                target = next(((rid, lt) for rid, lt, _ in pairs
                               if (lt or "").strip().lower() == ans.lower()),
                              None)
                if target:
                    if self._click_radio_by_id(entry, target[0], label, ans):
                        return True

        # Strategy 2: Yes/No with prefixed options ("Yes, and I currently...",
        # "No, but I would consider relocating", etc.)
        if len(pairs) >= 2:
            ans = self._yes_no_answer(label)
            if ans:
                ans_lc = ans.lower()
                # 2a: When Yes is the answer and multiple Yes-prefixed options
                # exist (eg "Yes, I currently live here" vs "Yes, willing to
                # relocate"), disambiguate using profile signals.
                if ans_lc == "yes":
                    yes_opts = [(rid, lt) for rid, lt, _ in pairs
                                if (lt or "").strip().lower().startswith("yes")]
                    if len(yes_opts) >= 2:
                        prefs = (profile.get("preferences", {}) or {})
                        addr = (profile.get("address", {}) or {})
                        user_city = (addr.get("city") or "").strip().lower()
                        user_state = (addr.get("state") or "").strip().lower()
                        L_lc = L
                        # Detect what city the question is about
                        asked_city = None
                        for c in ("san francisco", "sf", "bay area", "new york",
                                  "nyc", "seattle", "boston", "austin",
                                  "chicago", "los angeles", "london",
                                  "toronto"):
                            if c in L_lc:
                                asked_city = c
                                break
                        # If user is already in the asked city, prefer "currently
                        # live" / "currently based" option.
                        already_there = False
                        if asked_city:
                            if asked_city in user_city:
                                already_there = True
                            # Bay area shortcut: SF/Oakland/Berkeley/etc.
                            if asked_city in ("san francisco", "sf", "bay area"):
                                if any(t in user_city for t in (
                                        "san francisco", "oakland", "berkeley",
                                        "san jose", "palo alto", "mountain view",
                                        "sunnyvale", "redwood city")):
                                    already_there = True
                        already_there_opt = None
                        relocate_opt = None
                        for rid, lt in yes_opts:
                            lt_lc = (lt or "").lower()
                            if any(p in lt_lc for p in (
                                    "currently live", "currently based",
                                    "i live", "i am based", "live here",
                                    "based here")):
                                already_there_opt = (rid, lt)
                            if "relocat" in lt_lc:
                                relocate_opt = (rid, lt)
                        wt_relocate = str(prefs.get(
                            "willing_to_relocate", "")).lower().startswith("yes")
                        target = None
                        if already_there and already_there_opt:
                            target = already_there_opt
                        elif relocate_opt and wt_relocate:
                            target = relocate_opt
                        elif already_there_opt and not relocate_opt:
                            target = already_there_opt
                        if target:
                            if self._click_radio_by_id(entry, target[0],
                                                       label, target[1]):
                                return True

                # 2b: Standard prefix match (Yes / No / Yes, ... / No, ...)
                target = None
                for rid, lt, _ in pairs:
                    lt_lc = (lt or "").strip().lower()
                    if (lt_lc == ans_lc
                            or lt_lc.startswith(ans_lc + ",")
                            or lt_lc.startswith(ans_lc + " ")
                            or lt_lc.split(",", 1)[0].strip() == ans_lc):
                        target = (rid, lt)
                        break
                if target:
                    if self._click_radio_by_id(entry, target[0], label, ans):
                        return True

        # Strategy 3: profile-derived text answer (fuzzy match labels)
        text_ans = self._answer_text_question(label, profile)
        if text_ans:
            ta_lc = text_ans.strip().lower()
            for tactic in ("exact", "starts_with", "contains"):
                for rid, lt, _ in pairs:
                    lt_lc = (lt or "").strip().lower()
                    if not lt_lc:
                        continue
                    matched = False
                    if tactic == "exact" and lt_lc == ta_lc:
                        matched = True
                    elif tactic == "starts_with" and lt_lc.startswith(ta_lc):
                        matched = True
                    elif tactic == "contains" and ta_lc in lt_lc:
                        matched = True
                    if matched:
                        if self._click_radio_by_id(entry, rid, label, text_ans):
                            return True
                        break  # don't try other tactics for this text answer

        # Strategy 4: demographic decline option
        is_demographic = bool(re.search(
            r"gender|transgender|sexual orientation|orientation|"
            r"race|ethnic|hispanic|latino|veteran|disability|"
            r"\bage\b|date of birth|\bdob\b",
            L,
        ))
        if is_demographic:
            for cand in (
                "decline to self-identify",
                "decline to self identify",
                "i do not want to answer",
                "i don't wish to answer",
                "prefer not to say",
                "prefer not to disclose",
                "decline to answer",
                "prefer not to answer",
            ):
                for rid, lt, _ in pairs:
                    lt_lc = (lt or "").strip().lower()
                    if cand in lt_lc:
                        if self._click_radio_by_id(entry, rid, label, lt):
                            return True

        return False

    def _diagnose_entry(self, entry: Locator) -> Dict[str, Any]:
        """Capture targeted (not full-blob) diagnostics for an unhandled entry.
        Helps iterate dispatcher coverage without re-scouting forms."""
        diag: Dict[str, Any] = {}
        try:
            input_types: List[str] = []
            for inp in entry.locator("input").all():
                try:
                    t = inp.get_attribute("type") or ""
                    if t:
                        input_types.append(t)
                except Exception:
                    continue
            diag["input_types"] = input_types
        except Exception:
            pass
        try:
            btn_texts: List[str] = []
            for b in entry.locator("button").all():
                try:
                    if b.is_visible():
                        bt = (b.text_content() or "").strip()
                        if bt:
                            btn_texts.append(bt[:40])
                except Exception:
                    continue
            diag["button_texts"] = btn_texts[:8]
        except Exception:
            pass
        try:
            select_options: List[str] = []
            for s in entry.locator("select").all():
                for o in s.locator("option").all():
                    try:
                        t = (o.text_content() or "").strip()
                        if t:
                            select_options.append(t[:40])
                    except Exception:
                        continue
            diag["select_options"] = select_options[:10]
        except Exception:
            pass
        try:
            roles: List[str] = []
            for el in entry.locator("[role]").all():
                try:
                    r = el.get_attribute("role") or ""
                    if r and r not in roles:
                        roles.append(r)
                except Exception:
                    continue
            diag["roles"] = roles[:6]
        except Exception:
            pass
        try:
            html = entry.evaluate("el => el.outerHTML")
            if isinstance(html, str):
                # Strip our resume filename + name/email if they appear.
                # Truncate to keep result.json small.
                diag["outer_html_excerpt"] = html[:1500]
        except Exception:
            pass
        return diag

    # ---------------- submission classification (tiered) ----------------

    CONFIRMATION_PHRASES = (
        "thank you for applying", "thank you for your application",
        "thank you for your interest", "thanks for applying",
        "we've received", "we have received", "application received",
        "application was received", "your application was received",
        "successfully submitted", "your application has been",
        "application was submitted", "submission was successful",
        "we'll be in touch", "we will be in touch",
        "we'll review", "we will review",
        "you've successfully applied", "you have successfully applied",
        "application complete", "application has been submitted",
        "application sent", "we've got it",
    )

    URL_SUCCESS_HINTS = (
        "/submitted", "/thanks", "/thank", "/confirmation",
        "/complete", "/success", "/applied", "/sent",
    )

    VALIDATION_ERROR_PHRASES = (
        "please correct", "required field", "this field is required",
        "please fill", "please enter", "please select",
        "please complete", "must be answered",
    )

    # Hard-rejection phrases used by Ashby when the submission is blocked
    # (anti-spam, duplicate, captcha-fail, etc.). Distinct from validation
    # errors so the run is clearly logged as a rejection rather than a
    # silent "no confirmation matched".
    REJECTION_PHRASES = (
        "we couldn't submit your application",
        "we could not submit your application",
        "flagged as possible spam",
        "submission was flagged",
        "please submit your application again",
        "unable to submit your application",
        "you have already applied",
        "duplicate application",
    )

    CAP_EXCEEDED_PHRASES = (
        "limits for applications across roles",
        "may not apply more than",
        "180 day span",
        "180 days have passed",
        "maximum number of applications",
        "exceeded the application limit",
    )

    SPAM_FLAGGED_PHRASES = (
        "flagged as possible spam",
        "submission was flagged",
        "please submit your application again",
    )

    DUPLICATE_PHRASES = (
        "you have already applied",
        "duplicate application",
        "already submitted an application",
    )

    def _classify_submission(self, page: Page, pre_submit_url: str) -> None:
        """Tiered confirmation check. Order: URL change > form removal >
        body phrases. Negative checks (validation errors, form still present,
        rejection banners) veto a positive classification."""
        post_url = page.url
        url_changed = post_url != pre_submit_url
        url_hit = any(h in post_url.lower() for h in self.URL_SUCCESS_HINTS)

        try:
            form_still_present = page.locator("div[data-field-path]").count() > 0
        except Exception:
            form_still_present = True

        try:
            submit_still_present = page.locator(
                "button:has-text('Submit Application'), "
                "button:has-text('Submit application')"
            ).count() > 0
        except Exception:
            submit_still_present = True

        try:
            body = page.locator("body").inner_text(timeout=5000).lower()
        except Exception:
            body = ""

        body_phrase_hit = any(p in body for p in self.CONFIRMATION_PHRASES)
        validation_visible = any(p in body for p in self.VALIDATION_ERROR_PHRASES)
        rejection_phrase = next(
            (p for p in self.REJECTION_PHRASES if p in body), None
        )

        signals = {
            "pre_url": pre_submit_url,
            "post_url": post_url,
            "url_changed": url_changed,
            "url_success_hint": url_hit,
            "form_still_present": form_still_present,
            "submit_still_present": submit_still_present,
            "body_phrase_hit": body_phrase_hit,
            "validation_visible": validation_visible,
            "rejection_phrase": rejection_phrase,
        }

        if rejection_phrase:
            self.result.submitted = False
            if any(p in body for p in self.CAP_EXCEEDED_PHRASES):
                kind = "cap_exceeded"
            elif any(p in body for p in self.SPAM_FLAGGED_PHRASES):
                kind = "spam_rejected"
            elif any(p in body for p in self.DUPLICATE_PHRASES):
                kind = "duplicate"
            else:
                kind = "rejected"
            self.note(f"SUBMISSION REJECTED ({kind}): '{rejection_phrase}'")
            self.note({"submission_signals": signals,
                       "rejection_kind": kind})
            return

        # Strong positive: URL hint OR (url_changed AND form gone)
        strong_positive = url_hit or (url_changed and not form_still_present)
        # Medium positive: body phrase + form gone (no validation errors)
        medium_positive = (
            body_phrase_hit
            and not form_still_present
            and not validation_visible
        )
        # Veto: validation errors OR form+submit still present
        vetoed = validation_visible or (form_still_present and submit_still_present)

        if (strong_positive or medium_positive) and not vetoed:
            self.result.submitted = True
            tier = "url-strong" if url_hit else (
                "url+form-gone" if (url_changed and not form_still_present)
                else "body+form-gone"
            )
            self.note(f"submission confirmed ({tier})")
            self.note({"submission_signals": signals})
            return

        # No confirmation — log signals for diagnosis
        # Capture a sanitized body excerpt (first 500 chars) for triage.
        body_excerpt = body[:500] if body else ""
        self.note("submit clicked but no confirmation matched; review screenshots")
        self.note({"submission_signals": signals, "body_excerpt": body_excerpt})
