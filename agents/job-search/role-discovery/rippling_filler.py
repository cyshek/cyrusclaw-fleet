#!/usr/bin/env python3
"""
rippling_filler.py — Submit applications to Rippling-hosted job boards
(ats.rippling.com/<slug>/jobs/<uuid>).

Architecture (reverse-engineered from the apply page JS chunk
`/_next/static/chunks/pages/[jobBoardSlug]/jobs/[jobId]/apply-*.js`, 2026-05-30):

  1. GET /api/v1/utility/file_upload_url
       ?contentType=application/pdf
       &fileType=DOCUMENT_UPLOAD
       &fileName=<base>.pdf
     Returns {data:{url, fields:{...}, finalUrl:{url, previewUrl}, acl}}
     where `url` is an S3 endpoint and `fields` are the presigned-POST form
     keys (acl, key, x-amz-*, policy, signature, plus Content-Type,
     Content-Disposition, uploadsig, tagging).

  2. POST multipart to `url` with all `fields` + the file under key `file`.
     S3 returns 204 (no body).

  3. (For each file: resume, cover-letter) repeat 1–2.

  4. Solve Cloudflare Turnstile against sitekey
     `cloudflareEnvConfig.CLOUDFLARE_TURNSTILE_MANAGED_SITE_KEY` (read from
     the /apply page's __NEXT_DATA__; varies per tenant; Hammerspace's is
     `0x4AAAAAACMregvPzfoTgN2k`). Solve via CapSolver
     `AntiTurnstileTaskProxyless` (capsolver_client.turnstile()).

  5. POST /api/v1/board/<slug>/jobs/<uuid>/apply with JSON body:
       {
         applicationFormResponse: {
           first_name, last_name, email, current_company, location,
           linkedin_link (urlified via M = e => e.startsWith('http')? e : 'http://'+e),
           phone_number: {countryCode, nationalNumber},
           resume: <finalUrl.url>,
           resumeFileExtension: 'application/pdf',
           cover_letter: <finalUrl.url>,
           coverLetterFileExtension: 'application/pdf',
           timezone: 'America/Los_Angeles',
           jobSite: <optional>,
           # any extra basic question oids beyond the 9-field standard set
           # are passed at top level under their oid name (e.g. website_link).
         },
         eeocData: <eeoc-shaped dict or null>,
         referralId: null,
         customQuestionnaireResponses: null,   # only for tenants with additionalQuestions
         jobTargetParams: {utm_source, utm_medium, applicant_guid, sourceTracking},

         # Turnstile is passed in the BODY as four top-level keys (NOT headers).
         # This was the trap in the first end-to-end test (chain
         # `rippling-adapter-2026-05-30`): the minified `O.A.post(url, body,
         # ...headers)` actually uses Object.assign(body, headers), so the
         # cf-client-* keys are JSON-body keys, NOT HTTP headers.
         "cf-client-response":         <turnstile_token>,
         "cf-client-response-status":  "complete",
         "cf-client-widget-type":      "managed",
         "cf-client-widget-name":      "job-application-form",
       }

  6. On success Rippling returns HTTP 200 {"ok": true}.
     On Turnstile failure HTTP 401 {"error":"turnstile_verification_failure"}.
     On missing required field HTTP 400 {"error_code":"MALFORMED",
     "message":"Required question '<oid>' is missing from the application"}.

Usage (CLI):
    python3 rippling_filler.py \
        --slug hammerspace \
        --job-id 2c09a9fe-fedd-472a-9198-f2f6001934bc \
        --resume /path/to/resume.pdf \
        --answers /path/to/answers.json \
        [--cover-letter /path/to/cover.pdf] \
        [--dry-run]            # build payload but don't POST /apply
        [--no-captcha]         # skip turnstile (will 401 unless server allows it)

Programmatic:
    from rippling_filler import submit_application, RipplingSubmitError
    result = submit_application(
        slug="hammerspace",
        job_id="2c09a9fe-fedd-472a-9198-f2f6001934bc",
        resume_path="/path/to/resume.pdf",
        answers={"first_name": "...", "last_name": "...", ...},
        cover_letter_path=None,
    )
    # result -> {"status": "submitted"|"failed", "http_status": int,
    #            "response_body": str, "payload_hash": str, ...}

answers.json shape (oid -> value, matching basicQuestions schema):
    {
      "first_name": "Cyrus",
      "last_name": "Yari",
      "email": "...",
      "current_company": "...",
      "phone_number": "+14155551234",   # OR {"countryCode":"1","nationalNumber":"4155551234"}
      "location": "San Francisco, CA",
      "linkedin_link": "linkedin.com/in/cyrusyari"
    }
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capsolver_client import CapSolverClient, is_enabled as capsolver_enabled

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
)
RIPPLING_HOST = "https://ats.rippling.com"
UPLOAD_URL = f"{RIPPLING_HOST}/api/v1/utility/file_upload_url"

_NEXT_DATA_RX = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)
_PHONE_NUM_RX = re.compile(r"\D+")

LOG = logging.getLogger("rippling_filler")


class RipplingSubmitError(Exception):
    """Raised when the submit pipeline fails irrecoverably."""


# --- Driver protocol --------------------------------------------------------
#
# To support unit testing without mocking `requests`, all HTTP goes through a
# small Driver protocol. The production driver wraps `requests.Session`; tests
# inject a FakeDriver.

class _RequestsDriver:
    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", UA)

    def get(self, url: str, *, headers: Optional[dict] = None,
            params: Optional[dict] = None, timeout: int = 30) -> requests.Response:
        return self.session.get(url, headers=headers, params=params, timeout=timeout)

    def post(self, url: str, *, json_body: Optional[dict] = None,
             files: Optional[list] = None, headers: Optional[dict] = None,
             timeout: int = 30) -> requests.Response:
        return self.session.post(
            url, json=json_body, files=files, headers=headers, timeout=timeout,
        )


# --- Captcha protocol -------------------------------------------------------

class _CapSolverWrapper:
    """Thin wrapper so tests can inject a stub solver."""
    def __init__(self) -> None:
        self._client: Optional[CapSolverClient] = None

    def is_enabled(self) -> bool:
        return capsolver_enabled()

    def turnstile(self, sitekey: str, page_url: str) -> str:
        if self._client is None:
            self._client = CapSolverClient()
        return self._client.turnstile(sitekey, page_url)


# --- Helpers ----------------------------------------------------------------

def _apply_page_url(slug: str, job_id: str) -> str:
    return f"{RIPPLING_HOST}/{slug}/jobs/{job_id}/apply"


def _apply_api_url(slug: str, job_id: str) -> str:
    return f"{RIPPLING_HOST}/api/v1/board/{slug}/jobs/{job_id}/apply"


def _common_headers(slug: str, job_id: str) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Referer": _apply_page_url(slug, job_id),
        "Origin": RIPPLING_HOST,
    }


def _extract_next_data(html: str) -> dict:
    m = _NEXT_DATA_RX.search(html)
    if not m:
        raise RipplingSubmitError("apply-page missing __NEXT_DATA__")
    return json.loads(m.group(1))


def _content_type_for(path: str) -> str:
    p = path.lower()
    if p.endswith(".pdf"):
        return "application/pdf"
    if p.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if p.endswith(".doc"):
        return "application/msword"
    if p.endswith(".txt"):
        return "text/plain"
    return "application/octet-stream"


def _normalize_url_like(value: str) -> str:
    """Replicates the apply page's `M = e => has-hostname? e : 'http://'+e`."""
    if not value:
        return value
    try:
        if urlparse(value).hostname:
            return value
    except Exception:
        pass
    return f"http://{value}"


