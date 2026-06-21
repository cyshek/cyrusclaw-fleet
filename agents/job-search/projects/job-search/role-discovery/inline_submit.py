#!/usr/bin/env python3
"""
inline_submit.py — Inline submit driver (NEW pipeline, 2026-05-13).

Replaces the old stage→prep→submit dance. For each role, this script does the
PURE-PYTHON prep half (folder, JD fetch, dryrun spec, resume tailoring,
cover answers) and emits the browser plan that the calling agent executes.

Pipeline per role:
  1. Resolve role from tracker.db (or accept an existing slug).
  2. Build slug = "{company-slug}-{gh_jid}".
  3. Create applications/submitted/<slug>/ (yes — direct to submitted/).
  4. Fetch JD via Greenhouse boards-api → JD.md.
  5. Build meta.json + prefill.json.
  6. Generate dryrun spec (greenhouse_dryrun.py).
  7. Tailor resume (bullet_rewriter.py --render). Uses a queued→submitted
     symlink shim because bullet_rewriter currently hardcodes APPS_DIR.
  8. Generate cover answers (cover_answer_generator.py).
  9. Build browser plan (greenhouse_filler.build_plan + emit_steps) and
     write to role-discovery/output/inline-plan-<slug>.json.
 10. Copy resume PDF to /tmp/openclaw/uploads/ for browser upload.

What this script does NOT do:
  - Open a browser.
  - Click Submit.
  - Update tracker.db (the calling agent does that AFTER the submit confirms).
  - Run render_xlsx.py (calling agent does that after).

CLI:
  inline_submit.py --role-id <id>          # pull role from tracker.db
  inline_submit.py --slug <slug>           # if folder/dryrun already exist (re-prep)
  inline_submit.py --batch <N>             # auto-pick next N open Greenhouse roles
  inline_submit.py --dry-run               # do everything except final 'plan ready' marker

Conservatism:
  - Skip if applied_on IS NOT NULL (already submitted).
  - Each phase has its own try/except; on failure, mark STATUS.md=ABORT-<phase>
    and exit non-zero for that role. Batch continues to next role.
  - Per-role time budget enforced loosely via subprocess timeouts on the heavy
    phases (bullet_rewriter, cover_answer_generator).

See INLINE-SUBMIT-PLAYBOOK.md for the full playbook.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent  # projects/job-search
DB_PATH = PROJECT / "tracker.db"
PERSONAL_INFO = PROJECT / "personal-info.json"
QUEUED_DIR = PROJECT / "applications" / "queued"
SUBMITTED_DIR = PROJECT / "applications" / "submitted"
DRYRUN_DIR = PROJECT / "applications" / "dryrun"
OUTPUT_DIR = HERE / "output"
UPLOADS_DIR = Path("/tmp/openclaw/uploads")
VENV_PY = HERE / ".venv" / "bin" / "python"
GH_CSP_BLOCKLIST_PATH = HERE / "greenhouse_csp_blocklist.yaml"

# ---------------------------------------------------------------------------
# Greenhouse CSP/reCAPTCHA-Enterprise blocklist (2026-05-24)
# ---------------------------------------------------------------------------
# Some Greenhouse tenants deploy reCAPTCHA Enterprise (calls
# www.recaptcha.net/recaptcha/enterprise/clr) while the shared Greenhouse CSP
# only allows www.google.com in connect-src -> the captcha XHR is blocked ->
# submit button stays permanent-disabled and POST /v1/post returns 428.
#
# These are detected manually (failed submit attempt) and listed in
# greenhouse_csp_blocklist.yaml. When a tenant is on the list, prep short-
# circuits to PREP-READY-MANUAL-CSP-CAPTCHA without burning bullet_rewriter
# credits.

def load_gh_csp_blocklist() -> set[str]:
    """Return the set of Greenhouse tenant slugs known to fail submit due to
    CSP-vs-reCAPTCHA-Enterprise mismatch. Returns empty set if YAML is missing
    or PyYAML is unavailable; never raises."""
    if not GH_CSP_BLOCKLIST_PATH.exists():
        return set()
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(GH_CSP_BLOCKLIST_PATH.read_text()) or {}
        out: set[str] = set()
        for entry in (data.get("tenants") or []):
            if isinstance(entry, dict) and entry.get("slug"):
                out.add(str(entry["slug"]).strip().lower())
        return out
    except Exception as e:  # pragma: no cover - defensive
        print(f"[inline_submit] WARN: failed to load CSP blocklist: {e}", file=sys.stderr)
        return set()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GH_RX = re.compile(r"(?:job-boards|boards|eu)\.greenhouse\.io/([^/]+)/jobs/(\d+)")
GH_RX_ALT = re.compile(r"\?gh_jid=(\d+)")
LEVER_RX = re.compile(r"jobs\.lever\.co/([^/]+)/([0-9a-f-]{8,})")
ASHBY_RX = re.compile(r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")
_WORKDAY_RX = re.compile(r"https?://(?:[a-z0-9-]+\.wd\d+\.myworkdayjobs|wd\d+\.myworkdaysite)\.com/", re.I)
# CHAIN_033 2026-05-30: added optional locale prefix (e.g. /en-US/) to handle Daloopa 1243.
RIPPLING_RX = re.compile(r"ats\.rippling\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)/jobs/([A-Za-z0-9-]{6,})", re.I)
# chain_034a 2026-05-30: BambooHR-hosted careers pages
# (<tenant>.bamboohr.com/careers/<id>, /jobs/view.php?id=<n>, /jobs/embed2.php?id=<n>).
BAMBOOHR_RX = re.compile(r"([a-z0-9-]+)\.bamboohr\.com/(?:careers/(\d+)|jobs/(?:view|embed2)\.php\?id=(\d+))", re.I)

# iCIMS career portals: careers-<co>.icims.com/jobs/<reqId>/<slug>/job (also
# jobs.icims.com/... and <co>.icims.com/...). Capture the tenant host + reqId.
ICIMS_RX = re.compile(r"https?://([a-z0-9-]+)\.icims\.com/jobs/(\d+)", re.I)

# Greenhouse-iframe wrappers (Datadog, Databricks, Stripe, etc. — CUSTOM-ATS-SCOUT-2026-05-13).
sys.path.insert(0, str(HERE / "adapters"))
from greenhouse_iframe import (  # noqa: E402
    host_to_gh_slug as _gh_iframe_slug,
    extract_gh_jid as _gh_iframe_jid,
    embed_iframe_url as _gh_iframe_embed_url,
    synthetic_jd_url as _gh_iframe_synth_url,
)


NL_CONST = chr(10)


def detect_ats(url: str) -> str:
    """Return 'greenhouse' | 'greenhouse_iframe' | 'ashby' | 'lever' | 'workday' | 'rippling' | 'bamboohr' | 'meta' | 'unknown'."""
    u = url or ""
    if "greenhouse.io" in u:
        return "greenhouse"
    if "ashbyhq.com" in u:
        return "ashby"
    if "lever.co" in u:
        return "lever"
    if _WORKDAY_RX.search(u):
        return "workday"
    if RIPPLING_RX.search(u):
        return "rippling"
    if BAMBOOHR_RX.search(u):
        return "bamboohr"
    if "metacareers.com" in u:
        return "meta"
    if ICIMS_RX.search(u) or ".icims.com" in u:
        return "icims"
    if _gh_iframe_slug(u) and _gh_iframe_jid(u):
        return "greenhouse_iframe"
    return "unknown"


def parse_bamboohr_url(url: str) -> tuple[str, str] | None:
    """Return (tenant, job_id) or None. See bamboohr_filler for full spec."""
    m = BAMBOOHR_RX.search(url or "")
    if not m:
        return None
    tenant = m.group(1)
    job_id = m.group(2) or m.group(3)
    return (tenant, job_id) if job_id else None


def parse_icims_url(url: str) -> tuple[str, str] | None:
    """Return (tenant_host, req_id) or None for an iCIMS career-portal URL.

    iCIMS URL shape: https://careers-<co>.icims.com/jobs/<reqId>/<slug>/job
    (also jobs.icims.com/jobs/<reqId>/... and <co>.icims.com/jobs/<reqId>/...).
    The runner (_icims_runner.py) drives JD -> Apply -> email/OTP -> form ->
    submit over CDP, so we only need the tenant host + reqId for bookkeeping."""
    m = ICIMS_RX.search(url or "")
    if not m:
        return None
    return m.group(1), m.group(2)


def parse_rippling_url(url: str) -> tuple[str, str] | None:
    """Return (board_slug, job_uuid) or None.

    Rippling URL shape: https://ats.rippling.com/<slug>/jobs/<uuid>.
    See rippling_filler.py for the direct-API submit flow.
    """
    m = RIPPLING_RX.search(url or "")
    if m:
        return m.group(1), m.group(2)
    return None


def parse_ashby_url(url: str) -> tuple[str, str] | None:
    m = ASHBY_RX.search(url or "")
    if m:
        return m.group(1), m.group(2)
    return None


def parse_lever_url(url: str) -> tuple[str, str] | None:
    m = LEVER_RX.search(url or "")
    if m:
        return m.group(1), m.group(2)
    return None


def parse_workday_url(url: str) -> dict | None:
    """Return {host,tenant,site,job_path,reqid} or None. Delegates to workday_dryrun."""
    try:
        sys.path.insert(0, str(HERE))
        from workday_dryrun import parse_workday_url as _pw  # noqa: WPS433
        return _pw(url)
    except Exception:
        return None


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s_]+", "-", s)[:60]


# ---------------------------------------------------------------------------
# Ashby tenant-embed fallback (chain ashby-tenant-embed-2026-05-30)
#
# Ashby's hosted application page (jobs.ashbyhq.com/<tenant>/<id>/application)
# loads a reCAPTCHA Enterprise v3 sitekey on every tenant; on Azure DC egress
# the v3 score gate dead-letters every submit (TOOLS.md "UA fix is NOT
# sufficient"). A handful of tenants (currently only Cursor in production)
# inline the Ashby form on their own public website without that captcha. For
# those tenants we rewrite plan["url"] from the ashbyhq.com URL to the
# tenant-embed URL before dispatch. ashby_filler emits the same step sequence
# either way (the in-page widgets are identical React components).
#
# Registry source of truth: ashby_tenant_embed_registry.json. To add a tenant,
# run role-discovery/sweep_ashby_tenant_embeds.py and require:
#   - GraphQL ApiOrganizationFromHostedJobsPageName.publicWebsite returns a URL
#   - rendered embed page has #_systemfield_resume + >= 1 file input
#   - no recaptcha/hcaptcha/turnstile scripts or globals
# ---------------------------------------------------------------------------

ASHBY_TENANT_EMBED_REGISTRY_PATH = HERE / "ashby_tenant_embed_registry.json"


def load_ashby_tenant_embed_registry() -> dict:
    """Return the parsed registry, or {} on missing/malformed file. Safe to
    call at import time / on each role (small JSON, no network)."""
    try:
        if not ASHBY_TENANT_EMBED_REGISTRY_PATH.exists():
            return {}
        data = json.loads(ASHBY_TENANT_EMBED_REGISTRY_PATH.read_text())
        return data.get("tenants") or {}
    except Exception:
        return {}


def _ashby_tenant_embed_fallback(
    ash_org: str,
    ash_jid: str,
    role_title: str | None = None,
    embed_slug_override: str | None = None,
    registry: dict | None = None,
) -> dict | None:
    """Resolve the tenant-embed URL for an Ashby (org, jid) pair, or return None
    when no clean-embed entry is registered.

    Args:
        ash_org: Ashby hosted-jobs page name (e.g. "cursor").
        ash_jid: Ashby job UUID.
        role_title: JD title (used when slug_mode='role_slug').
        embed_slug_override: explicit slug from tracker.agent_notes
            ("embed_slug:<value>") that overrides the template's slug_mode.
        registry: optional pre-loaded registry dict (for tests).

    Returns:
        {"embed_url": <str>, "tenant_entry": <dict>, "slug": <str>,
         "slug_mode": <str>} when the tenant is in the registry AND captcha_clean,
        else None.
    """
    reg = registry if registry is not None else load_ashby_tenant_embed_registry()
    if not reg:
        return None
    # Tenant key match is case-insensitive vs. the Ashby hosted-jobs-page name.
    entry = None
    for k, v in reg.items():
        if k.lower() == (ash_org or "").lower():
            entry = v
            break
    if not entry:
        return None
    if not entry.get("captcha_clean"):
        return None
    template = entry.get("embed_url_template")
    if not template:
        return None
    slug_mode = entry.get("slug_mode", "role_slug")

    if embed_slug_override:
        slug = embed_slug_override
        slug_mode_used = "override"
    elif slug_mode == "job_id":
        slug = ash_jid
        slug_mode_used = "job_id"
    elif slug_mode == "role_slug":
        if not role_title:
            return None
        slug = slugify(role_title)
        slug_mode_used = "role_slug"
    else:  # custom — needs override
        return None

    try:
        embed_url = template.format(role_slug=slug, job_id=slug, slug=slug)
    except Exception:
        return None
    return {
        "embed_url": embed_url,
        "tenant_entry": entry,
        "slug": slug,
        "slug_mode": slug_mode_used,
    }


def html_to_md(html: str) -> str:
    s = unescape(html)
    s = re.sub(r"(?is)<br\s*/?>", "\n", s)
    s = re.sub(r"(?is)</p>", "\n\n", s)
    s = re.sub(r"(?is)</div>", "\n", s)
    s = re.sub(r"(?is)</li>", "\n", s)
    s = re.sub(r"(?is)<li[^>]*>", "- ", s)
    s = re.sub(r"(?is)</h[1-6]>", "\n\n", s)
    s = re.sub(r"(?is)<h([1-6])[^>]*>", lambda m: "\n" + "#" * int(m.group(1)) + " ", s)
    s = re.sub(r"(?is)<strong[^>]*>(.*?)</strong>", r"**\1**", s)
    s = re.sub(r"(?is)<b[^>]*>(.*?)</b>", r"**\1**", s)
    s = re.sub(r"(?is)<em[^>]*>(.*?)</em>", r"*\1*", s)
    s = re.sub(r"(?is)<a[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"[\2](\1)", s)
    s = re.sub(r"(?s)<[^>]+>", "", s)
    s = unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_gh_url(url: str) -> tuple[str, str] | None:
    """Return (gh_org, gh_jid) or None."""
    m = GH_RX.search(url or "")
    if m:
        return m.group(1), m.group(2)
    # embed form variant: .../embed/job_app?for=<org>&token=<jid> (Stripe etc.)
    me = re.search(r"greenhouse\.io/embed/job_app\?[^#]*\bfor=([^&]+)&[^#]*\btoken=(\d+)", url or "")
    if me:
        return me.group(1), me.group(2)
    # also tolerate token before for=
    me2 = re.search(r"greenhouse\.io/embed/job_app\?[^#]*\btoken=(\d+)&[^#]*\bfor=([^&]+)", url or "")
    if me2:
        return me2.group(2), me2.group(1)
    return None


def resolve_role(role_id: int, conn: sqlite3.Connection) -> dict:
    row = conn.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
    if not row:
        raise ValueError(f"role id={role_id} not found")
    if row["applied_on"]:
        raise ValueError(f"role id={role_id} already applied on {row['applied_on']} by {row['applied_by']}")
    url = row["app_url"] or row["jd_url"]
    ats = detect_ats(url)
    if ats == "greenhouse":
        gh = parse_gh_url(url)
        if not gh:
            raise ValueError(f"role id={role_id} URL parsed as Greenhouse but no jid: {url}")
        gh_org, gh_jid = gh
        slug = f"{slugify(row['company'])}-{gh_jid}"
        return {
            "role_id": row["id"], "company": row["company"], "role": row["role"],
            "loc": row["loc"], "exp_req": row["exp_req"], "url": url,
            "ats": "greenhouse", "gh_org": gh_org, "gh_jid": gh_jid,
            "slug": slug, "flags": row["flags"],
        }
    if ats == "greenhouse_iframe":
        gh_org = _gh_iframe_slug(url)
        gh_jid = _gh_iframe_jid(url)
        if not (gh_org and gh_jid):
            raise ValueError(f"role id={role_id} URL parsed as GH-iframe but missing slug/jid: {url}")
        slug = f"{slugify(row['company'])}-{gh_jid}"
        return {
            "role_id": row["id"], "company": row["company"], "role": row["role"],
            "loc": row["loc"], "exp_req": row["exp_req"], "url": url,
            "ats": "greenhouse_iframe", "gh_org": gh_org, "gh_jid": gh_jid,
            "wrapper_url": url,
            "embed_url": _gh_iframe_embed_url(gh_org, gh_jid),
            "slug": slug, "flags": row["flags"],
        }
    if ats == "ashby":
        ash = parse_ashby_url(url)
        if not ash:
            raise ValueError(f"role id={role_id} URL parsed as Ashby but no UUID: {url}")
        ash_org, ash_jid = ash
        slug = f"{slugify(row['company'])}-{ash_jid}"
        return {
            "role_id": row["id"], "company": row["company"], "role": row["role"],
            "loc": row["loc"], "exp_req": row["exp_req"], "url": url,
            "ats": "ashby", "ash_org": ash_org, "ash_jid": ash_jid,
            # Compat aliases so downstream calls (bullet_rewriter, etc.) that
            # used --org/--job-id keep working.
            "gh_org": ash_org, "gh_jid": ash_jid,
            "slug": slug, "flags": row["flags"],
        }
    if ats == "lever":
        lv = parse_lever_url(url)
        if not lv:
            raise ValueError(f"role id={role_id} URL parsed as Lever but no jobid: {url}")
        lv_org, lv_jid = lv
        slug = f"{slugify(row['company'])}-{lv_jid[:8]}"
        return {
            "role_id": row["id"], "company": row["company"], "role": row["role"],
            "loc": row["loc"], "exp_req": row["exp_req"], "url": url,
            "ats": "lever", "lv_org": lv_org, "lv_jid": lv_jid,
            "slug": slug, "flags": row["flags"],
        }
    if ats == "workday":
        wd = parse_workday_url(url)
        if not wd:
            raise ValueError(f"role id={role_id} URL parsed as Workday but not parseable: {url}")
        slug = f"{slugify(row['company'])}-{wd['reqid'].lower()}"
        return {
            "role_id": row["id"], "company": row["company"], "role": row["role"],
            "loc": row["loc"], "exp_req": row["exp_req"], "url": url,
            "ats": "workday",
            "wd_host": wd["host"], "wd_tenant": wd["tenant"],
            "wd_site": wd["site"], "wd_job_path": wd["job_path"],
            "wd_reqid": wd["reqid"],
            # Compat aliases for bullet_rewriter's --org/--job-id.
            "gh_org": f"workday-{wd['tenant']}",
            "gh_jid": wd["reqid"],
            "slug": slug, "flags": row["flags"],
        }
    if ats == "rippling":
        rp = parse_rippling_url(url)
        if not rp:
            raise ValueError(f"role id={role_id} URL parsed as Rippling but not parseable: {url}")
        rp_slug, rp_jid = rp
        slug = f"{slugify(row['company'])}-{rp_jid[:8]}"
        return {
            "role_id": row["id"], "company": row["company"], "role": row["role"],
            "loc": row["loc"], "exp_req": row["exp_req"], "url": url,
            "ats": "rippling", "rp_slug": rp_slug, "rp_jid": rp_jid,
            # Compat aliases so bullet_rewriter's --org/--job-id keep working.
            "gh_org": f"rippling-{rp_slug}",
            "gh_jid": rp_jid[:8],
            "slug": slug, "flags": row["flags"],
        }
    if ats == "bamboohr":
        bb = parse_bamboohr_url(url)
        if not bb:
            raise ValueError(f"role id={role_id} URL parsed as BambooHR but not parseable: {url}")
        bb_tenant, bb_jid = bb
        slug = f"{slugify(row['company'])}-{bb_jid}"
        return {
            "role_id": row["id"], "company": row["company"], "role": row["role"],
            "loc": row["loc"], "exp_req": row["exp_req"], "url": url,
            "ats": "bamboohr", "bb_tenant": bb_tenant, "bb_jid": bb_jid,
            "gh_org": f"bamboohr-{bb_tenant}",
            "gh_jid": bb_jid,
            "slug": slug, "flags": row["flags"],
        }
    if ats == "meta":
        import re as _re
        m = _re.search(r"/([0-9]{10,})", url)
        job_id = m.group(1) if m else ""
        slug = f"{slugify(row['company'])}-{job_id[:12]}"
        return {
            "role_id": row["id"], "company": row["company"], "role": row["role"],
            "loc": row["loc"], "exp_req": row["exp_req"], "url": url,
            "ats": "meta", "job_id": job_id,
            "slug": slug, "flags": row["flags"],
        }
    if ats == "icims":
        ic = parse_icims_url(url)
        ic_host, ic_reqid = ic if ic else ("", "")
        slug = f"{slugify(row['company'])}-{ic_reqid}" if ic_reqid else slugify(row["company"])
        return {
            "role_id": row["id"], "company": row["company"], "role": row["role"],
            "loc": row["loc"], "exp_req": row["exp_req"], "url": url,
            "ats": "icims", "icims_host": ic_host, "icims_reqid": ic_reqid,
            "slug": slug, "flags": row["flags"],
        }
    raise ValueError(f"role id={role_id} has unsupported ATS URL: {url}")


def pick_batch(n: int, conn: sqlite3.Connection, ats_filter: str | None = None) -> list[dict]:
    """Pick next N open Greenhouse OR Ashby roles not yet applied and not in queued/.
    ats_filter: 'greenhouse' | 'ashby' | None (both)."""
    queued = set(os.listdir(QUEUED_DIR)) if QUEUED_DIR.exists() else set()
    submitted = set(os.listdir(SUBMITTED_DIR)) if SUBMITTED_DIR.exists() else set()
    where_url = []
    if ats_filter in (None, "greenhouse"):
        where_url.append("app_url LIKE '%greenhouse.io%' OR jd_url LIKE '%greenhouse.io%'")
    if ats_filter in (None, "ashby"):
        where_url.append("app_url LIKE '%ashbyhq.com%' OR jd_url LIKE '%ashbyhq.com%'")
    if ats_filter in (None, "lever"):
        where_url.append("app_url LIKE '%lever.co%' OR jd_url LIKE '%lever.co%'")
    if ats_filter in (None, "greenhouse_iframe"):
        # Match any URL with gh_jid= (covers all 13 iframe wrapper hosts plus
        # native GH URLs; native ones get filtered back out by detect_ats).
        where_url.append("app_url LIKE '%gh_jid=%' OR jd_url LIKE '%gh_jid=%'")
    if ats_filter in (None, "workday"):
        where_url.append("app_url LIKE '%myworkdayjobs.com%' OR jd_url LIKE '%myworkdayjobs.com%' OR app_url LIKE '%myworkdaysite.com%' OR jd_url LIKE '%myworkdaysite.com%'")
    if ats_filter in (None, "rippling"):
        where_url.append("app_url LIKE '%ats.rippling.com%' OR jd_url LIKE '%ats.rippling.com%'")
    if ats_filter in (None, "bamboohr"):
        where_url.append("app_url LIKE '%.bamboohr.com%' OR jd_url LIKE '%.bamboohr.com%'")
    if ats_filter in (None, "meta"):
        where_url.append("app_url LIKE '%metacareers.com%' OR jd_url LIKE '%metacareers.com%'")
    where_clause = " OR ".join(where_url) or "1=0"
    rows = conn.execute(f"""
        SELECT * FROM roles
         WHERE (status IS NULL OR status='' OR status='queued')
           AND applied_on IS NULL
           AND (prep_status IS NULL OR prep_status='')
           AND ({where_clause})
         ORDER BY
           -- Role-type priority (Cyrus 2026-05-30): PM/TPM/EPM first, then SE/SA tier, then everything else.
           CASE
             WHEN role LIKE '%Product Manager%' OR role LIKE '%Program Manager%'
               OR role LIKE '%Project Manager%' OR role LIKE '%Product Marketing Manager%'
               OR role LIKE '% PM %' OR role LIKE '% PM' OR role LIKE 'PM %'
               OR role LIKE '% TPM %' OR role LIKE '% TPM' OR role LIKE 'TPM %'
               OR role LIKE '% EPM %' OR role LIKE '% EPM' OR role LIKE 'EPM %'
               OR role LIKE '% APM %' OR role LIKE '% APM' OR role LIKE 'APM %'
               OR role LIKE '% PgM %' OR role LIKE '% PgM' OR role LIKE 'PgM %'
             THEN 1
             WHEN role LIKE '%Solution%Engineer%' OR role LIKE '%Solution%Architect%'
               OR role LIKE '%Sales Engineer%' OR role LIKE '%Customer Engineer%'
               OR role LIKE '% SE %' OR role LIKE '% SE' OR role LIKE 'SE %'
               OR role LIKE '% SA %' OR role LIKE '% SA' OR role LIKE 'SA %'
             THEN 2
             ELSE 3
           END,
           company, id
    """).fetchall()
    out = []
    for r in rows:
        url = r["app_url"] or r["jd_url"]
        ats = detect_ats(url)
        if ats == "greenhouse":
            gh = parse_gh_url(url)
            if not gh:
                continue
            org, jid = gh
            slug = f"{slugify(r['company'])}-{jid}"
            entry = {
                "role_id": r["id"], "company": r["company"], "role": r["role"],
                "loc": r["loc"], "exp_req": r["exp_req"], "url": url,
                "ats": "greenhouse", "gh_org": org, "gh_jid": jid,
                "slug": slug, "flags": r["flags"],
            }
        elif ats == "ashby":
            ash = parse_ashby_url(url)
            if not ash:
                continue
            org, jid = ash
            slug = f"{slugify(r['company'])}-{jid}"
            entry = {
                "role_id": r["id"], "company": r["company"], "role": r["role"],
                "loc": r["loc"], "exp_req": r["exp_req"], "url": url,
                "ats": "ashby", "ash_org": org, "ash_jid": jid,
                "gh_org": org, "gh_jid": jid,  # compat aliases
                "slug": slug, "flags": r["flags"],
            }
        elif ats == "lever":
            lv = parse_lever_url(url)
            if not lv:
                continue
            org, jid = lv
            slug = f"{slugify(r['company'])}-{jid[:8]}"
            entry = {
                "role_id": r["id"], "company": r["company"], "role": r["role"],
                "loc": r["loc"], "exp_req": r["exp_req"], "url": url,
                "ats": "lever", "lv_org": org, "lv_jid": jid,
                "slug": slug, "flags": r["flags"],
            }
        elif ats == "greenhouse_iframe":
            gh_org = _gh_iframe_slug(url)
            gh_jid = _gh_iframe_jid(url)
            if not (gh_org and gh_jid):
                continue
            slug = f"{slugify(r['company'])}-{gh_jid}"
            entry = {
                "role_id": r["id"], "company": r["company"], "role": r["role"],
                "loc": r["loc"], "exp_req": r["exp_req"], "url": url,
                "ats": "greenhouse_iframe", "gh_org": gh_org, "gh_jid": gh_jid,
                "wrapper_url": url,
                "embed_url": _gh_iframe_embed_url(gh_org, gh_jid),
                "slug": slug, "flags": r["flags"],
            }
        elif ats == "workday":
            wd = parse_workday_url(url)
            if not wd:
                continue
            # skip roles that already have a prep packet
            if r.keys() and "prep_status" in r.keys() and r["prep_status"] in ("manual_ready", "submitted"):
                continue
            slug = f"{slugify(r['company'])}-{wd['reqid'].lower()}"
            entry = {
                "role_id": r["id"], "company": r["company"], "role": r["role"],
                "loc": r["loc"], "exp_req": r["exp_req"], "url": url,
                "ats": "workday",
                "wd_host": wd["host"], "wd_tenant": wd["tenant"],
                "wd_site": wd["site"], "wd_job_path": wd["job_path"],
                "wd_reqid": wd["reqid"],
                "gh_org": f"workday-{wd['tenant']}",
                "gh_jid": wd["reqid"],
                "slug": slug, "flags": r["flags"],
            }
        elif ats == "rippling":
            rp = parse_rippling_url(url)
            if not rp:
                continue
            rp_slug, rp_jid = rp
            slug = f"{slugify(r['company'])}-{rp_jid[:8]}"
            entry = {
                "role_id": r["id"], "company": r["company"], "role": r["role"],
                "loc": r["loc"], "exp_req": r["exp_req"], "url": url,
                "ats": "rippling", "rp_slug": rp_slug, "rp_jid": rp_jid,
                "gh_org": f"rippling-{rp_slug}",
                "gh_jid": rp_jid[:8],
                "slug": slug, "flags": r["flags"],
            }
        elif ats == "bamboohr":
            bb = parse_bamboohr_url(url)
            if not bb:
                continue
            bb_tenant, bb_jid = bb
            slug = f"{slugify(r['company'])}-{bb_jid}"
            entry = {
                "role_id": r["id"], "company": r["company"], "role": r["role"],
                "loc": r["loc"], "exp_req": r["exp_req"], "url": url,
                "ats": "bamboohr", "bb_tenant": bb_tenant, "bb_jid": bb_jid,
                "gh_org": f"bamboohr-{bb_tenant}",
                "gh_jid": bb_jid,
                "slug": slug, "flags": r["flags"],
            }
        elif ats == "meta":
            import re as _re
            m = _re.search(r"/([0-9]{10,})", url)
            job_id = m.group(1) if m else ""
            slug = f"{slugify(r['company'])}-{job_id[:12]}"
            entry = {
                "role_id": r["id"], "company": r["company"], "role": r["role"],
                "loc": r["loc"], "exp_req": r["exp_req"], "url": url,
                "ats": "meta", "job_id": job_id,
                "slug": slug, "flags": r["flags"],
            }
        else:
            continue
        if entry["slug"] in queued or entry["slug"] in submitted:
            continue
        # Overreach guard (Cyrus 2026-05-17): skip roles requiring >=8 YOE
        # or with people-management language in title. JD scan is also done
        # post-prep in prep_role() once JD body is available.
        from core import is_overreach as _is_overreach
        ovr, reason = _is_overreach(entry.get("exp_req"), None, entry.get("role"))
        if ovr:
            _log_skipped_overreach(entry, reason, phase="pick_batch")
            continue
        # Role-type + company blocklist guard (defense-in-depth, added 2026-06-02).
        # The classifier blocklist runs at classify time, but already-staged rows
        # (status NULL/''/queued) bypass it -> 17 FDE roles leaked to SUBMIT
        # 05-30..06-02. Re-check title role-type (FDE hard-block etc.) AND company
        # blocklist here so submission workers can NEVER apply to an excluded role.
        try:
            from jd_llm_classifier import extract_title_skip as _ets, company_is_blocked as _cbm
        except Exception:
            _ets = _cbm = None
        if _ets is not None:
            _skipkw = _ets(entry.get("role"))
            if _skipkw:
                _log_skipped_overreach(entry, f"role-type-blocklist:{_skipkw}", phase="pick_batch-blocklist")
                continue
        if _cbm is not None:
            _cb = _cbm(entry.get("company"))
            if _cb:
                _log_skipped_overreach(entry, f"company-blocked:{_cb}", phase="pick_batch-blocklist")
                continue
        out.append(entry)
        if len(out) >= n:
            break
    return out


SKIPPED_OVERREACH_FILE = PROJECT / "applications" / "_skipped-overreach.json"


def _log_skipped_overreach(entry: dict, reason: str, phase: str = "") -> None:
    """Append a skipped-overreach entry to applications/_skipped-overreach.json."""
    try:
        SKIPPED_OVERREACH_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(SKIPPED_OVERREACH_FILE.read_text())
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
        data.append({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "role_id": entry.get("role_id"),
            "company": entry.get("company"),
            "role": entry.get("role"),
            "ats": entry.get("ats"),
            "exp_req": entry.get("exp_req"),
            "url": entry.get("url"),
            "reason": reason,
            "phase": phase,
        })
        SKIPPED_OVERREACH_FILE.write_text(json.dumps(data, indent=2) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Phase 1: fetch JD + write meta + prefill
# ---------------------------------------------------------------------------

def fetch_jd_lever(lv_org: str, lv_jid: str) -> dict:
    """Fetch one Lever posting via the public board API."""
    api = f"https://api.lever.co/v0/postings/{lv_org}/{lv_jid}?mode=json"
    r = requests.get(api, timeout=20, headers={"User-Agent": "job-search-agent/1.0"})
    r.raise_for_status()
    return r.json()


def write_jd_files_lever(workdir: Path, role: dict, data: dict) -> None:
    title = data.get("text", role["role"])
    cat = data.get("categories") or {}
    loc = cat.get("location") or role["loc"] or ""
    apply_url = data.get("applyUrl") or (data.get("hostedUrl", "") + "/apply")
    hosted_url = data.get("hostedUrl") or role["url"]
    desc_plain = data.get("descriptionPlain") or ""
    lists = data.get("lists") or []
    parts = [desc_plain]
    for lst in lists:
        if isinstance(lst, dict):
            parts.append("\n## " + (lst.get("text") or "") + "\n")
            parts.append(html_to_md(lst.get("content") or ""))
    closing = data.get("additionalPlain") or ""
    if closing:
        parts.append("\n" + closing)
    jd_md = "\n".join(p for p in parts if p)
    (workdir / "JD.md").write_text(
        f"# {title}\n\n**Company:** {role['company']}\n**Location:** {loc}\n"
        f"**Apply:** {apply_url}\n**Lever ID:** {role['lv_jid']}\n\n---\n\n{jd_md}\n"
    )
    meta = {
        "company": role["company"], "role": title, "location": loc,
        "exp_required": role["exp_req"], "apply_url": apply_url,
        "jd_url": hosted_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ats": "lever", "lv_org": role["lv_org"], "lv_jid": role["lv_jid"],
        "flags": role["flags"] or "",
    }
    (workdir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    personal = json.loads(PERSONAL_INFO.read_text())
    (workdir / "prefill.json").write_text(json.dumps(personal, indent=2) + "\n")


def fetch_jd(gh_org: str, gh_jid: str) -> dict:
    api = f"https://boards-api.greenhouse.io/v1/boards/{gh_org}/jobs/{gh_jid}"
    r = requests.get(api, timeout=20, headers={"User-Agent": "job-search-agent/1.0"})
    r.raise_for_status()
    return r.json()


def fetch_jd_ashby(ash_org: str, ash_jid: str) -> dict:
    """Fetch the public Ashby posting via the posting-api."""
    api = f"https://api.ashbyhq.com/posting-api/job-board/{ash_org}?includeCompensation=true"
    r = requests.get(api, timeout=20, headers={"User-Agent": "job-search-agent/1.0"})
    r.raise_for_status()
    data = r.json()
    for job in data.get("jobs") or []:
        if job.get("id") == ash_jid:
            return job
    raise RuntimeError(f"Ashby job {ash_jid} not found in board for {ash_org}")


def write_jd_files(workdir: Path, role: dict, data: dict) -> None:
    title = data.get("title", role["role"])
    loc = (data.get("location") or {}).get("name", role["loc"] or "")
    absolute_url = data.get("absolute_url", role["url"])
    content_html = data.get("content", "")
    jd_md = html_to_md(content_html)

    (workdir / "JD.md").write_text(
        f"# {title}\n\n**Company:** {role['company']}\n**Location:** {loc}\n"
        f"**Apply:** {absolute_url}\n**Greenhouse ID:** {role['gh_jid']}\n\n---\n\n{jd_md}\n"
    )
    meta = {
        "company": role["company"], "role": title, "location": loc,
        "exp_required": role["exp_req"], "apply_url": absolute_url,
        "jd_url": absolute_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ats": "greenhouse", "gh_org": role["gh_org"], "gh_jid": role["gh_jid"],
        "flags": role["flags"] or "",
    }
    (workdir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    personal = json.loads(PERSONAL_INFO.read_text())
    (workdir / "prefill.json").write_text(json.dumps(personal, indent=2) + "\n")


def write_jd_files_ashby(workdir: Path, role: dict, data: dict) -> None:
    """Ashby posting-api shape: {title, location, descriptionHtml, jobUrl,
    employmentType, departmentName, ...}."""
    title = data.get("title", role["role"])
    loc = data.get("location") or role["loc"] or ""
    absolute_url = data.get("jobUrl") or role["url"]
    content_html = data.get("descriptionHtml") or data.get("descriptionPlain") or ""
    jd_md = html_to_md(content_html) if "<" in content_html else content_html

    (workdir / "JD.md").write_text(
        f"# {title}\n\n**Company:** {role['company']}\n**Location:** {loc}\n"
        f"**Apply:** {absolute_url}\n**Ashby Org:** {role['ash_org']}\n**Ashby Job ID:** {role['ash_jid']}\n\n---\n\n{jd_md}\n"
    )
    meta = {
        "company": role["company"], "role": title, "location": loc,
        "exp_required": role["exp_req"], "apply_url": absolute_url,
        "jd_url": absolute_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ats": "ashby", "ash_org": role["ash_org"], "ash_jid": role["ash_jid"],
        # Compat aliases so older tooling that reads gh_org/gh_jid keeps working.
        "gh_org": role["ash_org"], "gh_jid": role["ash_jid"],
        "flags": role["flags"] or "",
        "employment_type": data.get("employmentType"),
        "department": data.get("departmentName"),
        "published_date": data.get("publishedDate"),
    }
    (workdir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    personal = json.loads(PERSONAL_INFO.read_text())
    (workdir / "prefill.json").write_text(json.dumps(personal, indent=2) + "\n")


# ---------------------------------------------------------------------------
# Phase 2: dryrun spec
# ---------------------------------------------------------------------------

def run_dryrun(absolute_url: str, gh_org: str, gh_jid: str, ats: str = "greenhouse") -> Path:
    """Generate the form-fill dryrun spec. Returns path to JSON.
    `ats` selects which dryrun script to run."""
    spec_path = DRYRUN_DIR / f"{gh_org}-{gh_jid}.json"
    if spec_path.exists():
        # Refresh: still re-run; specs can stale.
        pass
    if ats == "ashby":
        script = HERE / "ashby_dryrun.py"
    else:
        script = HERE / "greenhouse_dryrun.py"
    res = subprocess.run(
        [str(VENV_PY), str(script), absolute_url, "--quiet"],
        capture_output=True, text=True, timeout=60,
    )
    if res.returncode != 0:
        raise RuntimeError(f"{script.name} failed (rc={res.returncode}): {res.stderr[:500]}")
    if not spec_path.exists():
        raise RuntimeError(f"dryrun spec not written: expected {spec_path}")
    return spec_path


def run_dryrun_lever(role_url: str, lv_org: str, lv_jid: str) -> Path:
    """Generate the Lever form-fill dryrun spec. Returns path to JSON."""
    spec_path = DRYRUN_DIR / f"lever-{lv_org}-{lv_jid}.json"
    res = subprocess.run(
        [str(VENV_PY), str(HERE / "lever_dryrun.py"), role_url, "--quiet"],
        capture_output=True, text=True, timeout=60,
    )
    if res.returncode != 0:
        raise RuntimeError(f"lever_dryrun.py failed (rc={res.returncode}): {res.stderr[:500]}")
    if not spec_path.exists():
        raise RuntimeError(f"lever dryrun spec not written: expected {spec_path}")
    return spec_path


# ---------------------------------------------------------------------------
# Phase 3: tailor resume (bullet_rewriter --render)
# ---------------------------------------------------------------------------

def run_bullet_rewriter(slug: str, workdir: Path, gh_org: str, gh_jid: str,
                        timeout_s: int = 360) -> Path:
    """Run bullet_rewriter --render. Uses a queued→submitted symlink shim
    because bullet_rewriter hardcodes APPS_DIR=applications/queued. Returns
    path to the rendered PDF."""
    QUEUED_DIR.mkdir(parents=True, exist_ok=True)
    shim = QUEUED_DIR / slug
    org_shim = QUEUED_DIR / f"{gh_org}-{gh_jid}"  # bullet_rewriter expects {gh_org}-{jid}
    created_shim = False
    created_org_shim = False
    if shim.exists() or shim.is_symlink():
        # Pre-existing — leave it; don't risk clobbering Cyrus's work.
        # Caller workdir might already be queued/<slug> in that case.
        pass
    else:
        shim.symlink_to(workdir, target_is_directory=True)
        created_shim = True
    if org_shim != shim and not (org_shim.exists() or org_shim.is_symlink()):
        org_shim.symlink_to(workdir, target_is_directory=True)
        created_org_shim = True
    try:
        res = subprocess.run(
            [str(VENV_PY), str(HERE / "bullet_rewriter.py"),
             "--org", gh_org, "--job-id", gh_jid, "--render", "--max-loops", "3"],
            capture_output=True, text=True, timeout=timeout_s,
        )
        if res.returncode != 0:
            raise RuntimeError(f"bullet_rewriter failed (rc={res.returncode}): {res.stderr[-1500:]}")
    finally:
        if created_shim and shim.is_symlink():
            shim.unlink()
        if created_org_shim and org_shim.is_symlink():
            org_shim.unlink()
    pdf_name = f"Cyrus_Shekari_Resume_{gh_org}_{gh_jid}_v2.pdf"
    docx_name = f"Cyrus_Shekari_Resume_{gh_org}_{gh_jid}_v2.docx"
    pdf = workdir / pdf_name
    if not pdf.exists():
        # bullet_rewriter may have written into a real queued/ folder that
        # pre-existed (so our symlink shim couldn't be created). Look there
        # and copy artifacts into our workdir.
        for cand_dir in (org_shim, shim):
            if cand_dir.is_dir() and not cand_dir.is_symlink():
                cand_pdf = cand_dir / pdf_name
                if cand_pdf.exists():
                    for fname in (pdf_name, docx_name, "rewrites.json", "tailoring-notes.md"):
                        src = cand_dir / fname
                        if src.exists():
                            shutil.copy2(src, workdir / fname)
                    break
    if not pdf.exists():
        raise RuntimeError(f"bullet_rewriter ran but PDF missing: {pdf}")
    return pdf


# ---------------------------------------------------------------------------
# Phase 4: cover answers
# ---------------------------------------------------------------------------

def run_cover_answers(slug: str, timeout_s: int = 240) -> Path:
    res = subprocess.run(
        [str(VENV_PY), str(HERE / "cover_answer_generator.py"), "--slug", slug],
        capture_output=True, text=True, timeout=timeout_s,
    )
    if res.returncode != 0:
        raise RuntimeError(f"cover_answer_generator failed (rc={res.returncode}): {res.stderr[-1500:]}")
    # locate output
    for base in (SUBMITTED_DIR, QUEUED_DIR):
        p = base / slug / "cover_answers.md"
        if p.exists():
            return p
    raise RuntimeError(f"cover_answers.md not found after generator ran (slug={slug})")


# ---------------------------------------------------------------------------
# Phase 5: emit browser plan
# ---------------------------------------------------------------------------

_WHY_COMPANY_LABEL_RE = re.compile(
    r"\bwhy\b.{0,40}\b(work|join|interested|interest|company|us|team|here|role|excit|want)\b"
    r"|what (interests|excites|draws|attracts|motivates) you"
    r"|why (do|are) you",
    re.I,
)


def _is_why_company_label(label: str) -> bool:
    """True if a free-text label is a motivational 'why this company/role'
    essay. Cyrus directive 2026-05-31: these must be fabricated, never
    skipped."""
    if not label:
        return False
    return bool(_WHY_COMPANY_LABEL_RE.search(label))


# Structured / PII / legal / link fields that must NOT be answered with a
# generated essay (mirrors cover_answer_generator.SKIP_PATTERNS). If an
# unfilled placeholder matches this, leave it to the proper structured
# resolver / skip rather than fabricating prose.
_NON_ESSAY_LABEL_RE = re.compile(
    r"\b(resume|cv|cover letter|linkedin|web ?site|github|portfolio|url|"
    r"how did you hear|where did you hear|referred by|referral|"
    r"first name|last name|full name|preferred name|legal name|email|phone|"
    r"address|street|city|state|province|zip|postal|country|pronoun|gender|"
    r"race|ethnic|veteran|disabilit|hispanic|lgbtq|salary|compensation|"
    r"desired pay|currency|start date|earliest start|notice period|"
    r"valid driver|background check|drug screen|felony|non-?compete|"
    r"already applied|previously applied|previously employed|currently employed|"
    r"work authoriz|authoriz.{0,20}work|right to work|legally (allowed|able|authorized) to work|"
    r"sponsorship|require.{0,20}sponsor|visa|citizen|latitude|longitude|date of birth|"
    r"\bdob\b|social security|\bssn\b|"
    # Knockout questions (location/relocation/clearance) must be answered
    # TRUTHFULLY (Cyrus integrity red line #3), never fabricated as prose.
    # Exclude them here so they fall through to the integrity-aware path.
    r"relocat|currently (located|based|living|reside)|are you (located|based)|"
    r"where (are you|do you) (located|based|live|reside)|current location|"
    r"which (city|state|country|location)|security clearance|active clearance|"
    r"clearance level|willing to (relocate|move|commute)|able to commute)\b",
    re.I,
)


def _is_answerable_essay_label(label: str) -> bool:
    """True if an unfilled free-text label is an open-ended QUESTION we should
    answer (vs a structured/PII/legal field). Cyrus directive (2026-05-31):
    parse and answer EVERYTHING a company asks, not just 'why <company>'.
    Conservative: excludes the known structured/PII/legal set so we never
    fabricate prose into a name/email/salary/visa slot."""
    if not label or len(label.strip()) < 3:
        return False
    if _NON_ESSAY_LABEL_RE.search(label):
        return False
    return True


def _fallback_essay_answer(plan: dict, spec: dict, label: str) -> str:
    """Generate an answer for ANY open-ended application question the cover
    generator left unfilled, so a required essay never silently drops / blocks
    submit. LLM-first (question-aware), with a deterministic non-empty fallback.
    Truth rule: no invented biographical facts; motivational framing may be
    inferred. AI-disclaimer phrases are guarded out."""
    if _is_why_company_label(label):
        return _fallback_why_company_answer(plan, spec, label)
    company = (spec.get("org") or spec.get("company")
               or (plan.get("slug", "") or "").split("-")[0] or "the company").strip()
    title = (spec.get("job_title") or spec.get("title") or "").strip()
    company_disp = company.replace("-", " ").title()
    try:
        prompt = (
            f"You are writing a first-person application answer as job applicant "
            f"Cyrus Shekari, applying to {company_disp}"
            + (f" for the {title} role" if title else "")
            + f".\n\nApplication question:\n{label}\n\n"
            "Write a focused, specific, confident answer in Cyrus's voice. "
            "Length: 1 short paragraph for a narrow question, 2-3 short "
            "paragraphs for a broad one. Lead with the most relevant concrete "
            "experience. You MAY infer reasonable motivation/enthusiasm and "
            "opinions. Do NOT invent biographical facts (no fake employers, "
            "projects, job titles, dates, or metrics) — those must be real. "
            "If asked about something with no real basis, pivot honestly to "
            "adjacent real experience. Never write 'as an AI', 'language "
            "model', 'Claude', or 'ChatGPT'. Plain text only, no markdown, "
            "avoid em dashes. Output ONLY the answer text."
        )
        from model_config import model_run_cmd
        cmd = model_run_cmd(prompt)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode == 0:
            env = json.loads(proc.stdout)
            outs = env.get("outputs") or []
            txt = (outs[0].get("text") if outs else "") or ""
            txt = txt.strip()
            low = txt.lower()
            if txt and not any(b in low for b in ("as an ai", "language model",
                                                   "claude", "chatgpt")):
                return txt
    except Exception:
        pass
    # Deterministic non-empty fallback (no biographical fabrication).
    return (
        "From my background building and shipping technical products end to "
        "end, I bring a pragmatic, ownership-driven approach: I dig into the "
        "real problem, work cross-functionally to align on the plan, and drive "
        "it through to a measurable outcome. I'd apply that same approach here "
        f"and ramp quickly to contribute to {company_disp}'s goals."
    )


def _fallback_why_company_answer(plan: dict, spec: dict, label: str) -> str:
    """Generate a motivational 'why this company' answer when the cover
    generator left the field unfilled. Tries the LLM generator first; on any
    failure falls back to a grounded, non-fabricated-fact template so the
    field is NEVER left empty (which would block submit). Only the
    motivational framing is inferred — no biographical claims are invented."""
    company = (spec.get("org") or spec.get("company")
               or (plan.get("slug", "") or "").split("-")[0] or "your team").strip()
    title = (spec.get("job_title") or spec.get("title") or "").strip()
    company_disp = company.replace("-", " ").title()
    try:
        prompt = (
            f"Write a 2-paragraph first-person answer (as job applicant Cyrus "
            f"Shekari) to this application question for {company_disp}"
            + (f" ({title})" if title else "")
            + f":\n\n{label}\n\n"
            "Be specific, confident, and genuine-sounding about why this "
            "company and role appeal to him. You MAY infer plausible "
            "company-specific motivation. Do NOT invent any biographical "
            "facts (no fake employers, projects, metrics, or titles). No AI "
            "disclaimers, no markdown, plain text only. Avoid em dashes."
        )
        from model_config import model_run_cmd
        cmd = model_run_cmd(prompt)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if proc.returncode == 0:
            env = json.loads(proc.stdout)
            outs = env.get("outputs") or []
            txt = (outs[0].get("text") if outs else "") or ""
            txt = txt.strip()
            low = txt.lower()
            if txt and not any(b in low for b in ("as an ai", "language model",
                                                   "claude", "chatgpt")):
                return txt
    except Exception:
        pass
    # Deterministic non-empty fallback (no biographical fabrication).
    role_clause = f" the {title} role" if title else " this role"
    return (
        f"I'm drawn to {company_disp} because the problems your team is taking "
        f"on line up closely with the kind of work I want to be doing next, and "
        f"{role_clause} is a strong match for my background in building and "
        f"shipping technical products end to end. The scope here — the technical "
        f"depth combined with real customer impact — is exactly the environment "
        f"where I do my best work.\n\n"
        f"What stands out about {company_disp} specifically is the ambition of "
        f"the product and the bar the team holds for execution. I'd bring a "
        f"pragmatic, ownership-driven approach, and I'm confident I could "
        f"contribute quickly while growing alongside the team."
    )


def merge_cover_answers_into_plan(plan: dict, spec: dict, cover_path: Path) -> dict:
    """Replace any text field with the cover_answers.md answer when the field's
    label matches a `## <question>` heading in cover_answers.md. Handles both
    the Greenhouse plan shape (text_fields dict[id->value]) and the Ashby
    plan shape (text_fields list[{short_id, value, label}])."""
    if not cover_path.exists():
        plan["cover_overrides"] = []
        return plan
    text = cover_path.read_text()
    blocks: list[tuple[str, str]] = []
    cur_q = None
    cur_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if cur_q is not None:
                blocks.append((cur_q, "\n".join(cur_lines).strip()))
            cur_q = line[3:].strip()
            cur_lines = []
        elif cur_q is not None and not line.startswith("# "):
            cur_lines.append(line)
    if cur_q is not None:
        blocks.append((cur_q, "\n".join(cur_lines).strip()))
    qa = {q.strip().lower(): a for q, a in blocks if a}
    # Normalize curly punctuation -> straight so cover_answer_generator's
    # markdown headings (often re-typed by the LLM with straight quotes)
    # match the dryrun's verbatim labels (which keep curly chars from Ashby).
    def _norm(s: str) -> str:
        return (s or "").translate(str.maketrans({
            "\u2019": "'", "\u2018": "'", "\u201c": '"', "\u201d": '"',
            "\u2013": "-", "\u2014": "-", "\u00a0": " ",
        })).strip().lower()
    qa_norm = {_norm(q): a for q, a in blocks if a}

    overrides = []
    tf = plan.get("text_fields")

    if isinstance(tf, dict):
        # Greenhouse / Ashby (dict) shape
        id_to_label = {f["id"]: (f.get("label") or "").strip().lower()
                       for f in spec.get("fields") or []}
        for fid in list(tf.keys()):
            label = id_to_label.get(fid, "")
            if not label:
                continue
            ans = qa.get(label) or qa_norm.get(_norm(label))
            if ans is None:
                nlabel = _norm(label)
                for q_low, a in qa_norm.items():
                    if nlabel in q_low or q_low in nlabel:
                        ans = a; break
            if ans:
                overrides.append({"id": fid, "label": label,
                                  "old_len": len(tf[fid]),
                                  "new_len": len(ans)})
                tf[fid] = ans
    elif isinstance(tf, list):
        # Ashby shape
        for item in tf:
            label = (item.get("label") or "").strip().lower()
            if not label:
                continue
            ans = qa.get(label)
            if ans is None:
                for q_low, a in qa.items():
                    if label in q_low or q_low in label:
                        ans = a; break
            if ans:
                overrides.append({"id": item.get("short_id"), "label": label,
                                  "old_len": len(str(item.get("value", ""))),
                                  "new_len": len(ans)})
                item["value"] = ans
    # Cyrus directive (2026-05-31): NEVER leave a "why do you want to work for
    # <company>" essay (or ANY open-ended question) unfilled — generate an
    # answer rather than letting an empty/placeholder field block submit.
    # Cyrus directive (2026-05-31): parse and answer everything a company asks.
    # Applies to both the dict (Greenhouse/Ashby) and list (Ashby) shapes.
    def _looks_unfilled(v) -> bool:
        s = v if isinstance(v, str) else ""
        return (not s.strip()) or (s.startswith("<<") and s.endswith(">>"))

    if isinstance(tf, dict):
        id_to_label2 = {f["id"]: (f.get("label") or "").strip()
                        for f in spec.get("fields") or []}
        for fid, val in list(tf.items()):
            label = id_to_label2.get(fid, "")
            if _looks_unfilled(val) and _is_answerable_essay_label(label):
                ans = _fallback_essay_answer(plan, spec, label)
                tf[fid] = ans
                src = ("why_company_fallback" if _is_why_company_label(label)
                       else "essay_fallback")
                overrides.append({"id": fid, "label": label, "old_len": 0,
                                  "new_len": len(ans), "source": src})
    elif isinstance(tf, list):
        for item in tf:
            label = (item.get("label") or "").strip()
            if _looks_unfilled(item.get("value")) and _is_answerable_essay_label(label):
                ans = _fallback_essay_answer(plan, spec, label)
                item["value"] = ans
                src = ("why_company_fallback" if _is_why_company_label(label)
                       else "essay_fallback")
                overrides.append({"id": item.get("short_id"), "label": label,
                                  "old_len": 0, "new_len": len(ans),
                                  "source": src})
    plan["cover_overrides"] = overrides
    return plan


def emit_browser_plan_lever(slug: str, spec_path: Path, pdf_path: Path,
                             workdir: Path) -> Path:
    """Build the ordered Lever browser-call plan via lever_filler. Stages the
    PDF and returns the plan JSON path."""
    sys.path.insert(0, str(HERE))
    import importlib
    lf = importlib.import_module("lever_filler")
    spec = json.loads(spec_path.read_text())
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    staged_pdf = UPLOADS_DIR / pdf_path.name
    shutil.copy2(pdf_path, staged_pdf)
    plan = lf.build_plan(spec)
    plan["resume_path"] = str(staged_pdf)
    cover_path = workdir / "cover_answers.md"
    plan = _merge_cover_lever(plan, spec, cover_path)
    steps = lf.emit_steps(plan, label=slug)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"inline-plan-{slug}.json"
    out_path.write_text(json.dumps({
        "slug": slug, "ats": "lever",
        "spec_path": str(spec_path),
        "pdf_path_local": str(pdf_path), "pdf_path_staged": str(staged_pdf),
        "url": plan["url"], "text_fields": plan["text_fields"],
        "selects": plan["selects"], "radios": plan["radios"],
        "checkboxes": plan["checkboxes"], "eeo": plan["eeo"],
        "skipped": plan.get("skipped", []), "unknown": plan.get("unknown", []),
        "cover_overrides": plan.get("cover_overrides", []),
        "steps": steps,
    }, indent=2, default=str) + "\n")
    return out_path


def _merge_cover_lever(plan: dict, spec: dict, cover_path: Path) -> dict:
    if not cover_path.exists():
        plan["cover_overrides"] = []
        return plan
    text = cover_path.read_text()
    blocks: list[tuple[str, str]] = []
    cur_q = None; cur_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if cur_q is not None:
                blocks.append((cur_q, "\n".join(cur_lines).strip()))
            cur_q = line[3:].strip(); cur_lines = []
        elif cur_q is not None and not line.startswith("# "):
            cur_lines.append(line)
    if cur_q is not None:
        blocks.append((cur_q, "\n".join(cur_lines).strip()))
    qa = {q.strip().lower(): a for q, a in blocks if a}
    id_to_label = {f["id"]: (f.get("label") or "").strip().lower()
                   for f in spec.get("fields") or []}
    overrides = []
    for fid in list(plan.get("text_fields", {}).keys()):
        label = id_to_label.get(fid, "")
        if not label:
            continue
        ans = qa.get(label)
        if ans is None:
            for q_low, a in qa.items():
                if label in q_low or q_low in label:
                    ans = a; break
        if ans:
            overrides.append({"id": fid, "label": label,
                              "old_len": len(plan["text_fields"][fid]),
                              "new_len": len(ans)})
            plan["text_fields"][fid] = ans
    plan["cover_overrides"] = overrides
    # Any remaining placeholders — cover didn't fill them.
    leftover = [fid for fid, v in plan["text_fields"].items()
                if isinstance(v, str) and v.startswith("<<") and v.endswith(">>")]
    for fid in leftover:
        label = id_to_label.get(fid, "")
        # Cyrus directive (2026-05-31): NEVER drop an open-ended question —
        # answer everything a company asks rather than skipping the field
        # (which can block submit). Only structured/PII/legal fields are left
        # to the proper resolver. No biographical facts are invented.
        if label and _is_answerable_essay_label(label):
            ans = _fallback_essay_answer(plan, spec, label)
            plan["text_fields"][fid] = ans
            src = ("why_company_fallback" if _is_why_company_label(label)
                   else "essay_fallback")
            plan.setdefault("cover_overrides", []).append({
                "id": fid, "label": label, "old_len": 0,
                "new_len": len(ans), "source": src,
            })
            continue
        plan.setdefault("skipped", []).append({
            "id": fid, "reason": "placeholder-not-filled-by-cover",
            "label": label,
        })
        del plan["text_fields"][fid]
    return plan


def emit_browser_plan(slug: str, spec_path: Path, pdf_path: Path,
                      workdir: Path, override_url: str | None = None,
                      wrapper_url: str | None = None,
                      ats_label: str | None = None) -> Path:
    """Build the ordered browser-call plan via the appropriate filler module.
    Also stages the PDF into /tmp/openclaw/uploads/ so the browser tool's
    upload action can find it. Returns plan JSON path.

    `override_url`: replace plan['url'] (used by greenhouse_iframe to point
    directly at the /embed/job_app URL instead of the synthetic GH hosted URL).
    `wrapper_url`: original company-branded URL (recorded in plan for audit).
    `ats_label`: written into the plan output so the runner knows which
    branch produced it.
    """
    sys.path.insert(0, str(HERE))
    import importlib
    spec = json.loads(spec_path.read_text())
    ats = spec.get("ats", "greenhouse")

    # stage PDF
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    staged_pdf = UPLOADS_DIR / pdf_path.name
    shutil.copy2(pdf_path, staged_pdf)

    if ats == "ashby":
        af = importlib.import_module("ashby_filler")
        plan = af.build_plan(spec)
        plan["resume_path"] = str(staged_pdf)
        cover_path = workdir / "cover_answers.md"
        plan = merge_cover_answers_into_plan(plan, spec, cover_path)
        # Tenant-embed fallback (chain ashby-tenant-embed-2026-05-30): when the
        # tenant is in ashby_tenant_embed_registry.json AND captcha_clean, rewrite
        # the plan URL from jobs.ashbyhq.com/<tenant>/<id>/application to the
        # tenant's own inlined-form embed (e.g. cursor.com/careers/<role-slug>).
        # Bypasses Ashby's reCAPTCHA Enterprise v3 wall. The ashby_filler-emitted
        # steps work unchanged because the in-page widgets are the same React
        # components on either host.
        tenant_embed_meta: dict | None = None
        if not override_url:
            ash_org = spec.get("org") or spec.get("ash_org")
            ash_jid = spec.get("job_id") or spec.get("ash_jid")
            if ash_org and ash_jid:
                role_title = spec.get("title") or spec.get("role_title") or spec.get("job_title")
                embed_slug_override = None
                # Optional per-role override hook: spec["embed_slug"] (set by
                # prep_role when tracker.agent_notes contains "embed_slug:<x>").
                if isinstance(spec.get("embed_slug"), str) and spec["embed_slug"].strip():
                    embed_slug_override = spec["embed_slug"].strip()
                resolved = _ashby_tenant_embed_fallback(
                    ash_org, ash_jid,
                    role_title=role_title,
                    embed_slug_override=embed_slug_override,
                )
                if resolved:
                    tenant_embed_meta = resolved
        if tenant_embed_meta:
            original_url = plan["url"]
            plan["url"] = tenant_embed_meta["embed_url"]
            # Re-emit steps now that plan["url"] points at the embed.
            steps = af.emit_steps(plan, label=slug)
        elif override_url:
            plan["url"] = override_url
            steps = af.emit_steps(plan, label=slug)
        else:
            steps = af.emit_steps(plan, label=slug)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / f"inline-plan-{slug}.json"
        out_path.write_text(json.dumps({
            "slug": slug,
            "ats": "ashby_tenant_embed" if tenant_embed_meta else "ashby",
            "spec_path": str(spec_path),
            "pdf_path_local": str(pdf_path),
            "pdf_path_staged": str(staged_pdf),
            "url": plan["url"],
            "tenant_embed": tenant_embed_meta,
            "text_fields": plan["text_fields"],
            "radios": plan["radios"],
            "checkboxes": plan["checkboxes"],
            "resume_path": plan["resume_path"],
            "skipped": plan.get("skipped", []),
            "needs_review": plan.get("needs_review", []),
            "cover_overrides": plan.get("cover_overrides", []),
            "steps": steps,
        }, indent=2, default=str) + "\n")
        return out_path

    # greenhouse (default)
    gf = importlib.import_module("greenhouse_filler")
    plan = gf.build_plan(spec)
    plan["resume_path"] = str(staged_pdf)
    cover_path = workdir / "cover_answers.md"
    plan = merge_cover_answers_into_plan(plan, spec, cover_path)
    if override_url:
        plan["url"] = override_url
    steps = gf.emit_steps(plan, label=slug)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"inline-plan-{slug}.json"
    out_path.write_text(json.dumps({
        "slug": slug,
        "ats": ats_label or "greenhouse",
        "wrapper_url": wrapper_url,
        "spec_path": str(spec_path),
        "pdf_path_local": str(pdf_path),
        "pdf_path_staged": str(staged_pdf),
        "url": plan["url"],
        "text_fields": plan["text_fields"],
        "dropdowns": plan["dropdowns"],
        "country_dropdowns": plan.get("country_dropdowns", []),
        "phone_iti": plan.get("phone_iti", []),
        "needs_review_dropdowns": plan.get("needs_review_dropdowns", []),
        "_education": plan.get("_education", {}),
        "skipped": plan.get("skipped", []),
        "unknown": plan.get("unknown", []),
        "cover_overrides": plan.get("cover_overrides", []),
        "steps": steps,
    }, indent=2, default=str) + "\n")
    return out_path


# ---------------------------------------------------------------------------
# Per-role driver
# ---------------------------------------------------------------------------

def write_jd_files_workday(workdir: Path, role: dict, spec: dict) -> str:
    """Write JD.md, meta.json, prefill.json for a Workday role from the dryrun spec.
    Returns the apply URL."""
    title = spec.get("job_title") or role["role"]
    loc = spec.get("job_location") or role["loc"] or ""
    apply_url = spec.get("apply_url_apply") or spec.get("apply_url") or role["url"]
    jd_text = spec.get("jd_text") or ""
    if spec.get("maintenance_mode"):
        jd_body = (
            "_(Workday CXS detail endpoint redirected to the maintenance page "
            "at fetch time; JD body unavailable. Re-run when service is restored.)_"
        )
    elif spec.get("fetch_error"):
        jd_body = f"_(JD fetch failed: {spec['fetch_error']})_"
    else:
        jd_body = jd_text
    (workdir / "JD.md").write_text(
        f"# {title}\n\n**Company:** {role['company']}\n**Location:** {loc}\n"
        f"**Apply:** {apply_url}\n**Workday tenant:** {role['wd_tenant']}\n"
        f"**Req ID:** {role['wd_reqid']}\n"
        f"**Posted on:** {spec.get('posted_on','')}\n"
        f"**Submit mode:** MANUAL (Workday auto-submit not implemented)\n\n---\n\n"
        f"{jd_body}\n"
    )
    meta = {
        "company": role["company"], "role": title, "location": loc,
        "exp_required": role["exp_req"], "apply_url": apply_url,
        "jd_url": role["url"],
        "fetched_at": spec.get("fetched_at") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ats": "workday",
        "wd_host": role["wd_host"], "wd_tenant": role["wd_tenant"],
        "wd_site": role["wd_site"], "wd_job_path": role["wd_job_path"],
        "wd_reqid": role["wd_reqid"],
        # Compat aliases — same convention as other ATSes for downstream tools.
        "gh_org": f"workday-{role['wd_tenant']}",
        "gh_jid": role["wd_reqid"],
        "flags": role["flags"] or "",
        "submit_mode": "manual",
        "maintenance_mode": bool(spec.get("maintenance_mode")),
        "posted_on": spec.get("posted_on", ""),
    }
    (workdir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    personal = json.loads(PERSONAL_INFO.read_text())
    (workdir / "prefill.json").write_text(json.dumps(personal, indent=2) + "\n")
    return apply_url


def run_workday_dryrun(role_url: str, tenant: str, reqid: str) -> Path:
    """Generate the Workday dryrun spec. Returns path to JSON."""
    spec_path = DRYRUN_DIR / f"workday-{tenant}-{reqid}.json"
    res = subprocess.run(
        [str(VENV_PY), str(HERE / "workday_dryrun.py"), role_url, "--quiet"],
        capture_output=True, text=True, timeout=60,
    )
    if res.returncode != 0:
        raise RuntimeError(f"workday_dryrun.py failed (rc={res.returncode}): {res.stderr[:500]}")
    if not spec_path.exists():
        raise RuntimeError(f"workday dryrun spec not written: expected {spec_path}")
    return spec_path


def prep_role_workday(role: dict, dry_run: bool = False) -> dict:
    """Workday prep-only pipeline. No browser plan emitted; STATUS.md flags
    PREP-READY-MANUAL (or MAINTENANCE_RETRY if Workday is down)."""
    slug = role["slug"]
    workdir = SUBMITTED_DIR / slug
    workdir.mkdir(parents=True, exist_ok=True)
    result = {
        "slug": slug, "role_id": role["role_id"], "company": role["company"],
        "role": role["role"], "ok": False, "phase_failed": None,
        "workdir": str(workdir),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ats": "workday", "submit_mode": "manual",
    }

    def abort(phase: str, err: str) -> dict:
        result["phase_failed"] = phase
        result["error"] = err[:2000]
        result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (workdir / "STATUS.md").write_text(
            f"ABORT-{phase.upper()} — {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
            f"role_id: {role['role_id']}\nphase: {phase}\nerror:\n{err[:2000]}\n"
        )
        return result

    # 1. Dryrun spec (also handles JD fetch + maintenance detection)
    try:
        spec_path = run_workday_dryrun(role["url"], role["wd_tenant"], role["wd_reqid"])
        spec = json.loads(spec_path.read_text())
    except Exception as e:
        return abort("workday-dryrun", f"{type(e).__name__}: {e}")

    # 2. Write JD.md / meta.json / prefill.json
    try:
        apply_url = write_jd_files_workday(workdir, role, spec)
    except Exception as e:
        return abort("jd-files", f"{type(e).__name__}: {e}")

    # 3. If maintenance mode (or JD body empty), bail with MAINTENANCE_RETRY.
    #    Skip tailoring — bullet_rewriter has nothing to work from, and we
    #    don't want to burn LLM credits on a placeholder JD.
    jd_text = spec.get("jd_text") or ""

    # 3a. JD-level overreach guard (catches "managing a team of PMs" etc.
    #     that title alone misses; also picks up YOE phrases the discovery
    #     adapter didn't see). 2026-05-17 after the Adobe Group PM incident.
    if jd_text and len(jd_text) >= 200:
        from core import is_overreach as _is_overreach, parse_experience as _parse_exp
        # Recompute exp_req from the JD text now that we have it.
        parsed_exp = _parse_exp(jd_text)
        ovr, reason = _is_overreach(parsed_exp, jd_text, role.get("role"))
        if ovr:
            _log_skipped_overreach(role, reason, phase="workday-jd-check")
            result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            result["phase_failed"] = "overreach"
            (workdir / "STATUS.md").write_text(
                f"ABORT-OVERREACH — {result['ended_at']}\n\n"
                f"role_id: {role['role_id']}\nreason: {reason}\n"
                f"parsed_exp: {parsed_exp}\noriginal_exp: {role.get('exp_req')}\n\n"
                "Role requires senior-IC YOE or people-management experience.\n"
                "Auto-submit refused per Cyrus 2026-05-17 guard.\n"
            )
            return result

    if spec.get("maintenance_mode") or not jd_text.strip() or len(jd_text) < 200:
        result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        result["phase_failed"] = "maintenance-retry"
        result["maintenance_mode"] = bool(spec.get("maintenance_mode"))
        result["apply_url"] = apply_url
        reason = "workday in maintenance mode" if spec.get("maintenance_mode") else \
                 (spec.get("fetch_error") or f"JD body too short ({len(jd_text)} chars)")
        (workdir / "STATUS.md").write_text(
            f"MAINTENANCE_RETRY — {result['ended_at']}\n\n"
            f"role_id: {role['role_id']}\n"
            f"ats: workday\n"
            f"apply_url: {apply_url}\n"
            f"reason: {reason}\n"
            f"http_status: {spec.get('http_status')}\n"
            f"final_url: {spec.get('final_url')}\n\n"
            "Workday CXS detail endpoint is unreachable. Cron will retry on the\n"
            "next scheduled run. No tailored resume / cover answers were\n"
            "generated (nothing to tailor against without a JD body).\n\n"
            "Do NOT mark applied_on / prep_status='manual_ready' — this packet\n"
            "is incomplete.\n"
        )
        # Do NOT flip prep_status; we want this picked up again next run.
        return result

    # 4. Bullet rewriter
    try:
        br_org = f"workday-{role['wd_tenant']}"
        br_jid = role["wd_reqid"]
        pdf = run_bullet_rewriter(slug, workdir, br_org, br_jid)
        result["pdf"] = str(pdf)
    except Exception as e:
        return abort("bullet-rewriter", f"{type(e).__name__}: {e}")

    # 5. Cover answers (JD-derived essay prep — useful for manual hand-fill too)
    try:
        cover = run_cover_answers(slug)
        result["cover_answers"] = str(cover)
    except Exception as e:
        # Non-fatal for workday: hand-fill doesn't strictly need cover_answers.md,
        # but flag it.
        result["cover_answers"] = None
        result["cover_answers_error"] = f"{type(e).__name__}: {e}"

    # 6. STATUS.md + tracker prep_status flip
    result["ok"] = True
    result["apply_url"] = apply_url
    result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (workdir / "STATUS.md").write_text(
        f"STATUS: PREP-READY-MANUAL\n"
        f"Generated: {result['ended_at']}\n\n"
        f"role_id: {role['role_id']}\n"
        f"ats: workday (tenant: {role['wd_tenant']})\n"
        f"company: {role['company']}\n"
        f"role: {role['role']}\n\n"
        f"=====================================================================\n"
        f"APPLY HERE (MANUAL):\n\n"
        f"    {apply_url}\n\n"
        f"=====================================================================\n\n"
        f"Packet contents:\n"
        f"  - JD.md                 ({len(jd_text)} chars of JD body)\n"
        f"  - {Path(result['pdf']).name}  (tailored resume PDF — upload this)\n"
        f"  - cover_answers.md      " +
        ("(answers for open-text/essay questions — copy-paste as needed)\n"
         if result.get("cover_answers") else f"(NOT GENERATED — {result.get('cover_answers_error','unknown error')})\n") +
        f"  - meta.json, prefill.json\n\n"
        f"Workday auto-submit is not implemented (per-tenant variability + MFA +\n"
        f"account creation makes it not worth building for the current role count).\n"
        f"Open the apply URL above, create/sign into the Workday account, paste\n"
        f"answers from cover_answers.md, attach the tailored PDF, submit.\n\n"
        f"Once submitted, set tracker.db: UPDATE roles SET applied_by='manual',\n"
        f"applied_on='YYYY-MM-DD', prep_status='submitted' WHERE id={role['role_id']};\n"
        f"then re-run render_xlsx.py.\n"
    )
    # Flip tracker prep_status so the role doesn't get re-prepped.
    if not dry_run:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE roles SET prep_status='manual_ready', prep_path=? WHERE id=?",
                (str(workdir), role["role_id"]),
            )
            conn.commit()
            conn.close()
            result["tracker_updated"] = True
        except Exception as e:
            result["tracker_update_error"] = f"{type(e).__name__}: {e}"
    return result


# ---------------------------------------------------------------------------
# Rippling prep pipeline (chain rippling-adapter-2026-05-30).
# ---------------------------------------------------------------------------
# Rippling jobs (ats.rippling.com/<slug>/jobs/<uuid>) submit via a direct
# JSON-API flow implemented in rippling_filler.py (uploads via S3 presigned
# POST + Cloudflare Turnstile solve + POST /api/v1/board/<slug>/jobs/<uuid>/apply).
# No browser plan is emitted. Prep produces:
#   - JD.md (from adapters/rippling._fetch_jd_text)
#   - meta.json + tailored resume PDF + cover_answers.md (standard tooling)
#   - STATUS-PREP-READY-RIPPLING-RUNNER pointing the caller at the runner CLI
# The cron/agent then runs:
#   .venv/bin/python role-discovery/rippling_filler.py \
#       --slug <rp_slug> --job-id <rp_jid> \
#       --resume <pdf> --answers <answers.json> [--cover-letter <pdf>] \
#       [--dry-run]   # MUST be passed for verification runs
# and overwrites STATUS.md with the SubmitArtifacts outcome.

def _fetch_rippling_jd(rp_slug: str, rp_jid: str) -> tuple[str, str]:
    """Return (title, jd_text). Delegates to adapters.rippling._fetch_jd_text.
    Raises on failure.
    """
    sys.path.insert(0, str(HERE / "adapters"))
    from rippling import _fetch_jd_text  # type: ignore  # noqa: WPS433
    title, jd_text = _fetch_jd_text(rp_slug, rp_jid)
    return title, jd_text


def write_jd_files_rippling(workdir: Path, role: dict, title: str, jd_text: str) -> str:
    """Write JD.md + meta.json for a Rippling role. Returns the apply URL."""
    apply_url = role.get("url") or f"https://ats.rippling.com/{role['rp_slug']}/jobs/{role['rp_jid']}"
    jd_md = (
        f"# {role['company']} \u2014 {title or role['role']}\n\n"
        f"**Location:** {role.get('loc') or 'n/a'}\n"
        f"**Apply:** {apply_url}\n"
        f"**Rippling board:** {role['rp_slug']}\n"
        f"**Job ID:** {role['rp_jid']}\n\n"
        "---\n\n"
        + (jd_text or "")
    )
    (workdir / "JD.md").write_text(jd_md)
    meta = {
        "company": role["company"],
        "role": title or role["role"],
        "location": role.get("loc"),
        "exp_required": role.get("exp_req"),
        "apply_url": apply_url,
        "jd_url": apply_url,
        "ats": "rippling",
        "rp_slug": role["rp_slug"],
        "rp_jid": role["rp_jid"],
        # Compat aliases (bullet_rewriter --org/--job-id).
        "gh_org": f"rippling-{role['rp_slug']}",
        "gh_jid": role["rp_jid"][:8],
        "flags": role.get("flags", ""),
    }
    (workdir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    return apply_url


def prep_role_rippling(role: dict, dry_run: bool = False) -> dict:
    """Rippling prep pipeline. No browser plan; STATUS flags PREP-READY-RIPPLING-RUNNER.

    Steps: JD fetch → write JD.md/meta.json → overreach guard → bullet_rewriter
    → cover_answers → STATUS.md. The runner (rippling_filler.py) is invoked
    by the calling agent/cron — we never call it from here so this function
    is safe in dry_run + tests.
    """
    slug = role["slug"]
    workdir = SUBMITTED_DIR / slug
    workdir.mkdir(parents=True, exist_ok=True)
    result = {
        "slug": slug, "role_id": role["role_id"], "company": role["company"],
        "role": role["role"], "ok": False, "phase_failed": None,
        "workdir": str(workdir),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ats": "rippling", "submit_mode": "runner",
    }

    def abort(phase: str, err: str) -> dict:
        result["phase_failed"] = phase
        result["error"] = err[:2000]
        result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (workdir / "STATUS.md").write_text(
            f"ABORT-{phase.upper()} \u2014 {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
            f"role_id: {role['role_id']}\nphase: {phase}\nerror:\n{err[:2000]}\n"
        )
        return result

    # 1. JD fetch (Next.js SSR scrape via adapters.rippling).
    try:
        title, jd_text = _fetch_rippling_jd(role["rp_slug"], role["rp_jid"])
    except Exception as e:
        return abort("jd-fetch", f"{type(e).__name__}: {e}")

    # 2. Write JD files.
    try:
        apply_url = write_jd_files_rippling(workdir, role, title, jd_text)
    except Exception as e:
        return abort("jd-files", f"{type(e).__name__}: {e}")

    # 3. JD-level overreach guard (same as Workday path).
    if jd_text and len(jd_text) >= 200:
        from core import is_overreach as _is_overreach, parse_experience as _parse_exp
        parsed_exp = _parse_exp(jd_text)
        ovr, reason = _is_overreach(parsed_exp, jd_text, role.get("role"))
        if ovr:
            _log_skipped_overreach(role, reason, phase="rippling-jd-check")
            result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            result["phase_failed"] = "overreach"
            (workdir / "STATUS.md").write_text(
                f"ABORT-OVERREACH \u2014 {result['ended_at']}\n\n"
                f"role_id: {role['role_id']}\nreason: {reason}\n"
                f"parsed_exp: {parsed_exp}\noriginal_exp: {role.get('exp_req')}\n\n"
                "Role requires senior-IC YOE or people-management experience.\n"
                "Auto-submit refused per Cyrus 2026-05-17 guard.\n"
            )
            return result

    if not jd_text.strip() or len(jd_text) < 200:
        return abort("jd-too-short",
                     f"JD body too short ({len(jd_text)} chars) \u2014 likely Cloudflare block or empty posting")

    # 4. Bullet rewriter (tailored resume PDF).
    try:
        br_org = f"rippling-{role['rp_slug']}"
        br_jid = role["rp_jid"][:8]
        pdf = run_bullet_rewriter(slug, workdir, br_org, br_jid)
        result["pdf"] = str(pdf)
    except Exception as e:
        return abort("bullet-rewriter", f"{type(e).__name__}: {e}")

    # 5. Cover answers (non-fatal).
    try:
        cover = run_cover_answers(slug)
        result["cover_answers"] = str(cover)
    except Exception as e:
        result["cover_answers"] = None
        result["cover_answers_error"] = f"{type(e).__name__}: {e}"

    # 6. STATUS.md.
    result["ok"] = True
    result["apply_url"] = apply_url
    result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    runner_cmd = (
        f".venv/bin/python role-discovery/rippling_filler.py \\\n"
        f"        --slug {role['rp_slug']} --job-id {role['rp_jid']} \\\n"
        f"        --resume {result['pdf']} \\\n"
        f"        --answers <answers.json> \\\n"
        f"        --out {workdir / 'submit_artifacts.json'} \\\n"
        f"        --dry-run   # remove for real submit"
    )
    (workdir / "STATUS.md").write_text(
        f"PREP-READY-RIPPLING-RUNNER \u2014 {result['ended_at']}\n\n"
        f"role_id: {role['role_id']}\n"
        f"ats:     rippling (board: {role['rp_slug']})\n"
        f"company: {role['company']}\n"
        f"role:    {role['role']}\n"
        f"slug:    {slug}\n"
        f"pdf:     {result['pdf']}\n"
        f"cover:   {result.get('cover_answers') or 'NOT GENERATED'}\n"
        f"apply:   {apply_url}\n\n"
        "Calling agent / cron: do NOT execute via the generic browser tool.\n"
        "Rippling submits via a direct-API flow (S3 presigned upload + Cloudflare\n"
        "Turnstile solve + POST /apply). Invoke the runner CLI:\n\n"
        f"    {runner_cmd}\n\n"
        "<answers.json> must contain the standard 9-field basicQuestions schema\n"
        "(first_name, last_name, email, current_company, location, linkedin_link,\n"
        "phone_number, plus optional cover-letter freeform). See\n"
        "rippling_filler.py header + applications/_rippling-smoke-2026-05-30.json\n"
        "for the verified shape.\n\n"
        "On success overwrite this STATUS.md with the SubmitArtifacts outcome\n"
        "and stamp tracker.db (applied_by='rippling-runner', applied_on=<date>,\n"
        "prep_status='submitted').\n"
    )
    # Flip tracker prep_status so the role isn't re-prepped.
    if not dry_run:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "UPDATE roles SET prep_status='runner_ready', prep_path=? WHERE id=?",
                (str(workdir), role["role_id"]),
            )
            conn.commit()
            conn.close()
            result["tracker_updated"] = True
        except Exception as e:
            result["tracker_update_error"] = f"{type(e).__name__}: {e}"
    return result


# ---------------------------------------------------------------------------
# Meta Careers (metacareers.com) prep+submit pipeline
# ---------------------------------------------------------------------------

def _extract_meta_jd(job_id: str) -> tuple[str, str]:
    """Fetch Meta JD title + body via HTTP (no browser needed for JD read)."""
    import requests
    url = f"https://www.metacareers.com/profile/job_details/{job_id}/"
    r = requests.get(url, timeout=15,
                     headers={"User-Agent": "Mozilla/5.0 Chrome/125"},
                     allow_redirects=True)
    if "position-not-available" in r.url or r.status_code >= 400:
        raise RuntimeError(f"Meta JD fetch failed: {r.status_code} {r.url}")
    import re as _re
    m = _re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', r.text)
    title = m.group(1).replace(" | Meta Careers", "").strip() if m else ""
    # Extract plain text from the og:description or page body
    dm = _re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', r.text)
    desc = dm.group(1) if dm else ""
    return title, desc


def prep_role_icims(role: dict, dry_run: bool = False) -> dict:
    """iCIMS prep -> runner. The runner (_icims_runner.py) drives the full
    JD -> Apply -> email/OTP -> form -> submit flow over CDP and uploads the
    standard resume itself, so prep is thin: create the packet folder, record
    tenant/reqId, and write STATUS-PREP-READY-ICIMS-RUNNER with the exact CLI.
    The role is flipped prep_status='manual_ready' so it is not re-prepped.

    NOTE: some iCIMS tenants gate the email-entry step behind hCaptcha BEFORE
    the OTP (block_reason icims-hcaptcha-no-vendor). On those the runner exits
    2 until a captcha vendor is provisioned; the OTP handling (EXIT 10 on miss)
    runs the moment human-verification is passed.
    """
    slug = role["slug"]
    workdir = SUBMITTED_DIR / slug
    workdir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result = {
        "slug": slug, "role_id": role["role_id"], "company": role["company"],
        "role": role["role"], "ok": False, "workdir": str(workdir),
        "ats": "icims", "submit_mode": "runner", "started_at": now,
    }
    try:
        import json as _json
        icims_doc = {
            "role_id": role["role_id"], "company": role["company"],
            "role": role["role"], "ats": "icims", "url": role["url"],
            "icims_host": role.get("icims_host", ""),
            "icims_reqid": role.get("icims_reqid", ""),
            "loc": role.get("loc", ""), "exp_req": role.get("exp_req", ""),
            "slug": slug,
        }
        (workdir / "icims.json").write_text(_json.dumps(icims_doc, indent=2) + NL_CONST)
        runner_cmd = (
            f"    .venv/bin/python role-discovery/_icims_runner.py "
            f"--url {role['url']} --apply --debug .icims-debug/{slug}"
        )
        (workdir / "STATUS.md").write_text(
            f"PREP-READY-ICIMS-RUNNER \u2014 {now}" + NL_CONST + NL_CONST
            + f"role_id: {role['role_id']}" + NL_CONST
            + f"slug:    {slug}" + NL_CONST
            + f"url:     {role['url']}" + NL_CONST
            + f"tenant:  {role.get('icims_host', '')}  reqId: {role.get('icims_reqid', '')}" + NL_CONST + NL_CONST
            + "iCIMS apply is driven by the CDP runner (handles email-OTP via" + NL_CONST
            + "Gmail IMAP, EXIT 10 on OTP timeout). Run:" + NL_CONST + NL_CONST
            + runner_cmd + NL_CONST + NL_CONST
            + "EXIT: 0=submitted/dryrun 2=auth/hcaptcha-wall 3=no-confirm" + NL_CONST
            + "4=no-submit 5=cap 6=closed 7=already-applied 10=otp-timeout" + NL_CONST
        )
        result["ok"] = True
        result["status_file"] = str(workdir / "STATUS.md")
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        (workdir / "STATUS.md").write_text(f"ABORT-ICIMS-PREP \u2014 {now}" + NL_CONST + result["error"] + NL_CONST)
        return result
    # Flip prep_status so it is not re-prepped (mirrors Workday manual_ready).
    if not dry_run:
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.execute(
                "UPDATE roles SET prep_status='manual_ready' WHERE id=?",
                (role["role_id"],),
            )
            conn.commit(); conn.close()
            result["tracker_updated"] = True
        except Exception as e:
            result["tracker_update_error"] = f"{type(e).__name__}: {e}"
    result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return result


def prep_role_meta(role: dict, dry_run: bool = False) -> dict:
    """Meta Careers prep+submit pipeline.

    Unlike Rippling/Workday, Meta's form is short enough to drive directly.
    Steps: HTTP JD fetch -> write JD.md/meta.json -> overreach guard ->
    bullet_rewriter -> meta_submit (or flag PREP-READY-META-RUNNER for manual).
    """
    slug = role["slug"]
    workdir = SUBMITTED_DIR / slug
    workdir.mkdir(parents=True, exist_ok=True)
    result = {
        "slug": slug, "role_id": role["role_id"], "company": role["company"],
        "role": role["role"], "ok": False, "phase_failed": None,
        "workdir": str(workdir),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ats": "meta", "submit_mode": "runner",
    }

    def abort(phase: str, err: str) -> dict:
        result["phase_failed"] = phase
        result["error"] = err[:2000]
        result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (workdir / "STATUS.md").write_text(
            f"ABORT-{phase.upper()} \u2014 {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
            f"role_id: {role['role_id']}\nphase: {phase}\nerror:\n{err[:2000]}\n"
        )
        return result

    # Extract job_id from URL
    import re as _re
    job_id_m = _re.search(r"/(\d{10,})", role.get("url", ""))
    if not job_id_m:
        return abort("job-id", f"Cannot extract job_id from URL: {role.get('url')}")
    job_id = job_id_m.group(1)

    # 1. JD fetch
    try:
        title, jd_text = _extract_meta_jd(job_id)
    except Exception as e:
        return abort("jd-fetch", f"{type(e).__name__}: {e}")

    # 2. Write JD files
    try:
        import json as _json
        (workdir / "JD.md").write_text(f"# {title}\n\n{jd_text}\n")
        meta_doc = {
            "role_id": role["role_id"], "company": "Meta",
            "role": title or role["role"], "ats": "meta",
            "url": role["url"], "job_id": job_id,
            "loc": role.get("loc", ""), "exp_req": role.get("exp_req", ""),
            "slug": slug,
        }
        (workdir / "meta.json").write_text(_json.dumps(meta_doc, indent=2) + "\n")
    except Exception as e:
        return abort("jd-files", f"{type(e).__name__}: {e}")

    # 3. Overreach guard
    if jd_text and len(jd_text) >= 100:
        from core import is_overreach as _is_overreach, parse_experience as _parse_exp
        parsed_exp = _parse_exp(jd_text)
        ovr, reason = _is_overreach(parsed_exp, jd_text, role.get("role"))
        if ovr:
            _log_skipped_overreach(role, reason, phase="meta-jd-check")
            result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            result["phase_failed"] = "overreach"
            (workdir / "STATUS.md").write_text(
                f"ABORT-OVERREACH \u2014 {result['ended_at']}\n\nrole_id: {role['role_id']}\nreason: {reason}\n"
            )
            return result

    # 4. Bullet rewriter
    try:
        br_org = f"meta-{job_id[:8]}"
        br_jid = job_id[:8]
        pdf = run_bullet_rewriter(slug, workdir, br_org, br_jid)
        result["pdf"] = str(pdf)
    except Exception as e:
        return abort("bullet-rewriter", f"{type(e).__name__}: {e}")

    # 5. Cover answers (non-fatal)
    try:
        cover = run_cover_answers(slug)
        result["cover_answers"] = str(cover)
    except Exception as e:
        result["cover_answers"] = None
        result["cover_answers_error"] = f"{type(e).__name__}: {e}"

    apply_url = f"https://www.metacareers.com/profile/create_application/{job_id}/"
    result["apply_url"] = apply_url
    result["job_id"] = job_id

    # 6. Submit (or flag for manual if dry_run)
    if dry_run:
        result["ok"] = True
        result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (workdir / "STATUS.md").write_text(
            f"PREP-READY-META-RUNNER \u2014 {result['ended_at']}\n\n"
            f"role_id: {role['role_id']}\nslug: {slug}\npdf: {result['pdf']}\n"
            f"apply: {apply_url}\n\n"
            f"    .venv/bin/python role-discovery/_meta_runner.py {apply_url} "
            f"--role-id {role['role_id']} --resume {result['pdf']}\n"
        )
        return result

    # Live submit
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path(__file__).parent))
        from _meta_runner import meta_submit as _meta_submit, _load_personal as _meta_personal
        personal = _meta_personal()
        plan = {"job_id": job_id, "apply_url": apply_url, "location_pref": ""}
        exit_code = _meta_submit(role["role_id"], plan, result["pdf"], personal)
    except Exception as e:
        return abort("meta-submit", f"{type(e).__name__}: {e}")

    if exit_code == 0:
        result["ok"] = True
        result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (workdir / "STATUS.md").write_text(
            f"SUBMITTED \u2014 {result['ended_at']}\n\n"
            f"role_id: {role['role_id']}\nslug: {slug}\n"
            f"submitted_by: _meta_runner\napply_url: {apply_url}\n"
            f"resume: {result['pdf']}\n"
        )
        # Stamp tracker
        try:
            import sqlite3 as _sq3
            from datetime import date as _date
            conn = _sq3.connect(DB_PATH)
            conn.execute(
                "UPDATE roles SET applied_by='meta-runner', applied_on=?, prep_status='submitted' WHERE id=?",
                (_date.today().isoformat(), role["role_id"]),
            )
            conn.commit(); conn.close()
            result["tracker_updated"] = True
        except Exception as e:
            result["tracker_update_error"] = f"{type(e).__name__}: {e}"
        # Re-render xlsx
        try:
            import subprocess as _sub
            _sub.run(
                [str(Path(__file__).parent / ".venv/bin/python"),
                 str(Path(__file__).parent / "render_xlsx.py")],
                capture_output=True, timeout=60,
            )
        except Exception:
            pass
    elif exit_code == 6:
        return abort("meta-closed", "role closed at apply time")
    elif exit_code == 7:
        return abort("meta-already-applied", "already applied to this role")
    elif exit_code == 2:
        return abort("meta-auth", "auth gate encountered (unexpected on guest apply)")
    else:
        return abort("meta-submit", f"runner EXIT {exit_code}")

    return result


# ---------------------------------------------------------------------------
# chain_005 P5 (2026-05-26): URL liveness HEAD probe
# ---------------------------------------------------------------------------
# Avoid burning a full prep cycle on a dead URL (lost Cursor 933 cycle this
# way on 2026-05-26). Probe the JD URL with HEAD before any other prep work.
# - status >= 400 and != 999: treat as dead. (LinkedIn anti-bot returns 999;
#   fall through to normal flow — LinkedIn pages still resolve via the
#   linkedin_resolver_pipeline upstream.)
# - status 200 with body containing "page not found" / "no longer available"
#   / "this position has been filled" etc.: dead. (Some ATSes return a
#   200 with an HTML 404 page — GET a small slice to detect.)
# - everything else: live.
# When dead and we have a real role_id (>0), stamp the tracker with
# status='closed' + agent_notes='url-dead-head-probe <date>' so the slug is
# excluded from the next batch pick.

DEAD_BODY_MARKERS = (
    "page not found",
    "no longer available",
    "this position has been filled",
    "this position is no longer accepting",
    "posting is no longer active",
    "this job is no longer available",
    "position has been closed",
)


def probe_url_liveness(url: str, timeout: float = 10.0) -> dict:
    """HEAD-probe the URL, then small GET on ambiguous results. Returns
    {alive: bool, status: int|None, reason: str, body_marker: str|None}.

    Never raises (returns alive=True on network error — prefer false-negative
    over killing a viable role on a flaky probe).
    """
    if not url:
        return {"alive": True, "status": None, "reason": "no-url-skip", "body_marker": None}
    headers = {"User-Agent": "job-search-agent/1.0 (HEAD-probe)"}
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout, headers=headers)
        status = r.status_code
    except Exception as e:
        return {"alive": True, "status": None, "reason": f"probe-error-{type(e).__name__}", "body_marker": None}

    # LinkedIn anti-bot returns 999 — do NOT treat as dead.
    if status == 999:
        return {"alive": True, "status": status, "reason": "linkedin-999", "body_marker": None}
    if status >= 400:
        return {"alive": False, "status": status, "reason": f"http-{status}", "body_marker": None}
    # 2xx/3xx — some ATSes return 200 with a soft-404 HTML page. Sniff body.
    try:
        r2 = requests.get(url, allow_redirects=True, timeout=timeout, headers=headers, stream=True)
        # Read at most 64KB — enough to catch typical 404 banners.
        chunk = r2.raw.read(65536, decode_content=True) if hasattr(r2.raw, "read") else r2.content[:65536]
        try:
            r2.close()
        except Exception:
            pass
        body_lc = (chunk.decode("utf-8", errors="ignore") if isinstance(chunk, (bytes, bytearray)) else str(chunk)).lower()
        for marker in DEAD_BODY_MARKERS:
            if marker in body_lc:
                return {"alive": False, "status": status, "reason": "soft-404-body", "body_marker": marker}
    except Exception:
        # If the GET fails we already saw HEAD 2xx — call it alive.
        pass
    return {"alive": True, "status": status, "reason": "ok", "body_marker": None}


def _mark_role_closed_url_dead(role: dict, probe: dict) -> None:
    """Stamp the tracker with status='closed' + agent_notes when role_id>0."""
    rid = role.get("role_id") or 0
    if not rid:
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    tag = (
        f"url-dead-head-probe {today}: status={probe.get('status')} "
        f"reason={probe.get('reason')}"
    )
    if probe.get("body_marker"):
        tag += f" marker={probe['body_marker']!r}"
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        prev = cur.execute("SELECT agent_notes FROM roles WHERE id=?", (rid,)).fetchone()
        prev_n = (prev[0] if prev and prev[0] else "").strip()
        new_n = (prev_n + (" | " if prev_n else "") + tag).strip()
        cur.execute("UPDATE roles SET status='closed', agent_notes=? WHERE id=?", (new_n, rid))
        conn.commit()
        conn.close()
    except Exception as e:  # pragma: no cover
        print(f"[inline_submit] WARN: failed to mark role {rid} closed: {e}", file=sys.stderr)


def prep_role(role: dict, dry_run: bool = False, ignore_csp_block: bool = False,
              skip_head_probe: bool = False, ignore_blockers: bool = False) -> dict:
    """Run all prep phases for one role. Returns a result dict.
    Writes ABORT STATUS.md on failure but does not raise."""
    # Workday is prep-only — dispatch to a separate code path.
    if role.get("ats") == "workday":
        return prep_role_workday(role, dry_run=dry_run)

    # Rippling — direct-API submitter (rippling_filler.py). Prep produces a
    # tailored PDF + cover_answers + STATUS-PREP-READY-RIPPLING-RUNNER
    # pointing the caller at the runner CLI.
    if role.get("ats") == "rippling":
        return prep_role_rippling(role, dry_run=dry_run)

    # Meta Careers — full prep+submit via _meta_runner.py (guest apply, no auth).
    if role.get("ats") == "meta":
        return prep_role_meta(role, dry_run=dry_run)

    # iCIMS — full prep+submit via _icims_runner.py (CDP; email-OTP handled).
    if role.get("ats") == "icims":
        return prep_role_icims(role, dry_run=dry_run)

    # chain_005 P5 (2026-05-26): HEAD-probe the URL before any other work.
    # Cursor 933 lost a full prep cycle to a page-not-found. Probe runs after
    # Workday short-circuit so Workday's own JD fetch + CXS detection isn't
    # disturbed (Workday JDs sometimes 403 to HEAD anyway).
    if not skip_head_probe:
        probe_url = role.get("url") or ""
        probe = probe_url_liveness(probe_url)
        if not probe["alive"]:
            slug = role["slug"]
            workdir = SUBMITTED_DIR / slug
            workdir.mkdir(parents=True, exist_ok=True)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            (workdir / "STATUS.md").write_text(
                f"CLOSED-URL-DEAD — {now}\n\n"
                f"role_id: {role.get('role_id')}\n"
                f"slug:    {slug}\n"
                f"url:     {probe_url}\n"
                f"probe:   status={probe.get('status')} reason={probe.get('reason')}"
                f"{' marker=' + repr(probe.get('body_marker')) if probe.get('body_marker') else ''}\n\n"
                "chain_005 P5 URL-liveness HEAD probe: posting is no longer\n"
                "reachable. Tracker stamped status='closed'. No prep work\n"
                "performed. Override with --no-head-probe.\n"
            )
            if not dry_run:
                _mark_role_closed_url_dead(role, probe)
            return {
                "slug": slug, "role_id": role.get("role_id"),
                "company": role["company"], "role": role["role"],
                "ok": True, "closed": True, "head_probe": probe,
                "workdir": str(workdir),
                "started_at": now, "ended_at": now, "phase_failed": None,
            }

    # CSP/reCAPTCHA-Enterprise blocklist short-circuit (2026-05-24).
    # If this Greenhouse tenant is known to ship reCAPTCHA Enterprise against a
    # CSP that doesn't whitelist www.recaptcha.net, the submit form POST will
    # 428 no matter how cleanly we fill it. Skip prep entirely and flag for
    # manual application. Override with --ignore-csp-block.
    if (
        not ignore_csp_block
        and role.get("ats") in ("greenhouse", "greenhouse_iframe")
        and (role.get("gh_org") or "").lower() in load_gh_csp_blocklist()
    ):
        slug = role["slug"]
        workdir = SUBMITTED_DIR / slug
        workdir.mkdir(parents=True, exist_ok=True)
        gh_org = role["gh_org"]
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (workdir / "STATUS.md").write_text(
            f"STATUS: PREP-READY-MANUAL-CSP-CAPTCHA\n"
            f"observed_at: {now}\n"
            f"role_id: {role['role_id']}\n"
            f"slug: {slug}\n"
            f"gh_org: {gh_org}\n"
            f"company: {role['company']}\n"
            f"role: {role['role']}\n"
            f"url: {role.get('url')}\n\n"
            "Tenant is on greenhouse_csp_blocklist.yaml: reCAPTCHA Enterprise\n"
            "calls www.recaptcha.net which the Greenhouse CSP blocks ->\n"
            "submit button stays permanent-disabled / POST /v1/post 428.\n\n"
            "Apply manually via the Apply URL. Override: pass --ignore-csp-block\n"
            "if you want to attempt prep+submit anyway (e.g. to re-confirm the\n"
            "block is still in place).\n"
        )
        result = {
            "slug": slug,
            "role_id": role["role_id"],
            "company": role["company"],
            "role": role["role"],
            "ok": True,
            "phase_failed": None,
            "csp_blocklist_skip": True,
            "workdir": str(workdir),
            "started_at": now,
            "ended_at": now,
        }
        if not dry_run and role.get("role_id"):
            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                prev_notes = cur.execute(
                    "SELECT agent_notes FROM roles WHERE id=?", (role["role_id"],)
                ).fetchone()
                prev = (prev_notes[0] if prev_notes and prev_notes[0] else "").strip()
                tag = f"CSP-CAPTCHA-BLOCK-BLOCKLIST 2026-05-24: tenant {gh_org}"
                if tag not in prev:
                    new_notes = (prev + (" | " if prev else "") + tag).strip()
                else:
                    new_notes = prev
                cur.execute(
                    "UPDATE roles SET prep_status='manual_ready', prep_path=?, agent_notes=? WHERE id=?",
                    (str(workdir), new_notes, role["role_id"]),
                )
                conn.commit()
                conn.close()
            except Exception as e:  # pragma: no cover
                print(f"[inline_submit] WARN: failed to mark tracker for {slug}: {e}", file=sys.stderr)
        return result

    slug = role["slug"]
    workdir = SUBMITTED_DIR / slug
    workdir.mkdir(parents=True, exist_ok=True)
    result = {
        "slug": slug, "role_id": role["role_id"], "company": role["company"],
        "role": role["role"], "ok": False, "phase_failed": None,
        "workdir": str(workdir), "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    def abort(phase: str, err: str) -> dict:
        result["phase_failed"] = phase
        result["error"] = err[:2000]
        result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        status_path = workdir / "STATUS.md"
        status_path.write_text(
            f"ABORT-{phase.upper()} — {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
            f"role_id: {role['role_id']}\nphase: {phase}\nerror:\n{err[:2000]}\n"
        )
        return result

    # 1. JD fetch
    try:
        ats = role.get("ats", "greenhouse")
        if ats == "lever":
            data = fetch_jd_lever(role["lv_org"], role["lv_jid"])
            write_jd_files_lever(workdir, role, data)
            absolute_url = data.get("hostedUrl") or role["url"]
        elif ats == "ashby":
            data = fetch_jd_ashby(role["ash_org"], role["ash_jid"])
            write_jd_files_ashby(workdir, role, data)
            absolute_url = data.get("jobUrl") or data.get("applyUrl") or role["url"]
        elif ats == "greenhouse_iframe":
            # Identical to greenhouse — same boards-api endpoint with the
            # mapped slug. Keep the wrapper URL in meta so the user can
            # always click back to the company’s branded page.
            data = fetch_jd(role["gh_org"], role["gh_jid"])
            write_jd_files(workdir, role, data)
            # Tag meta with iframe info for forensics.
            meta_path = workdir / "meta.json"
            meta = json.loads(meta_path.read_text())
            meta["ats"] = "greenhouse_iframe"
            meta["wrapper_url"] = role.get("wrapper_url") or role["url"]
            meta["embed_url"] = role.get("embed_url")
            meta_path.write_text(json.dumps(meta, indent=2) + "\n")
            # For dryrun + downstream plumbing we need a synthetic GH URL
            # because greenhouse_dryrun.parse_greenhouse_url() only accepts
            # greenhouse.io hosts.
            absolute_url = _gh_iframe_synth_url(role["gh_org"], role["gh_jid"])
        else:
            data = fetch_jd(role["gh_org"], role["gh_jid"])
            write_jd_files(workdir, role, data)
            # 2026-06-02 linkedin-recovery fix: boards-api absolute_url often
            # points at the COMPANY careers site (e.g. stripe.com, veriff.com,
            # samsara.com) which greenhouse_dryrun.parse_greenhouse_url rejects
            # as 'not a greenhouse URL'. Always feed the dryrun the canonical
            # boards.greenhouse.io form URL built from gh_org/gh_jid.
            absolute_url = _gh_iframe_synth_url(role["gh_org"], role["gh_jid"])
    except Exception as e:
        return abort("jd-fetch", f"{type(e).__name__}: {e}")

    # 2. Dryrun spec
    try:
        if ats == "lever":
            spec_path = run_dryrun_lever(absolute_url, role["lv_org"], role["lv_jid"])
        elif ats == "ashby":
            spec_path = run_dryrun(absolute_url, role["ash_org"], role["ash_jid"], ats="ashby")
        else:
            # Both 'greenhouse' and 'greenhouse_iframe' use the same dryrun.
            spec_path = run_dryrun(absolute_url, role["gh_org"], role["gh_jid"])
        spec = json.loads(spec_path.read_text())
        if not spec.get("ready_to_submit") and spec.get("blockers") and not ignore_blockers:
            return abort("dryrun-blockers",
                         f"dryrun has blockers: {json.dumps(spec.get('blockers'))[:500]}")
        result["dryrun_counts"] = spec.get("counts")
    except Exception as e:
        return abort("dryrun", f"{type(e).__name__}: {e}")

    # 3. Bullet rewriter (resume tailoring)
    try:
        if ats == "lever":
            # Pass lever-specific org/jid identifiers; bullet_rewriter only uses
            # them to name the packet folder + PDF (org="lever-<lvorg>", jid=lvjid[:8]).
            br_org = f"lever-{role['lv_org']}"
            br_jid = role["lv_jid"][:8]
        elif ats == "ashby":
            # Same naming convention for Ashby — prefix the org so it doesn't
            # collide with a Greenhouse org of the same name; trim the UUID.
            br_org = f"ashby-{role['ash_org']}"
            br_jid = role["ash_jid"][:8]
        else:
            br_org = role["gh_org"]; br_jid = role["gh_jid"]
        pdf = run_bullet_rewriter(slug, workdir, br_org, br_jid)
        result["pdf"] = str(pdf)
    except Exception as e:
        return abort("bullet-rewriter", f"{type(e).__name__}: {e}")

    # 4. Cover answers
    try:
        cover = run_cover_answers(slug)
        result["cover_answers"] = str(cover)
    except Exception as e:
        return abort("cover-answers", f"{type(e).__name__}: {e}")

    # 5. Browser plan
    try:
        if ats == "lever":
            plan_path = emit_browser_plan_lever(slug, spec_path, pdf, workdir)
        else:
            # greenhouse + greenhouse_iframe share the emitter; for iframe
            # we override the navigate URL to the direct /embed/job_app URL.
            override_url = role.get("embed_url") if ats == "greenhouse_iframe" else None
            plan_path = emit_browser_plan(slug, spec_path, pdf, workdir,
                                          override_url=override_url,
                                          wrapper_url=role.get("wrapper_url"),
                                          ats_label=ats)
        result["plan_path"] = str(plan_path)
    except Exception as e:
        return abort("emit-plan", f"{type(e).__name__}: {e}")

    result["ok"] = True
    result["ended_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if not dry_run:
        # mark prep-ready (calling agent will overwrite when submit completes)
        #
        # greenhouse_iframe special case (2026-05-24, captcha-gate workaround):
        # Canonical /embed/job_app URLs are now gated by reCAPTCHA Enterprise.
        # The validated workaround is to drive the form via
        # `greenhouse_iframe_runner.py --slug <slug>`, which loads the
        # company's careers-page wrapper URL and replays the filler steps
        # inside the wrapped iframe Frame. When we have a wrapper_url we emit
        # a distinct STATUS marker so the calling cron/agent invokes the
        # runner directly instead of executing the generic browser-tool plan.
        wrapper = role.get("wrapper_url")
        if ats == "greenhouse_iframe" and wrapper:
            (workdir / "STATUS.md").write_text(
                f"PREP-READY-IFRAME-RUNNER — {result['ended_at']}\n\n"
                f"role_id: {role['role_id']}\n"
                f"slug:    {slug}\n"
                f"plan:    {result['plan_path']}\n"
                f"pdf:     {result['pdf']}\n"
                f"cover:   {result['cover_answers']}\n"
                f"wrapper: {wrapper}\n\n"
                "Calling agent / cron: do NOT execute the browser plan with the\n"
                "generic browser tool — the canonical /embed/job_app URL is\n"
                "reCAPTCHA-Enterprise gated. Instead run:\n\n"
                f"    .venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug {slug}\n\n"
                "and overwrite this STATUS.md with the runner's outcome block\n"
                "(see INLINE-SUBMIT-PLAYBOOK.md § greenhouse_iframe runner).\n"
            )
        else:
            (workdir / "STATUS.md").write_text(
                f"PREP-READY — {result['ended_at']}\n\n"
                f"role_id: {role['role_id']}\n"
                f"plan: {result['plan_path']}\n"
                f"pdf:  {result['pdf']}\n"
                f"cover: {result['cover_answers']}\n\n"
                "Calling agent: execute the browser plan, click Submit, observe confirmation,\n"
                "then overwrite this STATUS.md with the success block (see INLINE-SUBMIT-PLAYBOOK.md).\n"
            )
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--role-id", type=int)
    g.add_argument("--slug")
    g.add_argument("--batch", type=int)
    ap.add_argument("--dry-run", action="store_true",
                    help="Run prep but skip writing PREP-READY STATUS marker.")
    ap.add_argument("--ats", choices=["greenhouse", "ashby", "lever", "workday", "greenhouse_iframe", "rippling", "bamboohr", "meta"], default=None,
                    help="Filter --batch picks to a specific ATS (default: any).")
    ap.add_argument("--ignore-csp-block", action="store_true",
                    help="Run prep even if tenant is in greenhouse_csp_blocklist.yaml.")
    ap.add_argument("--no-head-probe", action="store_true",
                    help="chain_005 P5: skip the HEAD-probe URL-liveness check.")
    ap.add_argument("--ignore-blockers", action="store_true",
                    help="linkedin-recovery: still produce the plan when dryrun has custom-question blockers (answered later via _gh_submit.py --answers).")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    roles: list[dict] = []
    if args.role_id:
        roles = [resolve_role(args.role_id, conn)]
    elif args.batch:
        roles = pick_batch(args.batch, conn, ats_filter=args.ats)
        if not roles:
            ats_label = args.ats or "Greenhouse/Ashby"
            print(f"[inline_submit] no eligible open {ats_label} roles found", file=sys.stderr)
            return 1
    elif args.slug:
        # re-prep an existing slug by reading meta.json
        meta_p = SUBMITTED_DIR / args.slug / "meta.json"
        if not meta_p.exists():
            meta_p = QUEUED_DIR / args.slug / "meta.json"
        if not meta_p.exists():
            print(f"[inline_submit] meta.json not found for slug={args.slug}", file=sys.stderr)
            return 2
        meta = json.loads(meta_p.read_text())
        ats = meta.get("ats", "greenhouse")
        if ats == "lever":
            role_id = None
            for r in conn.execute("SELECT id FROM roles WHERE jd_url LIKE ? OR app_url LIKE ?",
                                  (f"%{meta['lv_jid']}%", f"%{meta['lv_jid']}%")):
                role_id = r["id"]; break
            roles = [{
                "role_id": role_id or 0, "company": meta["company"],
                "role": meta["role"], "loc": meta["location"],
                "exp_req": meta.get("exp_required"), "url": meta["apply_url"],
                "ats": "lever", "lv_org": meta["lv_org"], "lv_jid": meta["lv_jid"],
                "slug": args.slug, "flags": meta.get("flags", ""),
            }]
        elif ats == "workday":
            role_id = None
            for r in conn.execute("SELECT id FROM roles WHERE jd_url LIKE ? OR app_url LIKE ?",
                                  (f"%{meta['wd_reqid']}%", f"%{meta['wd_reqid']}%")):
                role_id = r["id"]; break
            roles = [{
                "role_id": role_id or 0, "company": meta["company"],
                "role": meta["role"], "loc": meta["location"],
                "exp_req": meta.get("exp_required"), "url": meta["jd_url"] or meta["apply_url"],
                "ats": "workday",
                "wd_host": meta["wd_host"], "wd_tenant": meta["wd_tenant"],
                "wd_site": meta["wd_site"], "wd_job_path": meta["wd_job_path"],
                "wd_reqid": meta["wd_reqid"],
                "gh_org": meta.get("gh_org") or f"workday-{meta['wd_tenant']}",
                "gh_jid": meta.get("gh_jid") or meta["wd_reqid"],
                "slug": args.slug, "flags": meta.get("flags", ""),
            }]
        elif ats == "rippling":
            role_id = None
            for r in conn.execute("SELECT id FROM roles WHERE jd_url LIKE ? OR app_url LIKE ?",
                                  (f"%{meta['rp_jid']}%", f"%{meta['rp_jid']}%")):
                role_id = r["id"]; break
            roles = [{
                "role_id": role_id or 0, "company": meta["company"],
                "role": meta["role"], "loc": meta["location"],
                "exp_req": meta.get("exp_required"), "url": meta.get("jd_url") or meta["apply_url"],
                "ats": "rippling",
                "rp_slug": meta["rp_slug"], "rp_jid": meta["rp_jid"],
                "gh_org": meta.get("gh_org") or f"rippling-{meta['rp_slug']}",
                "gh_jid": meta.get("gh_jid") or meta["rp_jid"][:8],
                "slug": args.slug, "flags": meta.get("flags", ""),
            }]
        else:
            # try to find role_id from db
            role_id = None
            id_key = "ash_jid" if ats == "ashby" else "gh_jid"
            id_val = meta.get(id_key) or meta.get("gh_jid")
            for r in conn.execute("SELECT id FROM roles WHERE app_url LIKE ? OR jd_url LIKE ?",
                                  (f"%{id_val}%", f"%{id_val}%")):
                role_id = r["id"]; break
            entry = {
                "role_id": role_id or 0, "company": meta["company"],
                "role": meta["role"], "loc": meta["location"],
                "exp_req": meta.get("exp_required"), "url": meta["apply_url"],
                "ats": ats,
                "gh_org": meta.get("gh_org"), "gh_jid": meta.get("gh_jid"),
                "slug": args.slug, "flags": meta.get("flags", ""),
            }
            if ats == "ashby":
                entry["ash_org"] = meta.get("ash_org") or meta.get("gh_org")
                entry["ash_jid"] = meta.get("ash_jid") or meta.get("gh_jid")
            roles = [entry]

    print(f"[inline_submit] processing {len(roles)} role(s)", file=sys.stderr)
    results = []
    for i, role in enumerate(roles, 1):
        print(f"\n[inline_submit] === [{i}/{len(roles)}] {role['slug']} "
              f"({role['company']} — {role['role']}) ===", file=sys.stderr)
        t0 = time.time()
        res = prep_role(role, dry_run=args.dry_run, ignore_csp_block=args.ignore_csp_block,
                        skip_head_probe=args.no_head_probe, ignore_blockers=args.ignore_blockers)
        res["elapsed_s"] = round(time.time() - t0, 1)
        results.append(res)
        status = "OK" if res["ok"] else f"ABORT({res['phase_failed']})"
        print(f"[inline_submit] {res['slug']}: {status} in {res['elapsed_s']}s", file=sys.stderr)
        if not res["ok"]:
            print(f"  error: {res.get('error','')[:400]}", file=sys.stderr)

    # batch summary
    print(json.dumps({
        "total": len(results),
        "ok": sum(1 for r in results if r["ok"]),
        "aborted": sum(1 for r in results if not r["ok"]),
        "results": results,
    }, indent=2, default=str))
    return 0 if all(r["ok"] for r in results) else 3


if __name__ == "__main__":
    sys.exit(main())
