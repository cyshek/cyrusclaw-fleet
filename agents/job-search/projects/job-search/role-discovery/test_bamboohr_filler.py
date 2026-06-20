"""Unit tests for bamboohr_filler.

Covers:
- parse_bamboohr_url (careers/<id>, /jobs/view.php, /jobs/embed2.php, malformed)
- canonical_apply_url
- build_plan (default field_ids, override, dropdowns, yesno, files, extras)
- emit_steps (presence/order of steps, payload shape, captcha gating)
- end-to-end on the Uphold 1023 smoke spec
- recaptcha_v2 added to capsolver_client
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bamboohr_filler as bf


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

class TestParseUrl:
    def test_careers_canonical(self):
        assert bf.parse_bamboohr_url("https://uphold.bamboohr.com/careers/839") == ("uphold", "839")

    def test_careers_trailing_slash(self):
        assert bf.parse_bamboohr_url("https://acme.bamboohr.com/careers/42/") == ("acme", "42")

    def test_view_php(self):
        assert bf.parse_bamboohr_url("https://x.bamboohr.com/jobs/view.php?id=99") == ("x", "99")

    def test_embed2_php(self):
        assert bf.parse_bamboohr_url("https://x.bamboohr.com/jobs/embed2.php?id=123") == ("x", "123")

    def test_with_query(self):
        assert bf.parse_bamboohr_url(
            "https://uphold.bamboohr.com/careers/839?utm=foo") == ("uphold", "839")

    def test_subdomain_with_dashes(self):
        assert bf.parse_bamboohr_url(
            "https://acme-corp.bamboohr.com/careers/7") == ("acme-corp", "7")

    def test_wrong_host(self):
        assert bf.parse_bamboohr_url("https://uphold.com/careers/839") is None

    def test_no_id(self):
        assert bf.parse_bamboohr_url("https://x.bamboohr.com/careers/") is None

    def test_view_php_no_id_param(self):
        assert bf.parse_bamboohr_url("https://x.bamboohr.com/jobs/view.php?foo=bar") is None

    def test_empty(self):
        assert bf.parse_bamboohr_url("") is None
        assert bf.parse_bamboohr_url(None) is None

    def test_canonical_apply_url(self):
        assert bf.canonical_apply_url("uphold", "839") == \
            "https://uphold.bamboohr.com/careers/839"


# ---------------------------------------------------------------------------
# build_plan
# ---------------------------------------------------------------------------

class TestBuildPlan:
    BASE_SPEC = {
        "role_url": "https://uphold.bamboohr.com/careers/839",
        "answers": {
            "first_name": "Cyrus",
            "last_name": "Yari",
            "email": "x@y.com",
            "phone": "+1 415 555 1234",
            "street": "1 Main",
            "city": "Kirkland",
            "state": "Washington",
            "zip": "98033",
            "desired_pay": "150000",
            "linkedin": "https://linkedin.com/in/x",
            "resume_path": "/r.pdf",
        },
    }

    def test_text_fields_use_default_ids(self):
        plan = bf.build_plan(self.BASE_SPEC)
        tf = plan["text_fields"]
        assert tf["firstName"] == "Cyrus"
        assert tf["lastName"] == "Yari"
        assert tf["email"] == "x@y.com"
        assert tf["phone"] == "+1 415 555 1234"
        assert tf["addressStreet1"] == "1 Main"
        assert tf["addressCity"] == "Kirkland"
        assert tf["addressZip"] == "98033"
        assert tf["desiredPay"] == "150000"
        assert tf["linkedinUrl"] == "https://linkedin.com/in/x"

    def test_state_becomes_dropdown(self):
        plan = bf.build_plan(self.BASE_SPEC)
        prefixes = [d["label_prefix"] for d in plan["dropdowns"]]
        assert "State" in prefixes
        state = next(d for d in plan["dropdowns"] if d["label_prefix"] == "State")
        assert state["option_text"] == "Washington"

    def test_country_becomes_dropdown(self):
        spec = dict(self.BASE_SPEC)
        spec["answers"] = dict(spec["answers"], country="United States")
        plan = bf.build_plan(spec)
        prefixes = [d["label_prefix"] for d in plan["dropdowns"]]
        assert "State" in prefixes
        assert "Country" in prefixes

    def test_explicit_dropdowns_take_priority(self):
        spec = dict(self.BASE_SPEC)
        spec["answers"] = dict(spec["answers"],
                               dropdowns=[{"label_prefix": "State", "option_text": "WA"}])
        plan = bf.build_plan(spec)
        # explicit "State" wins; auto-add suppressed
        state_picks = [d for d in plan["dropdowns"] if d["label_prefix"] == "State"]
        assert len(state_picks) == 1
        assert state_picks[0]["option_text"] == "WA"

    def test_yesno_questions_passthrough(self):
        spec = dict(self.BASE_SPEC)
        spec["answers"] = dict(
            spec["answers"],
            yesno_questions=[
                {"question_text": "Authorized?", "answer": "Yes"},
                {"question_text": "Sponsor?", "answer": "No"},
            ])
        plan = bf.build_plan(spec)
        assert len(plan["yesno_questions"]) == 2
        assert plan["yesno_questions"][0]["answer"] == "Yes"

    def test_yesno_skips_incomplete(self):
        spec = dict(self.BASE_SPEC)
        spec["answers"] = dict(spec["answers"],
                               yesno_questions=[{"question_text": "Q?", "answer": ""},
                                                {"question_text": "", "answer": "Yes"}])
        plan = bf.build_plan(spec)
        assert plan["yesno_questions"] == []

    def test_field_ids_override(self):
        spec = dict(self.BASE_SPEC)
        spec["field_ids"] = {"first_name": "applicantFirstName"}
        plan = bf.build_plan(spec)
        assert plan["text_fields"]["applicantFirstName"] == "Cyrus"
        assert "firstName" not in plan["text_fields"]

    def test_extra_text_fields_passthrough(self):
        spec = dict(self.BASE_SPEC)
        spec["answers"] = dict(spec["answers"],
                               extra_text_fields={"someCustomField": "value"})
        plan = bf.build_plan(spec)
        assert plan["text_fields"]["someCustomField"] == "value"

    def test_empty_values_filtered(self):
        spec = dict(self.BASE_SPEC)
        spec["answers"] = dict(spec["answers"], phone="", desired_pay=None)
        plan = bf.build_plan(spec)
        assert "phone" not in plan["text_fields"]
        assert "desiredPay" not in plan["text_fields"]

    def test_resume_and_cover_letter(self):
        spec = dict(self.BASE_SPEC)
        spec["answers"] = dict(spec["answers"], cover_letter_path="/c.pdf")
        plan = bf.build_plan(spec)
        assert plan["resume_path"] == "/r.pdf"
        assert plan["cover_letter_path"] == "/c.pdf"

    def test_url_normalized_to_careers_canonical(self):
        spec = dict(self.BASE_SPEC,
                    role_url="https://uphold.bamboohr.com/jobs/view.php?id=839")
        plan = bf.build_plan(spec)
        assert plan["url"] == "https://uphold.bamboohr.com/careers/839"
        assert plan["tenant"] == "uphold"
        assert plan["job_id"] == "839"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="not a recognized"):
            bf.build_plan({"role_url": "https://greenhouse.io/x/jobs/1"})


# ---------------------------------------------------------------------------
# emit_steps
# ---------------------------------------------------------------------------

class TestEmitSteps:
    def _plan(self, **answers_overrides):
        ans = {
            "first_name": "C", "last_name": "Y", "email": "a@b.c",
            "state": "Washington", "resume_path": "/r.pdf",
            "yesno_questions": [{"question_text": "Auth?", "answer": "Yes"}],
        }
        ans.update(answers_overrides)
        return bf.build_plan({
            "role_url": "https://uphold.bamboohr.com/careers/839",
            "answers": ans,
        })

    def test_first_step_is_open(self):
        steps = bf.emit_steps(self._plan(), label="uphold")
        assert steps[0]["tool"] == "browser.open"
        assert steps[0]["args"]["url"] == "https://uphold.bamboohr.com/careers/839"
        assert steps[0]["args"]["label"] == "uphold"

    def test_second_step_is_sleep(self):
        steps = bf.emit_steps(self._plan())
        assert steps[1]["tool"] == "sleep"

    def test_includes_text_fill_step(self):
        steps = bf.emit_steps(self._plan())
        tools = [s["tool"] for s in steps]
        assert "browser.act.evaluate" in tools
        # First evaluate after sleep is the text-fill step
        text_step = next(s for s in steps if s["tool"] == "browser.act.evaluate"
                         and "Fill all native text" in s["args"].get("comment", ""))
        assert "firstName" in text_step["args"]["fn"]

    def test_includes_upload_step(self):
        steps = bf.emit_steps(self._plan())
        upload = [s for s in steps if s["tool"] == "bamboohr.upload_files"]
        assert len(upload) == 1
        assert upload[0]["args"]["resume_path"] == "/r.pdf"
        assert upload[0]["args"]["cover_letter_path"] is None

    def test_skips_upload_when_no_files(self):
        plan = self._plan(resume_path=None)
        steps = bf.emit_steps(plan)
        assert not any(s["tool"] == "bamboohr.upload_files" for s in steps)

    def test_includes_dropdown_step(self):
        steps = bf.emit_steps(self._plan())
        dd = [s for s in steps if s["tool"] == "browser.act.evaluate"
              and "MenuVessel" in s["args"].get("comment", "")]
        assert len(dd) == 1
        # Payload should contain Washington
        assert "Washington" in dd[0]["args"]["fn"]

    def test_skips_dropdown_step_when_no_dropdowns(self):
        plan = self._plan(state=None)
        steps = bf.emit_steps(plan)
        assert not any(s["tool"] == "browser.act.evaluate"
                       and "MenuVessel" in s["args"].get("comment", "")
                       for s in steps)

    def test_includes_yesno_step(self):
        steps = bf.emit_steps(self._plan())
        yn = [s for s in steps if s["tool"] == "browser.act.evaluate"
              and "Yes/No" in s["args"].get("comment", "")]
        assert len(yn) == 1
        assert "Auth?" in yn[0]["args"]["fn"]

    def test_captcha_detect_and_solve_steps_always_present(self):
        steps = bf.emit_steps(self._plan())
        tools = [s["tool"] for s in steps]
        assert "bamboohr.solve_recaptcha_v2" in tools
        solve = next(s for s in steps if s["tool"] == "bamboohr.solve_recaptcha_v2")
        assert solve["args"]["driver_exec"]["gate_env"] == "ENABLE_CAPSOLVER"
        assert solve["args"]["driver_exec"]["function"] == "recaptcha_v2"
        assert "g-recaptcha-response" in solve["args"]["inject_fn"]

    def test_verify_then_submit_at_end(self):
        steps = bf.emit_steps(self._plan())
        # Find verify and submit positions
        verify_idx = max(i for i, s in enumerate(steps)
                         if s["tool"] == "browser.act.evaluate"
                         and "Pre-submit verify" in s["args"].get("comment", ""))
        submit_idx = max(i for i, s in enumerate(steps)
                         if s["tool"] == "browser.act.evaluate"
                         and s["args"].get("meta", {}).get("final_submit"))
        assert verify_idx < submit_idx
        assert submit_idx == len(steps) - 1

    def test_step_payload_is_valid_json_in_fn(self):
        # Make sure the wrapped fn embeds JSON-serialized payload that survives
        # round-trip parsing of the front matter.
        plan = self._plan()
        steps = bf.emit_steps(plan)
        text_step = next(s for s in steps
                         if s["tool"] == "browser.act.evaluate"
                         and "Fill all native text" in s["args"].get("comment", ""))
        fn = text_step["args"]["fn"]
        # Extract the JSON between "= " and "; return "
        start = fn.index("= ") + 2
        end = fn.index("; return ")
        payload = json.loads(fn[start:end])
        assert payload["firstName"] == "C"


# ---------------------------------------------------------------------------
# Smoke: Uphold 1023 end-to-end
# ---------------------------------------------------------------------------

class TestUpholdSmoke:
    def test_smoke_spec_produces_full_plan(self):
        spec = bf._smoke_spec_for("uphold", "839")
        plan = bf.build_plan(spec)
        steps = bf.emit_steps(plan, label="uphold-839")
        # All four field-handler step kinds present
        comments = [s["args"].get("comment", "") for s in steps
                    if s["tool"] == "browser.act.evaluate"]
        assert any("Fill all native text" in c for c in comments)
        assert any("MenuVessel" in c for c in comments)
        assert any("Yes/No" in c for c in comments)
        assert any("Pre-submit verify" in c for c in comments)
        # Final step is submit
        assert steps[-1]["args"].get("meta", {}).get("final_submit") is True
        # All steps serialize to JSON (no non-serializable closures, etc.)
        json.dumps(steps)


# ---------------------------------------------------------------------------
# inline_submit URL classifier integration
# ---------------------------------------------------------------------------

class TestInlineSubmitDispatch:
    def test_detect_ats_bamboohr(self):
        from inline_submit import detect_ats
        assert detect_ats("https://uphold.bamboohr.com/careers/839") == "bamboohr"
        assert detect_ats("https://x.bamboohr.com/jobs/view.php?id=1") == "bamboohr"
        assert detect_ats("https://x.bamboohr.com/jobs/embed2.php?id=1") == "bamboohr"

    def test_parse_bamboohr_url_in_inline_submit(self):
        from inline_submit import parse_bamboohr_url
        assert parse_bamboohr_url("https://uphold.bamboohr.com/careers/839") == ("uphold", "839")
        assert parse_bamboohr_url("https://x.bamboohr.com/jobs/view.php?id=42") == ("x", "42")
        assert parse_bamboohr_url("https://greenhouse.io/x/jobs/1") is None


# ---------------------------------------------------------------------------
# capsolver_client v2 method
# ---------------------------------------------------------------------------

class TestCapSolverV2:
    def test_recaptcha_v2_method_exists(self):
        from capsolver_client import CapSolverClient
        assert hasattr(CapSolverClient, "recaptcha_v2")

    def test_recaptcha_v2_builds_correct_task(self, monkeypatch):
        from capsolver_client import CapSolverClient
        captured = {}

        def fake_solve(self, task, solution_keys, label):
            captured["task"] = task
            captured["keys"] = solution_keys
            captured["label"] = label
            return "v2-token-xyz"

        monkeypatch.setattr(CapSolverClient, "_solve", fake_solve)
        c = CapSolverClient(api_key="fake")
        tok = c.recaptcha_v2("6Le-test", "https://uphold.bamboohr.com/careers/839")
        assert tok == "v2-token-xyz"
        assert captured["task"]["type"] == "ReCaptchaV2TaskProxyless"
        assert captured["task"]["websiteKey"] == "6Le-test"
        assert captured["task"]["websiteURL"] == "https://uphold.bamboohr.com/careers/839"
        assert captured["task"]["isInvisible"] is False

    def test_recaptcha_v2_invisible_flag(self, monkeypatch):
        from capsolver_client import CapSolverClient
        captured = {}

        def fake_solve(self, task, solution_keys, label):
            captured["task"] = task
            return "tok"

        monkeypatch.setattr(CapSolverClient, "_solve", fake_solve)
        c = CapSolverClient(api_key="fake")
        c.recaptcha_v2("k", "u", is_invisible=True)
        assert captured["task"]["isInvisible"] is True
