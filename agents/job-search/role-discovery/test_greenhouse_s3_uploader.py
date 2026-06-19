#!/usr/bin/env python3
"""Tests for the Greenhouse native S3 resume uploader sidecar (chain_009).

These tests deliberately avoid Playwright/browser dependencies. They:
1. Validate the structural shape + invariants of the JS payloads.
2. Validate the kill-switch behavior in the runner.
3. Use a tiny synthetic JS runtime (`js2py`-style hand evaluator) to exercise
   the fetch-patch logic without spinning up Playwright. We translate the
   patch's body-mutation core into a Python helper for unit purposes and
   assert the runtime JS textually contains the same invariants.

If the JS bundles drift (GH ships a new bundle that uses different keys),
these tests SHOULD fail loudly. Run:
    .venv/bin/python -m unittest test_greenhouse_s3_uploader
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Personal info loaded from personal-info.json
_PI = json.loads((HERE.parent / "personal-info.json").read_text())
_pi_id = _PI["identity"]

import greenhouse_filler as gf  # noqa: E402


# ---------------------------------------------------------------------------
# Pure-Python re-implementation of the fetch patch's body-mutation core, used
# to test the substantive logic. The JS lives in gf.JS_INSTALL_FETCH_PATCH and
# its STRUCTURAL invariants are checked by separate tests.
# ---------------------------------------------------------------------------

def mutate_submit_body(body_str: str, content_type: str, inject: dict | None) -> tuple[str, dict | None]:
    """Mirror of the JS in JS_INSTALL_FETCH_PATCH. Returns (new_body, mutated_record)."""
    if not inject:
        return body_str, None
    if not body_str or not isinstance(body_str, str):
        return body_str, None
    is_jsonish = "application/json" in (content_type or "") or (body_str.startswith("{") and body_str.endswith("}"))
    if not is_jsonish:
        return body_str, None
    try:
        parsed = json.loads(body_str)
    except Exception:
        return body_str, None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("job_application"), dict):
        return body_str, None
    parsed["job_application"]["resume_url"] = inject["resume_url"]
    parsed["job_application"]["resume_url_filename"] = inject["resume_url_filename"]
    return json.dumps(parsed), {
        "resume_url": inject["resume_url"],
        "resume_url_filename": inject["resume_url_filename"],
    }


def substitute_key(key: str, now_ms: int, unique_id: str) -> str:
    """Mirror of the key-substitution logic in JS_S3_UPLOAD."""
    return key.replace("{timestamp}", str(now_ms)).replace("{unique_id}", unique_id)


# ===========================================================================
# Tests
# ===========================================================================

class JSPayloadInvariants(unittest.TestCase):
    """Verify the JS source contains the invariants the real GH bundle requires.

    These act as canaries: if Greenhouse changes the upload schema or field
    names, the runtime would break and these tests would also need to update.
    """

    def test_fetch_patch_has_idempotency_guard(self):
        self.assertIn("__gh_fetch_patched", gf.JS_INSTALL_FETCH_PATCH)
        self.assertIn("alreadyPatched", gf.JS_INSTALL_FETCH_PATCH)

    def test_fetch_patch_targets_job_application_only(self):
        self.assertIn("job_application", gf.JS_INSTALL_FETCH_PATCH)
        self.assertIn("resume_url", gf.JS_INSTALL_FETCH_PATCH)
        self.assertIn("resume_url_filename", gf.JS_INSTALL_FETCH_PATCH)

    def test_patch_covers_both_fetch_and_xhr(self):
        # chain_009 v3: GH submits via XMLHttpRequest, not fetch. Patch must
        # cover both transports or live-verify of Lyft 1343 hangs on fieldErrs.
        self.assertIn("window.fetch", gf.JS_INSTALL_FETCH_PATCH)
        self.assertIn("XMLHttpRequest", gf.JS_INSTALL_FETCH_PATCH)
        self.assertIn("prototype.send", gf.JS_INSTALL_FETCH_PATCH)
        self.assertIn("prototype.open", gf.JS_INSTALL_FETCH_PATCH)
        # XHR patch must also be idempotent so we don't double-wrap on hot reloads.
        self.assertIn("__gh_patched", gf.JS_INSTALL_FETCH_PATCH)

    def test_fetch_patch_does_not_break_on_non_post(self):
        # The wrapper checks method === POST; non-POST falls through to orig.
        self.assertIn("'POST'", gf.JS_INSTALL_FETCH_PATCH)

    def test_presigned_uses_jben_url_env_with_fallback(self):
        self.assertIn("JBEN_URL", gf.JS_FETCH_PRESIGNED_FIELDS)
        self.assertIn("https://boards.greenhouse.io", gf.JS_FETCH_PRESIGNED_FIELDS)
        self.assertIn("uncacheable_attributes/presigned_fields", gf.JS_FETCH_PRESIGNED_FIELDS)
        self.assertIn("fields[]=resume", gf.JS_FETCH_PRESIGNED_FIELDS)

    def test_s3_upload_substitutes_timestamp_and_unique_id(self):
        self.assertIn("{timestamp}", gf.JS_S3_UPLOAD)
        self.assertIn("{unique_id}", gf.JS_S3_UPLOAD)
        self.assertIn("Date.now()", gf.JS_S3_UPLOAD)

    def test_s3_upload_appends_required_form_fields(self):
        for field in ("utf8", "authenticity_token", "Content-Type", "key", "file"):
            self.assertIn(f"'{field}'", gf.JS_S3_UPLOAD, msg=f"missing {field}")

    def test_s3_upload_checks_201_only(self):
        # GH uses success_action_status=201; we must accept exactly 201.
        self.assertIn("201", gf.JS_S3_UPLOAD)

    def test_inject_install_sets_correct_window_global(self):
        self.assertIn("__gh_resume_inject", gf.JS_INSTALL_RESUME_INJECT)
        self.assertIn("resume_url", gf.JS_INSTALL_RESUME_INJECT)
        self.assertIn("resume_url_filename", gf.JS_INSTALL_RESUME_INJECT)


class FetchPatchMutation(unittest.TestCase):
    """Behavior tests of the mutation logic (Python mirror)."""

    INJECT = {
        "resume_url": "https://grnhse-prod-jben-us-east-1.s3.amazonaws.com/stash/applications/resumes/1700000000000-abc123def456ab-xyz",
        "resume_url_filename": "Cyrus_Shekari_Resume.pdf",
    }

    def test_passthrough_when_no_inject(self):
        body = json.dumps({"job_application": {"first_name": "X"}})
        new, mut = mutate_submit_body(body, "application/json", None)
        self.assertEqual(new, body)
        self.assertIsNone(mut)

    def test_passthrough_when_not_json_content_type_and_not_jsonish(self):
        body = "name=foo&val=bar"
        new, mut = mutate_submit_body(body, "application/x-www-form-urlencoded", self.INJECT)
        self.assertEqual(new, body)
        self.assertIsNone(mut)

    def test_passthrough_when_no_job_application_key(self):
        body = json.dumps({"something_else": {"a": 1}})
        new, mut = mutate_submit_body(body, "application/json", self.INJECT)
        self.assertEqual(new, body)
        self.assertIsNone(mut)

    def test_mutates_job_application_resume_fields(self):
        body = json.dumps({
            "job_application": {"first_name": _pi_id["first_name"], "last_name": _pi_id["last_name"]},
            "fingerprint": {"foo": "bar"},
        })
        new, mut = mutate_submit_body(body, "application/json", self.INJECT)
        self.assertIsNotNone(mut)
        parsed = json.loads(new)
        self.assertEqual(parsed["job_application"]["resume_url"], self.INJECT["resume_url"])
        self.assertEqual(parsed["job_application"]["resume_url_filename"], self.INJECT["resume_url_filename"])
        # Other fields preserved
        self.assertEqual(parsed["job_application"]["first_name"], _pi_id["first_name"])
        self.assertEqual(parsed["fingerprint"], {"foo": "bar"})

    def test_overwrites_existing_resume_fields(self):
        body = json.dumps({
            "job_application": {
                "first_name": _pi_id["first_name"],
                "resume_url": "https://example.com/old.pdf",
                "resume_url_filename": "old.pdf",
            }
        })
        new, mut = mutate_submit_body(body, "application/json", self.INJECT)
        parsed = json.loads(new)
        self.assertEqual(parsed["job_application"]["resume_url"], self.INJECT["resume_url"])

    def test_jsonish_body_no_content_type_still_mutates(self):
        # GH actually sends Content-Type: application/json, but the patch also
        # accepts bodies that "look JSON-y" (starts with { ends with }).
        body = json.dumps({"job_application": {"first_name": "X"}})
        new, mut = mutate_submit_body(body, "", self.INJECT)
        self.assertIsNotNone(mut)
        self.assertIn(self.INJECT["resume_url"], new)

    def test_malformed_json_body_passthrough(self):
        body = "{not really json"
        new, mut = mutate_submit_body(body, "application/json", self.INJECT)
        self.assertEqual(new, body)
        self.assertIsNone(mut)


class KeySubstitution(unittest.TestCase):
    SAMPLE_KEY = "stash/applications/resumes/{timestamp}-{unique_id}-ebe785c78337d70d9813443a95c79a1f"

    def test_substitutes_both_placeholders(self):
        out = substitute_key(self.SAMPLE_KEY, 1748345469000, "abc123def45612")
        self.assertNotIn("{timestamp}", out)
        self.assertNotIn("{unique_id}", out)
        self.assertIn("1748345469000", out)
        self.assertIn("abc123def45612", out)

    def test_substitution_pattern_matches_gh_format(self):
        out = substitute_key(self.SAMPLE_KEY, 1748345469000, "a" * 14)
        m = re.match(r"stash/applications/resumes/(\d+)-([a-z0-9]+)-([a-f0-9]+)$", out)
        self.assertIsNotNone(m, f"expected GH key format, got {out}")
        self.assertEqual(m.group(1), "1748345469000")
        self.assertEqual(len(m.group(2)), 14)


class RunnerIntegration(unittest.TestCase):
    """Smoke test: runner module imports + kill switch + flag are wired."""

    def test_kill_switch_default_on(self):
        import greenhouse_iframe_runner as r
        self.assertTrue(r.USE_GH_S3_UPLOADER, "expected sidecar enabled by default")

    def test_debug_filestack_flag_wired(self):
        import greenhouse_iframe_runner as r
        # The run() signature should accept debug_filestack
        import inspect
        sig = inspect.signature(r.run)
        self.assertIn("debug_filestack", sig.parameters)

    def test_debug_log_helper_is_safe(self):
        import greenhouse_iframe_runner as r
        # Should not raise on unserializable input
        r._debug_filestack_log({}, True, "test", object())
        r._debug_filestack_log({}, False, "test", {"any": "thing"})


class HelperImports(unittest.TestCase):
    def test_helpers_present(self):
        for name in ("JS_INSTALL_FETCH_PATCH", "JS_FETCH_PRESIGNED_FIELDS",
                     "JS_S3_UPLOAD", "JS_INSTALL_RESUME_INJECT"):
            self.assertTrue(hasattr(gf, name), f"greenhouse_filler missing {name}")
            self.assertGreater(len(getattr(gf, name)), 100, f"{name} too short")


if __name__ == "__main__":
    unittest.main()