def _normalize_phone(value: Any) -> dict[str, str]:
    """Accept either dict or string. Default countryCode 1 (US)."""
    if isinstance(value, dict):
        # Trust caller-provided structure but ensure keys exist.
        return {
            "countryCode": str(value.get("countryCode") or "1"),
            "nationalNumber": str(value.get("nationalNumber") or "").strip(),
        }
    s = str(value or "").strip()
    if not s:
        return {"countryCode": "1", "nationalNumber": ""}
    # Strip everything non-digit. Leading "+1" or "1" → US country code.
    raw = _PHONE_NUM_RX.sub("", s)
    if s.startswith("+"):
        # +<cc><number>
        if raw.startswith("1") and len(raw) == 11:
            return {"countryCode": "1", "nationalNumber": raw[1:]}
        # Fallback: 1-3 char country code (best-effort; if user passes a
        # non-US number they should use dict form).
        if len(raw) >= 11:
            return {"countryCode": raw[:1], "nationalNumber": raw[1:]}
    # No +; treat as US local
    if len(raw) == 11 and raw.startswith("1"):
        raw = raw[1:]
    return {"countryCode": "1", "nationalNumber": raw}


# --- Public API -------------------------------------------------------------

@dataclass
class SubmitArtifacts:
    """All inputs that went into a submit attempt, retained for audit/replay."""
    slug: str
    job_id: str
    apply_page_url: str
    apply_api_url: str
    sitekey: Optional[str]
    turnstile_token_len: int = 0
    turnstile_solve_ms: int = 0
    resume_finalUrl: Optional[str] = None
    cover_letter_finalUrl: Optional[str] = None
    payload: dict = field(default_factory=dict)
    payload_hash: str = ""
    http_status: int = 0
    response_body: str = ""
    status: str = "pending"   # "submitted" | "failed" | "dry-run" | "skipped"
    error: Optional[str] = None
    submitted_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def upload_file(driver, slug: str, job_id: str, file_path: str,
                file_type: str = "DOCUMENT_UPLOAD") -> str:
    """Upload one file via the presigned-POST flow. Returns finalUrl.url."""
    p = Path(file_path)
    if not p.is_file():
        raise RipplingSubmitError(f"file not found: {file_path}")
    content_type = _content_type_for(file_path)
    file_bytes = p.read_bytes()

    headers = _common_headers(slug, job_id)
    params = {
        "contentType": content_type,
        "fileType": file_type,
        "fileName": p.name,
    }
    r = driver.get(UPLOAD_URL, headers=headers, params=params, timeout=30)
    if r.status_code != 200:
        raise RipplingSubmitError(
            f"file_upload_url HTTP {r.status_code}: {r.text[:300]}"
        )
    try:
        d = r.json()["data"]
    except (ValueError, KeyError):
        raise RipplingSubmitError(f"file_upload_url malformed response: {r.text[:300]}")

    s3_url = d["url"]
    fields = d.get("fields") or {}
    final_url = (d.get("finalUrl") or {}).get("url")
    if not final_url:
        raise RipplingSubmitError("file_upload_url returned no finalUrl")

    # Build multipart per the JS:
    #   for (k,v) in fields: form.append(k, v)
    #   if data.acl != False: form.append("acl", "public-read")
    #   if "Content-Type" not in form: form.append("Content-Type", file.type)
    #   form.append("file", file)
    multipart: list[tuple[str, Any]] = []
    for k, v in fields.items():
        multipart.append((k, (None, v)))
    if d.get("acl", True):
        multipart.append(("acl", (None, "public-read")))
    if not any(k.lower() == "content-type" for k, _ in multipart):
        multipart.append(("Content-Type", (None, content_type)))
    multipart.append(("file", (p.name, file_bytes, content_type)))

    s3_resp = driver.post(s3_url, files=multipart, timeout=60)
    if s3_resp.status_code not in (200, 204):
        raise RipplingSubmitError(
            f"S3 upload HTTP {s3_resp.status_code}: {s3_resp.text[:300]}"
        )
    return final_url


