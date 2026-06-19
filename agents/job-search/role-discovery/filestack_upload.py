"""
filestack_upload.py — Eightfold resume upload client

IMPORTANT FINDING: Netflix/Eightfold does NOT use Filestack for resume upload.
The Filestack widget visible in the DOM is for the rich-text editor (job description
rendering), NOT for resume upload. Resume upload uses Eightfold's own REST API.

The actual upload endpoint is:
    POST /api/application/v2/resume_upload?domain=<tenant>&user_mode=logged_out_candidate

Auth requirements:
    - CSRF token from <meta name="_csrf"> must be sent in BOTH:
        a) Form body as field '_csrf_token'
        b) Request header as 'X-CSRFToken'
    - Session cookie is set by the browser; for Playwright/requests this comes
      from the session that loaded /careers/apply?pid=<job_id>

On success, returns JSON with:
    data.profile.encId      -- session identifier used for submit
    data.profile.resumeFilename
    data.profile.resumeUrl
    data.profile.resumeUrlsTs[0].url  -- the canonical resume URL

NOTE: The task name "filestack" was based on prior diagnosis. Real blocker was
CSRF token mechanics, not Filestack token injection.
"""

import os
import re
import requests
from typing import Optional


def upload_resume(
    file_path: str,
    domain: str,
    csrf_token: str,
    session_cookies: dict,
    user_mode: str = "logged_out_candidate",
    base_url: str = "https://explore.jobs.netflix.net",
) -> dict:
    """
    Upload a resume to Eightfold /api/application/v2/resume_upload.

    Args:
        file_path:       Absolute path to the resume file (.pdf, .doc, .docx, .txt)
        domain:          Tenant domain e.g. "netflix.com"
        csrf_token:      Value of <meta name="_csrf"> from the apply page HTML
        session_cookies: Dict of cookies from the browser session (from CDP)
        user_mode:       "logged_out_candidate" for guest apply
        base_url:        Base URL of the Eightfold tenant

    Returns dict with keys:
        success: bool
        enc_id: str  -- session identifier for subsequent submit call
        resume_filename: str
        resume_url: str
        full_response: dict  -- raw API response
        error: str (only on failure)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Resume file not found: {file_path}")

    upload_url = (
        f"{base_url}/api/application/v2/resume_upload"
        f"?domain={domain}&user_mode={user_mode}"
    )

    filename = os.path.basename(file_path)

    with open(file_path, "rb") as fh:
        file_bytes = fh.read()

    ext = os.path.splitext(filename)[1].lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    # CSRF must be in BOTH form body AND header
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Origin": base_url,
        "Referer": f"{base_url}/careers/apply",
        "X-CSRFToken": csrf_token,
        "X-Requested-With": "XMLHttpRequest",
    }

    files = {"resume": (filename, file_bytes, mime_type)}
    data = {"_csrf_token": csrf_token}

    resp = requests.post(
        upload_url,
        files=files,
        data=data,
        headers=headers,
        cookies=session_cookies,
        timeout=60,
    )

    if resp.status_code != 200:
        return {
            "success": False,
            "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
            "status_code": resp.status_code,
        }

    body = resp.json()
    profile = body.get("data", {}).get("profile", {})
    enc_id = profile.get("encId", "")
    resume_filename = profile.get("resumeFilename", "")
    urls_ts = profile.get("resumeUrlsTs", [])
    resume_url = urls_ts[0].get("url", "") if urls_ts else profile.get("resumeUrl", "")

    return {
        "success": True,
        "enc_id": enc_id,
        "resume_filename": resume_filename,
        "resume_url": resume_url,
        "full_response": body,
    }


def get_csrf_from_apply_page(
    pid: str,
    domain: str = "netflix.com",
    base_url: str = "https://explore.jobs.netflix.net",
) -> tuple:
    """
    Fetch the apply page and extract CSRF token + session cookies.
    Returns (csrf_token: str, session_cookies: dict).
    NOTE: This stateless HTTP path may get stale CSRF tokens.
    Use the Playwright/CDP path in _eightfold_runner.py for production.
    """
    apply_url = f"{base_url}/careers/apply?pid={pid}"
    resp = requests.get(
        apply_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        },
        timeout=30,
    )
    csrf_match = re.search(r'<meta name="_csrf" content="([^"]+)"', resp.text)
    csrf_token = csrf_match.group(1) if csrf_match else ""
    session_cookies = dict(resp.cookies)
    return csrf_token, session_cookies


def extract_filestack_handle(filestack_response: dict) -> Optional[str]:
    """
    DEPRECATED / INVESTIGATION ARTIFACT:
    Extract the Filestack handle from a Filestack API response.

    Netflix/Eightfold does NOT use Filestack for resume upload.
    Retained for reference in case a future Lyft/Hume investigation confirms
    a true Filestack path (data-allow-s3="true" on GH embed).

    Filestack /api/store/S3 returns:
        {"url": "https://cdn.filestackapi.com/HANDLE", "handle": "HANDLE", ...}
    """
    handle = filestack_response.get("handle")
    if handle:
        return handle
    url = filestack_response.get("url", "")
    if url:
        parts = url.rstrip("/").split("/")
        if parts:
            return parts[-1]
    return None
