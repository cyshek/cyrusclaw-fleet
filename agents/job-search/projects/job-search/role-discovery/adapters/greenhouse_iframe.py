"""Greenhouse-iframe wrapper adapter.

Some companies host their careers pages on a branded domain that embeds the
standard Greenhouse `/embed/job_app` iframe. The apply form is identical to a
native Greenhouse board — it's the same boards-api JSON, the same react-select
widgets, the same Filestack resume picker, the same invisible reCAPTCHA. The
only difference is the URL shape: instead of `job-boards.greenhouse.io/<slug>/jobs/<jid>`,
the user-facing URL is on the company's own domain and carries `?gh_jid=<jid>`.

This adapter provides a host→slug map for the 13 known iframe wrappers and a
`host_to_gh_slug()` helper used by `inline_submit.py:detect_ats()` to route
these roles through the Greenhouse pipeline.

Source: CUSTOM-ATS-SCOUT-2026-05-13.md.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# Host (lowercased, no port) -> Greenhouse board slug.
# Only the 13 confirmed iframe wrappers from the scout report. Bare-domain
# entries (e.g. `databricks.com`) match both with and without `www.` because
# `_normalize_host()` strips a leading `www.` before lookup.
HOST_TO_GH_SLUG: dict[str, str] = {
    "careers.datadoghq.com":      "datadog",
    "databricks.com":             "databricks",
    "stripe.com":                 "stripe",
    "coreweave.com":              "coreweave",
    "abnormal.ai":                "abnormalsecurity",
    "jobs.dropbox.com":           "dropbox",
    "jobs.elastic.co":            "elastic",
    "okta.com":                   "okta",
    "salesloft.com":              "salesloft",
    "pinterestcareers.com":       "pinterest",
    "mongodb.com":                "mongodb",
    "orca.security":              "orcasecurity",
    "app.careerpuck.com":         "lyft",  # careerpuck is a third-party careers wrapper around GH
    "fivetran.com":               "fivetran",  # added 2026-05-16 — overnight scout miss
    "guidewheel.com":             "guidewheel",  # added 2026-05-24 — role 1110 worker discovered iframe wrapper
    "comet.com":                  "comet",  # added 2026-05-24 — role 1233 worker (Opik PM); /site/about-us/careers/job/?gh_jid=...
    "wiz.io":                     "wizinc",  # added 2026-05-25 — role 1370 SUBMIT subagent; /careers/job/<jid>/:title?gh_jid=<jid>
    "asana.com":                  "asana",  # added 2026-05-25 — role 1542 SUBMIT subagent; /jobs/apply/<jid>?gh_jid=<jid>
    "smartcat.com":               "smartcatplatforminc",  # added 2026-05-26 — role 1136 chain worker #003; /career/?gh_jid=<jid> wrapper around boards-api smartcatplatforminc
    # added 2026-06-04 — gh_jid careers-page cohort (org slug verified live via boards-api)
    "samsara.com":                "samsara",
    "harness.io":                 "harnessinc",
    "fanduel.careers":            "fanduel",
    "wayve.firststage.co":        "wayve",
    "digicert.com":               "digicert",
    "netskope.com":               "netskope",
    "careers.nintendo.com":       "nintendo",
    "paystand.com":               "paystand",
    "credera.com":                "credera",
    "actively.ai":                "activelyai",
    # added 2026-06-08 — gh_jid wrapper-host cohort gap (autonomous tick): these
    # hosts carry ?gh_jid= and resolve live via boards-api, but were missing from
    # the map so inline_submit.detect_ats() returned 'unknown' -> resolve_role
    # raised "unsupported ATS URL" and the submit pipeline silently dropped them.
    # Slug verified live via boards-api/v1/boards/<slug>/jobs/<jid> (id match).
    # Unblocks: Dealpath 2454 (was blank/manual-apply), Lob 2625
    # (block_reason=gh-embed-bounce-company-wrapper). Roblox/PubMatic/VideoAmp
    # added for future crawls (current rows stay correctly skip/blocked).
    "dealpath.com":               "dealpath",
    "lob.com":                    "lob",
    "careers.roblox.com":         "roblox",
    "pubmatic.com":               "pubmatic",
    "videoamp.com":               "videoamp",
    # added 2026-06-24 — block.xyz/instacart.careers/coinbase.com gh_jid wrappers
    # slug verified live via boards-api (block→207 jobs, instacart→156, coinbase→116)
    "block.xyz":                  "block",
    "instacart.careers":          "instacart",
    "coinbase.com":               "coinbase",
    "brex.com":                   "brex",
    "fastly.com":                 "fastly",
    # added 2026-06-24 pass10b — gh_jid wrapper-host cohort gap
    "zoominfo.com":               "zoominfo",
    "gigs.com":                   "gigs",
    "salt.security":              "saltsecurity",
    "catonetworks.com":           "catonetworks",
    "taboola.com":                "taboola",
    # added 2026-06-24 pass10b — batch of gh_jid wrapper-hosts discovered during drain pass
    "avathon.com":                "avathon",
    "careers.formlabs.com":       "formlabs",
    "careers.withwaymo.com":      "waymo",
    "nuro.ai":                    "nuro",
    "ripple.com":                 "ripple",
    "wing.com":                   "wing",
    "alloy.com":                  "alloy",
    "intersystems.com":           "intersystems",
    "ixl.com":                    "ixllearning",
    "picarro.com":                "picarroinc",
    "praetorian.com":             "praetorian",
    "rubrik.com":                 "rubrik",
    "esri.com":                   "esri",
    "cribl.io":                   "cribl",
    # added 2026-06-30 — Spot & Tango gh_jid wrapper
    "spotandtango.com":           "spotandtango",
    # added 2026-06-30 batch drain 3972-4014
    "careers.nebius.com":        "nebius",
}

GH_JID_RX = re.compile(r"[?&]gh_jid=(\d+)")
# Stripe path-based listing URL: stripe.com/jobs/listing/<title-slug>/<jid>[/apply]
STRIPE_PATH_JID_RX = re.compile(r"stripe\.com/jobs/listing/[^/]+/(\d+)(?:/apply)?/?$")


def _normalize_host(host: str) -> str:
    h = (host or "").lower().strip()
    if h.startswith("www."):
        h = h[4:]
    return h


def host_to_gh_slug(url: str) -> str | None:
    """Return the Greenhouse board slug if `url` is a known GH-iframe wrapper.

    Returns None for unknown hosts (caller should fall through to other ATS
    detection)."""
    try:
        host = _normalize_host(urlparse(url or "").netloc)
    except Exception:
        return None
    if not host:
        return None
    if host in HOST_TO_GH_SLUG:
        return HOST_TO_GH_SLUG[host]
    # CareerPuck path: `app.careerpuck.com/job-board/<org>/job/<jid>` — the
    # org segment IS the GH slug. Hardcoded to lyft above for now; if more
    # CareerPuck-hosted boards show up, parse the path here.
    return None


def extract_gh_jid(url: str) -> str | None:
    """Extract the gh_jid query param from a wrapper URL.

    Also handles Stripe's path-based listing URLs like
    `stripe.com/jobs/listing/<title>/<jid>/apply` where the jid is in the path
    rather than a query param."""
    m = GH_JID_RX.search(url or "")
    if m:
        return m.group(1)
    m2 = STRIPE_PATH_JID_RX.search(url or "")
    if m2:
        return m2.group(1)
    return None


def is_greenhouse_iframe(url: str) -> bool:
    """True if the URL is a known GH-iframe wrapper AND has a gh_jid."""
    return bool(host_to_gh_slug(url) and extract_gh_jid(url))


def embed_iframe_url(slug: str, jid: str) -> str:
    """Direct GH `/embed/job_app` iframe URL. Per CUSTOM-ATS-SCOUT-2026-05-13,
    every tenant accepts this without a validityToken on first render; the
    token is only enforced at submit-time on tenants that opted in (and we
    can refresh it from the company page if the smoke-test reveals it)."""
    return f"https://job-boards.greenhouse.io/embed/job_app?for={slug}&token={jid}"


def synthetic_jd_url(slug: str, jid: str) -> str:
    """Synthetic Greenhouse hosted-board URL used to feed `greenhouse_dryrun.py`,
    which only accepts greenhouse.io URLs. The boards-api lookup uses
    (slug, jid) directly so the URL itself is just a vehicle."""
    return f"https://job-boards.greenhouse.io/{slug}/jobs/{jid}"