def fetch_turnstile_sitekey(driver, slug: str, job_id: str) -> Optional[str]:
    """Pull the per-tenant Turnstile sitekey from the apply page __NEXT_DATA__.

    Returns None if the page disables Turnstile (DISABLE_CLOUDFLARE_TURNSTILE).
    """
    r = driver.get(_apply_page_url(slug, job_id), timeout=30)
    if r.status_code != 200:
        raise RipplingSubmitError(f"apply page HTTP {r.status_code}")
    data = _extract_next_data(r.text)
    api = data.get("props", {}).get("pageProps", {}).get("apiData", {}) or {}
    cf = api.get("cloudflareEnvConfig") or {}
    if cf.get("DISABLE_CLOUDFLARE_TURNSTILE"):
        return None
    sitekey = cf.get("CLOUDFLARE_TURNSTILE_MANAGED_SITE_KEY")
    return sitekey or None


# Map answers oid -> applicationFormResponse field name. For the basic
# question set, oids and field names are the same EXCEPT:
#   - resume     -> resume + resumeFileExtension (special path)
#   - cover_letter -> cover_letter + coverLetterFileExtension
#   - phone_number -> nested dict {countryCode, nationalNumber}
#   - linkedin_link / website_link -> normalize URL with leading scheme
_STANDARD_BASIC_OIDS = {
    "first_name", "last_name", "email", "current_company", "location",
    "phone_number", "linkedin_link", "website_link",
}


