"""Unit tests for rippling_filler.

Covers:
- _normalize_phone (string, dict, +1, US-local, edge cases)
- _normalize_url_like (bare domain, full URL, empty)
- build_application_payload (basic-questions, resume url, cover letter,
  turnstile injection in BODY not headers, custom oids pass-through,
  reserved keys filtered)
- _hash_payload stability
- upload_file (with FakeDriver simulating presign + S3 204)
- fetch_turnstile_sitekey (parses __NEXT_DATA__)
- submit_application end-to-end with FakeDriver + FakeCaptcha:
    happy path -> "submitted"
    turnstile rejection -> "failed" / "turnstile_rejected"
    missing-field 400 -> "failed" / "malformed:..."
    capsolver disabled -> "skipped"
    dry-run -> "dry-run" (no /apply call)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import rippling_filler as rf


# --- Fake transport ----------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code: int, body=None, text=""):
        self.status_code = status_code
        self._body = body
        self.text = text if text else (json.dumps(body) if body is not None else "")
    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


class FakeDriver:
    def __init__(self):
        self.gets = []
        self.posts = []
        self.responses = {"get": [], "post": []}

    def queue(self, method: str, response: FakeResponse):
        self.responses[method].append(response)

    def get(self, url, *, headers=None, params=None, timeout=30):
        self.gets.append({"url": url, "headers": headers, "params": params})
        return self.responses["get"].pop(0)

    def post(self, url, *, json_body=None, files=None, headers=None, timeout=30):
        self.posts.append({"url": url, "json_body": json_body,
                           "files": files, "headers": headers})
        return self.responses["post"].pop(0)


class FakeCaptcha:
    def __init__(self, enabled=True, token="FAKE-TURNSTILE-TOKEN-x" * 4):
        self._enabled = enabled
        self._token = token
        self.calls = []
    def is_enabled(self): return self._enabled
    def turnstile(self, sitekey, page_url):
        self.calls.append((sitekey, page_url))
        if self._token is None:
            raise RuntimeError("solver_failed")
        return self._token


# --- helpers ----------------------------------------------------------------

PRESIGN_OK = FakeResponse(200, {
    "data": {
        "url": "https://prod-rippling-us1-ats.s3.amazonaws.com/",
        "fields": {
            "Content-Type": "application/pdf",
            "Content-Disposition": "inline; filename=abc.pdf",
            "uploadsig": "JWT.JWT.JWT",
            "key": "common/ats_public/abc.pdf",
            "x-amz-algorithm": "AWS4-HMAC-SHA256",
            "policy": "BASE64POLICY",
            "x-amz-signature": "deadbeef",
        },
        "acl": False,
        "finalUrl": {
            "url": "https://prod-rippling-us1-ats.s3.amazonaws.com/common/ats_public/abc.pdf",
        },
    }
})

S3_OK = FakeResponse(204, text="")

NEXT_DATA_HTML = '''<html><head></head><body>
<script id="__NEXT_DATA__" type="application/json">{
  "props": {"pageProps": {"apiData": {
    "cloudflareEnvConfig": {
      "CLOUDFLARE_TURNSTILE_MANAGED_SITE_KEY": "0xTESTKEY",
      "DISABLE_CLOUDFLARE_TURNSTILE": null
    }
  }}}
}</script></body></html>'''
NEXT_DATA_DISABLED = NEXT_DATA_HTML.replace('"DISABLE_CLOUDFLARE_TURNSTILE": null',
                                            '"DISABLE_CLOUDFLARE_TURNSTILE": true')

APPLY_PAGE_OK = FakeResponse(200, text=NEXT_DATA_HTML)
APPLY_PAGE_DISABLED = FakeResponse(200, text=NEXT_DATA_DISABLED)


@pytest.fixture
def tmp_pdf(tmp_path):
    p = tmp_path / "resume.pdf"
    p.write_bytes(b"%PDF-1.4\nfake\n%%EOF")
    return str(p)


# --- _normalize_phone -------------------------------------------------------

class TestNormalizePhone:
    def test_us_local(self):
        assert rf._normalize_phone("415-555-1234") == {
            "countryCode": "1", "nationalNumber": "4155551234"
        }
    def test_us_with_country(self):
        assert rf._normalize_phone("+1 415 555 1234") == {
            "countryCode": "1", "nationalNumber": "4155551234"
        }
    def test_us_with_one_prefix(self):
        assert rf._normalize_phone("14155551234") == {
            "countryCode": "1", "nationalNumber": "4155551234"
        }
    def test_dict_form(self):
        assert rf._normalize_phone({"countryCode": "44", "nationalNumber": "7700900123"}) == {
            "countryCode": "44", "nationalNumber": "7700900123"
        }
    def test_dict_partial(self):
        assert rf._normalize_phone({"nationalNumber": "5551234567"}) == {
            "countryCode": "1", "nationalNumber": "5551234567"
        }
    def test_empty(self):
        assert rf._normalize_phone("") == {"countryCode": "1", "nationalNumber": ""}
        assert rf._normalize_phone(None) == {"countryCode": "1", "nationalNumber": ""}


# --- _normalize_url_like ----------------------------------------------------

class TestNormalizeUrlLike:
    def test_bare(self):
        assert rf._normalize_url_like("linkedin.com/in/x") == "http://linkedin.com/in/x"
    def test_https(self):
        assert rf._normalize_url_like("https://linkedin.com/in/x") == "https://linkedin.com/in/x"
    def test_http(self):
        assert rf._normalize_url_like("http://x.com") == "http://x.com"
    def test_empty(self):
        assert rf._normalize_url_like("") == ""


# --- build_application_payload ---------------------------------------------

class TestBuildPayload:
    BASE = {
        "first_name": "Cyrus", "last_name": "Yari",
        "email": "x@example.com", "current_company": "Acme",
        "location": "SF", "phone_number": "+14155551234",
        "linkedin_link": "linkedin.com/in/cy",
    }

    def test_minimum(self):
        body = rf.build_application_payload(
            answers=self.BASE,
            resume_finalUrl="https://s3.example/r.pdf",
            cover_letter_finalUrl=None,
            turnstile_token=None,
        )
        afr = body["applicationFormResponse"]
        assert afr["first_name"] == "Cyrus"
        assert afr["resume"] == "https://s3.example/r.pdf"
        assert afr["resumeFileExtension"] == "application/pdf"
        assert "cover_letter" not in afr
        assert afr["phone_number"] == {"countryCode": "1", "nationalNumber": "4155551234"}
        assert afr["linkedin_link"] == "http://linkedin.com/in/cy"
        assert afr["timezone"] == "America/Los_Angeles"
        # No turnstile keys when no token
        assert "cf-client-response" not in body
        assert body["eeocData"] is None
        assert body["referralId"] is None
        assert body["customQuestionnaireResponses"] is None

    def test_cover_letter(self):
        body = rf.build_application_payload(
            answers=self.BASE,
            resume_finalUrl="https://s3/r.pdf",
            cover_letter_finalUrl="https://s3/c.pdf",
            turnstile_token=None,
        )
        afr = body["applicationFormResponse"]
        assert afr["cover_letter"] == "https://s3/c.pdf"
        assert afr["coverLetterFileExtension"] == "application/pdf"

    def test_turnstile_in_body_not_headers(self):
        body = rf.build_application_payload(
            answers=self.BASE,
            resume_finalUrl="r",
            cover_letter_finalUrl=None,
            turnstile_token="TOKEN",
        )
        # These MUST be top-level body keys; this is the trap from chain
        # rippling-adapter-2026-05-30.
        assert body["cf-client-response"] == "TOKEN"
        assert body["cf-client-response-status"] == "complete"
        assert body["cf-client-widget-type"] == "managed"
        assert body["cf-client-widget-name"] == "job-application-form"

    def test_custom_oid_passthrough(self):
        ans = dict(self.BASE)
        ans["custom_q_yoe"] = "5 years"
        body = rf.build_application_payload(
            answers=ans,
            resume_finalUrl="r",
            cover_letter_finalUrl=None,
            turnstile_token=None,
        )
        assert body["applicationFormResponse"]["custom_q_yoe"] == "5 years"

    def test_reserved_keys_filtered(self):
        ans = dict(self.BASE, resume="should_be_ignored",
                   resumeFileExtension="should_be_ignored",
                   timezone="should_be_overridden",
                   eeoc="ignored", customQuestions="ignored")
        body = rf.build_application_payload(
            answers=ans,
            resume_finalUrl="https://s3/real.pdf",
            cover_letter_finalUrl=None,
            turnstile_token=None,
        )
        afr = body["applicationFormResponse"]
        assert afr["resume"] == "https://s3/real.pdf"
        assert afr["resumeFileExtension"] == "application/pdf"
        assert afr["timezone"] == "America/Los_Angeles"
        assert "eeoc" not in afr
        assert "customQuestions" not in afr

    def test_phone_dict_input(self):
        ans = dict(self.BASE, phone_number={"countryCode": "44", "nationalNumber": "7700900123"})
        body = rf.build_application_payload(
            answers=ans, resume_finalUrl="r",
            cover_letter_finalUrl=None, turnstile_token=None)
        assert body["applicationFormResponse"]["phone_number"] == {
            "countryCode": "44", "nationalNumber": "7700900123"
        }


# --- _hash_payload ---------------------------------------------------------

def test_hash_stable():
    a = {"x": 1, "y": [2, 3]}
    b = {"y": [2, 3], "x": 1}
    assert rf._hash_payload(a) == rf._hash_payload(b)
    assert len(rf._hash_payload(a)) == 16


# --- upload_file ------------------------------------------------------------

def test_upload_file_happy(tmp_pdf):
    drv = FakeDriver()
    drv.queue("get", PRESIGN_OK)
    drv.queue("post", S3_OK)
    url = rf.upload_file(drv, "hammerspace", "jid-1", tmp_pdf)
    assert url == "https://prod-rippling-us1-ats.s3.amazonaws.com/common/ats_public/abc.pdf"
    # presign request
    g = drv.gets[0]
    assert g["url"] == rf.UPLOAD_URL
    assert g["params"]["contentType"] == "application/pdf"
    assert g["params"]["fileType"] == "DOCUMENT_UPLOAD"
    # S3 POST
    p = drv.posts[0]
    assert p["url"] == "https://prod-rippling-us1-ats.s3.amazonaws.com/"
    # Field order matters for S3 — file MUST be last
    field_names = [k for k, _ in p["files"]]
    assert field_names[-1] == "file"
    # acl:false in response means NO acl field
    assert "acl" not in field_names


def test_upload_file_with_acl(tmp_pdf):
    drv = FakeDriver()
    # presign with acl=True
    presign = FakeResponse(200, {
        "data": {
            "url": "https://s3/", "fields": {"key": "k"},
            "acl": True,
            "finalUrl": {"url": "https://final/x.pdf"},
        }})
    drv.queue("get", presign)
    drv.queue("post", S3_OK)
    rf.upload_file(drv, "x", "y", tmp_pdf)
    field_names = [k for k, _ in drv.posts[0]["files"]]
    assert "acl" in field_names


def test_upload_file_missing(tmp_path):
    drv = FakeDriver()
    with pytest.raises(rf.RipplingSubmitError, match="file not found"):
        rf.upload_file(drv, "x", "y", str(tmp_path / "nope.pdf"))


def test_upload_file_presign_500(tmp_pdf):
    drv = FakeDriver()
    drv.queue("get", FakeResponse(500, text="boom"))
    with pytest.raises(rf.RipplingSubmitError, match="HTTP 500"):
        rf.upload_file(drv, "x", "y", tmp_pdf)


def test_upload_file_s3_403(tmp_pdf):
    drv = FakeDriver()
    drv.queue("get", PRESIGN_OK)
    drv.queue("post", FakeResponse(403, text="<Error>"))
    with pytest.raises(rf.RipplingSubmitError, match="S3 upload HTTP 403"):
        rf.upload_file(drv, "x", "y", tmp_pdf)


# --- fetch_turnstile_sitekey ----------------------------------------------

def test_fetch_sitekey_ok():
    drv = FakeDriver()
    drv.queue("get", APPLY_PAGE_OK)
    sk = rf.fetch_turnstile_sitekey(drv, "x", "y")
    assert sk == "0xTESTKEY"


def test_fetch_sitekey_disabled():
    drv = FakeDriver()
    drv.queue("get", APPLY_PAGE_DISABLED)
    assert rf.fetch_turnstile_sitekey(drv, "x", "y") is None


def test_fetch_sitekey_404():
    drv = FakeDriver()
    drv.queue("get", FakeResponse(404, text="not found"))
    with pytest.raises(rf.RipplingSubmitError, match="HTTP 404"):
        rf.fetch_turnstile_sitekey(drv, "x", "y")


# --- submit_application end-to-end ----------------------------------------

ANSWERS = {
    "first_name": "Cyrus", "last_name": "Yari",
    "email": "x@example.com", "current_company": "Acme",
    "location": "SF, CA", "phone_number": "415-555-1234",
    "linkedin_link": "linkedin.com/in/cy",
}


def test_submit_happy(tmp_pdf):
    drv = FakeDriver()
    # 1. apply page GET (sitekey)
    drv.queue("get", APPLY_PAGE_OK)
    # 2. resume: presign GET + S3 POST
    drv.queue("get", PRESIGN_OK)
    drv.queue("post", S3_OK)
    # 3. apply API POST
    drv.queue("post", FakeResponse(200, {"ok": True}))

    cap = FakeCaptcha()
    art = rf.submit_application(
        slug="hammerspace", job_id="jid-1",
        resume_path=tmp_pdf, answers=ANSWERS,
        driver=drv, captcha=cap,
    )
    assert art.status == "submitted", art.error
    assert art.http_status == 200
    assert art.sitekey == "0xTESTKEY"
    assert art.turnstile_token_len > 0
    assert art.payload["applicationFormResponse"]["first_name"] == "Cyrus"
    assert art.payload["cf-client-response"]
    assert art.submitted_at
    # captcha called with the right sitekey
    assert cap.calls[0][0] == "0xTESTKEY"


def test_submit_turnstile_rejected(tmp_pdf):
    drv = FakeDriver()
    drv.queue("get", APPLY_PAGE_OK)
    drv.queue("get", PRESIGN_OK)
    drv.queue("post", S3_OK)
    drv.queue("post", FakeResponse(401, {"error": "turnstile_verification_failure"}))

    art = rf.submit_application(
        slug="x", job_id="y", resume_path=tmp_pdf, answers=ANSWERS,
        driver=drv, captcha=FakeCaptcha(),
    )
    assert art.status == "failed"
    assert art.error == "turnstile_rejected"
    assert art.http_status == 401


def test_submit_missing_field(tmp_pdf):
    drv = FakeDriver()
    drv.queue("get", APPLY_PAGE_OK)
    drv.queue("get", PRESIGN_OK)
    drv.queue("post", S3_OK)
    drv.queue("post", FakeResponse(400, {
        "error_code": "MALFORMED",
        "message": "Required question 'first_name' is missing from the application",
        "resource": None,
    }))
    incomplete = dict(ANSWERS); incomplete.pop("first_name")
    art = rf.submit_application(
        slug="x", job_id="y", resume_path=tmp_pdf, answers=incomplete,
        driver=drv, captcha=FakeCaptcha(),
    )
    assert art.status == "failed"
    assert art.error.startswith("malformed:")
    assert "first_name" in art.error


def test_submit_capsolver_disabled(tmp_pdf):
    drv = FakeDriver()
    drv.queue("get", APPLY_PAGE_OK)
    cap = FakeCaptcha(enabled=False)
    art = rf.submit_application(
        slug="x", job_id="y", resume_path=tmp_pdf, answers=ANSWERS,
        driver=drv, captcha=cap,
    )
    assert art.status == "skipped"
    assert art.error == "capsolver_disabled"
    # We didn't even attempt upload or apply POST.
    assert len(drv.posts) == 0
    assert cap.calls == []


def test_submit_dry_run(tmp_pdf):
    drv = FakeDriver()
    drv.queue("get", APPLY_PAGE_OK)
    drv.queue("get", PRESIGN_OK)
    drv.queue("post", S3_OK)
    # dry-run must NOT hit /apply
    art = rf.submit_application(
        slug="x", job_id="y", resume_path=tmp_pdf, answers=ANSWERS,
        driver=drv, captcha=FakeCaptcha(),
        dry_run=True,
    )
    assert art.status == "dry-run"
    # Exactly: 1 GET (page) + 1 GET (presign) + 1 POST (S3); no /apply.
    assert len(drv.gets) == 2
    assert len(drv.posts) == 1
    assert drv.posts[0]["url"].startswith("https://prod-rippling-us1-ats.s3")


def test_submit_skip_captcha(tmp_pdf):
    drv = FakeDriver()
    drv.queue("get", APPLY_PAGE_OK)
    drv.queue("get", PRESIGN_OK)
    drv.queue("post", S3_OK)
    drv.queue("post", FakeResponse(401, {"error": "turnstile_verification_failure"}))
    cap = FakeCaptcha()
    art = rf.submit_application(
        slug="x", job_id="y", resume_path=tmp_pdf, answers=ANSWERS,
        driver=drv, captcha=cap,
        skip_captcha=True,
    )
    # No turnstile call attempted
    assert cap.calls == []
    assert art.turnstile_token_len == 0
    # Server will reject (expected)
    assert art.status == "failed"
    assert art.error == "turnstile_rejected"
    # Payload built WITHOUT cf-client-* keys
    assert "cf-client-response" not in art.payload


def test_submit_tenant_disables_turnstile(tmp_pdf):
    """If cloudflareEnvConfig.DISABLE_CLOUDFLARE_TURNSTILE=true we skip captcha
    automatically and submit anyway."""
    drv = FakeDriver()
    drv.queue("get", APPLY_PAGE_DISABLED)
    drv.queue("get", PRESIGN_OK)
    drv.queue("post", S3_OK)
    drv.queue("post", FakeResponse(200, {"ok": True}))
    cap = FakeCaptcha()
    art = rf.submit_application(
        slug="x", job_id="y", resume_path=tmp_pdf, answers=ANSWERS,
        driver=drv, captcha=cap,
    )
    assert art.sitekey is None
    assert cap.calls == []   # no captcha solve attempted
    assert art.status == "submitted"