def build_application_payload(
    *,
    answers: dict,
    resume_finalUrl: Optional[str],
    cover_letter_finalUrl: Optional[str],
    turnstile_token: Optional[str],
    timezone: str = "America/Los_Angeles",
    job_site: Optional[str] = None,
    eeoc_data: Optional[dict] = None,
    referral_id: Optional[str] = None,
    custom_questionnaire_responses: Optional[list] = None,
    job_target_params: Optional[dict] = None,
    turnstile_widget_name: str = "job-application-form",
    turnstile_widget_type: str = "managed",
) -> dict:
    """Construct the JSON body for POST /api/v1/board/<slug>/jobs/<id>/apply.

    Pure function — no I/O, no side effects. Unit-testable.
    """
    afr: dict[str, Any] = {}

    for oid in _STANDARD_BASIC_OIDS:
        if oid not in answers:
            continue
        val = answers[oid]
        if val is None:
            continue
        if oid == "phone_number":
            afr["phone_number"] = _normalize_phone(val)
        elif oid in ("linkedin_link", "website_link"):
            if val:
                afr[oid] = _normalize_url_like(str(val))
        else:
            afr[oid] = val

    # Pass-through any non-standard text/short-answer oids (some tenants
    # add fields like `years_of_experience` to basicQuestions). Reserved
    # names are skipped.
    _RESERVED = _STANDARD_BASIC_OIDS | {
        "resume", "cover_letter", "resumeFileExtension", "coverLetterFileExtension",
        "timezone", "jobSite", "customQuestions", "eeoc",
        "pronouns_custom", "pronouns_strategy",
    }
    for k, v in answers.items():
        if k in _RESERVED:
            continue
        if v is None:
            continue
        afr[k] = v

    if resume_finalUrl:
        afr["resume"] = resume_finalUrl
        afr["resumeFileExtension"] = "application/pdf"
    if cover_letter_finalUrl:
        afr["cover_letter"] = cover_letter_finalUrl
        afr["coverLetterFileExtension"] = "application/pdf"

    if job_site:
        afr["jobSite"] = job_site
    afr["timezone"] = timezone

    body: dict[str, Any] = {
        "applicationFormResponse": afr,
        "eeocData": eeoc_data,
        "referralId": referral_id,
        "customQuestionnaireResponses": custom_questionnaire_responses,
    }
    if job_target_params:
        body["jobTargetParams"] = job_target_params

    if turnstile_token:
        # NOTE: per the apply-page JS, these are body keys (Object.assign
        # into the body), NOT HTTP headers. See module docstring.
        body["cf-client-response"] = turnstile_token
        body["cf-client-response-status"] = "complete"
        body["cf-client-widget-type"] = turnstile_widget_type
        body["cf-client-widget-name"] = turnstile_widget_name

    return body


def _hash_payload(body: dict) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]


def submit_application(
    *,
    slug: str,
    job_id: str,
    resume_path: str,
    answers: dict,
    cover_letter_path: Optional[str] = None,
    eeoc_data: Optional[dict] = None,
    referral_id: Optional[str] = None,
    custom_questionnaire_responses: Optional[list] = None,
    job_target_params: Optional[dict] = None,
    dry_run: bool = False,
    skip_captcha: bool = False,
    driver: Optional[Any] = None,
    captcha: Optional[Any] = None,
) -> SubmitArtifacts:
    """Submit a single Rippling application end-to-end.

    Returns SubmitArtifacts with status + diagnostics. Does NOT raise on
    HTTP non-200; that's reflected in the .status / .error fields. Does
    raise RipplingSubmitError on pipeline-level failures (file missing,
    sitekey lookup failed, etc.).
    """
    driver = driver or _RequestsDriver()
    captcha = captcha or _CapSolverWrapper()

    art = SubmitArtifacts(
        slug=slug,
        job_id=job_id,
        apply_page_url=_apply_page_url(slug, job_id),
        apply_api_url=_apply_api_url(slug, job_id),
        sitekey=None,
    )

    # 1. Resolve Turnstile sitekey (also doubles as a liveness check on the
    #    apply page itself).
    sitekey = fetch_turnstile_sitekey(driver, slug, job_id)
    art.sitekey = sitekey
    LOG.info("rippling[%s/%s] sitekey=%r", slug, job_id, sitekey)

    # 2. Solve Turnstile (unless skipped or disabled tenant-side).
    turnstile_token: Optional[str] = None
    if sitekey and not skip_captcha:
        if not captcha.is_enabled():
            art.status = "skipped"
            art.error = "capsolver_disabled"
            return art
        t0 = time.monotonic()
        try:
            turnstile_token = captcha.turnstile(sitekey, art.apply_page_url)
        except Exception as e:
            art.status = "failed"
            art.error = f"turnstile_solve_failed: {e}"
            return art
        art.turnstile_solve_ms = int((time.monotonic() - t0) * 1000)
        art.turnstile_token_len = len(turnstile_token)
        LOG.info("rippling[%s/%s] turnstile solved len=%d in %dms",
                 slug, job_id, art.turnstile_token_len, art.turnstile_solve_ms)

    # 3. Upload resume + (optional) cover letter.
    art.resume_finalUrl = upload_file(driver, slug, job_id, resume_path,
                                      file_type="DOCUMENT_UPLOAD")
    LOG.info("rippling[%s/%s] resume uploaded -> %s",
             slug, job_id, art.resume_finalUrl[-80:])
    if cover_letter_path:
        art.cover_letter_finalUrl = upload_file(
            driver, slug, job_id, cover_letter_path, file_type="DOCUMENT_UPLOAD")
        LOG.info("rippling[%s/%s] cover-letter uploaded -> %s",
                 slug, job_id, art.cover_letter_finalUrl[-80:])

    # 4. Build the payload.
    payload = build_application_payload(
        answers=answers,
        resume_finalUrl=art.resume_finalUrl,
        cover_letter_finalUrl=art.cover_letter_finalUrl,
        turnstile_token=turnstile_token,
        eeoc_data=eeoc_data,
        referral_id=referral_id,
        custom_questionnaire_responses=custom_questionnaire_responses,
        job_target_params=job_target_params,
    )
    art.payload = payload
    art.payload_hash = _hash_payload(payload)

    if dry_run:
        art.status = "dry-run"
        return art

    # 5. POST the application.
    headers = _common_headers(slug, job_id)
    headers["Content-Type"] = "application/json"
    r = driver.post(art.apply_api_url, json_body=payload, headers=headers,
                    timeout=60)
    art.http_status = r.status_code
    art.response_body = (r.text or "")[:2000]

    if 200 <= r.status_code < 300:
        # Endpoint returns {"ok": true} on success.
        try:
            body = r.json()
            if body.get("ok") is True:
                art.status = "submitted"
                art.submitted_at = datetime.utcnow().isoformat() + "Z"
                return art
        except ValueError:
            pass
        # Non-JSON 2xx — treat as success but flag.
        art.status = "submitted"
        art.submitted_at = datetime.utcnow().isoformat() + "Z"
        return art

    art.status = "failed"
    # Map known error shapes to friendlier .error
    try:
        body = r.json()
        if isinstance(body, dict):
            if body.get("error") == "turnstile_verification_failure":
                art.error = "turnstile_rejected"
            elif body.get("error_code") == "MALFORMED":
                art.error = f"malformed: {body.get('message')}"
            else:
                art.error = body.get("error") or body.get("message") or f"http_{r.status_code}"
        else:
            art.error = f"http_{r.status_code}"
    except ValueError:
        art.error = f"http_{r.status_code}"
    return art


# --- CLI --------------------------------------------------------------------

def _main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Submit a Rippling job application.")
    ap.add_argument("--slug", required=True, help="Rippling board slug (e.g. hammerspace)")
    ap.add_argument("--job-id", required=True, help="Job UUID")
    ap.add_argument("--resume", required=True, help="Path to resume PDF")
    ap.add_argument("--cover-letter", help="Path to cover-letter PDF (optional)")
    ap.add_argument("--answers", required=True,
                    help="JSON file with oid->value answers (basicQuestions schema)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Build payload, upload files, solve captcha — but DON'T POST /apply")
    ap.add_argument("--no-captcha", action="store_true",
                    help="Skip captcha solve (will likely 401 unless tenant disabled it)")
    ap.add_argument("--out", help="Write SubmitArtifacts JSON here on completion")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args(argv)

    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(message)s")

    with open(args.answers) as f:
        answers = json.load(f)

    art = submit_application(
        slug=args.slug,
        job_id=args.job_id,
        resume_path=args.resume,
        answers=answers,
        cover_letter_path=args.cover_letter,
        dry_run=args.dry_run,
        skip_captcha=args.no_captcha,
    )
    out = art.to_dict()
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, indent=2, default=str))
    return 0 if art.status in ("submitted", "dry-run") else 1


if __name__ == "__main__":
    sys.exit(_main())
