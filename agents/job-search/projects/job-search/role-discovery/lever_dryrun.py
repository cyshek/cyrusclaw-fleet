#!/usr/bin/env python3
"""
lever_dryrun.py — Generate a NO-SUBMIT, dry-run application fill spec
for a Lever-hosted role.

Lever applications are at:
    https://jobs.lever.co/<org>/<jobid>/apply

The HTML embeds card schemas as JSON in hidden inputs:
    <input value="<json>" name="cards[<cardId>][baseTemplate]">

Each card has a list of `fields` with type, text, required, options.
Standard fields: name, email, phone, location, org (current company),
urls[LinkedIn], urls[GitHub], urls[Portfolio], resume.
EEO fields: eeo[gender], eeo[race], eeo[veteran], eeo[disability], etc.

ZERO writes to Lever. Read-only. No POSTs. Ever.

Usage:
    .venv/bin/python lever_dryrun.py <lever_url> [<url2> ...]
    .venv/bin/python lever_dryrun.py --slug <packet-slug>

Output:
    ../applications/dryrun/lever-{org}-{jobid}.json
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

# Reuse Greenhouse resolvers — same personal-info shape, same labels.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import greenhouse_dryrun as gh  # noqa: E402

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
PERSONAL_INFO_PATH = PROJECT_ROOT / "personal-info.json"
OUTPUT_DIR = PROJECT_ROOT / "applications" / "dryrun"

HTTP_TIMEOUT = 25
UA = "job-search-agent/1.0 (lever-dryrun)"

LEVER_URL_RX = re.compile(r"jobs\.lever\.co/([^/]+)/([0-9a-f-]{8,})")


def parse_lever_url(url: str) -> tuple[str, str]:
    m = LEVER_URL_RX.search(url)
    if not m:
        raise ValueError(f"Not a Lever URL: {url}")
    return m.group(1), m.group(2)


def fetch_apply_html(org: str, job_id: str) -> tuple[str, str]:
    """Returns (apply_url, html). Apply page is jobs.lever.co/<org>/<id>/apply."""
    apply_url = f"https://jobs.lever.co/{org}/{job_id}/apply"
    r = requests.get(apply_url, timeout=HTTP_TIMEOUT, headers={"User-Agent": UA})
    if r.status_code != 200:
        raise RuntimeError(f"Lever apply page HTTP {r.status_code} for {apply_url}")
    return apply_url, r.text


def parse_cards(html: str) -> list[dict]:
    """Extract per-card schemas from the apply page HTML.

    Returns a list of card dicts, each with keys: id, text (card title),
    instructions, fields (list of {type, text, required, options}).
    """
    cards: list[dict] = []
    # `value="<JSON>"   name="cards[<cardId>][baseTemplate]"`
    rx = re.compile(
        r'value="([^"]*)"\s+name="cards\[([^\]]+)\]\[baseTemplate\]"',
        re.DOTALL,
    )
    for raw, cid in rx.findall(html):
        try:
            data = json.loads(html_mod.unescape(raw))
        except Exception:
            continue
        data["_card_id"] = cid
        cards.append(data)
    return cards


def parse_posting_meta(html: str) -> dict:
    """Pull the posting id, role title, and the structured contact location flag
    out of the apply page. Best-effort — used for spec metadata only."""
    meta: dict[str, Any] = {}
    m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
    if m:
        meta["og_title"] = html_mod.unescape(m.group(1))
    if 'data-qa="structured-contact-location-question"' in html:
        meta["structured_location"] = True
    if 'name="eeo' in html:
        meta["has_eeo"] = True
    if 'data-qa="input-resume"' in html:
        meta["has_resume_input"] = True
    return meta


# ---------------------------------------------------------------------------
# Standard top-level fields (name/email/phone/location/org/urls/resume).
# These are NOT inside cards — they're the fixed application form fields.
# We synthesize entries for them using Greenhouse-style resolvers.
# ---------------------------------------------------------------------------

STANDARD_FIELDS = [
    # (id, label, ftype, required)
    ("name",            "Full name",       "input_text", True),
    ("email",           "Email",           "input_text", True),
    ("phone",           "Phone",           "input_text", True),
    ("location",        "Current location","input_text", True),
    ("org",             "Current company", "input_text", False),
    ("urls[LinkedIn]",  "LinkedIn URL",    "input_text", False),
    ("urls[GitHub]",    "GitHub URL",      "input_text", False),
    ("urls[Portfolio]", "Portfolio URL",   "input_text", False),
    ("resume",          "Resume/CV",       "input_file", True),
]


# Map Lever native field types -> Greenhouse-style ftypes that the filler
# already understands (so we can reuse greenhouse_filler-style buckets).
LEVER_TYPE_MAP = {
    "text":             "input_text",
    "textarea":         "textarea",
    "dropdown":         "multi_value_single_select",
    "multiple-choice":  "multi_value_single_select",  # radio buttons
    "multiple-select":  "multi_value_multi_select",   # checkboxes
}


def card_field_ftype(lever_type: str) -> str:
    return LEVER_TYPE_MAP.get(lever_type, "input_text")


def card_field_id(card_id: str, idx: int) -> str:
    """Lever uses cards[<cardId>][field<idx>] for the fillable input name."""
    return f"cards[{card_id}][field{idx}]"


# ---------------------------------------------------------------------------
# Resolver helpers
# ---------------------------------------------------------------------------

DECLINE_LABELS = [
    "Decline to self identify", "Decline to self-identify",
    "Decline to identify", "Prefer not to say", "Prefer not to disclose",
    "I do not wish to answer", "I don't wish to answer",
    "Choose not to disclose", "I don't wish to self-identify",
]


def is_eeo_label(label: str) -> bool:
    L = label.lower()
    return any(k in L for k in [
        "gender", "ethnic", "race", "veteran", "disability", "lgbt",
        "transgender", "self-identify", "self identify",
    ])


def resolve_card_field(personal: dict, card_text: str, lever_field: dict,
                       fid: str) -> dict:
    """Resolve a Lever card field into a dryrun spec entry. Falls back to
    Greenhouse's resolver registry for label matching."""
    label = lever_field.get("text") or card_text or ""
    required = bool(lever_field.get("required"))
    ftype = card_field_ftype(lever_field.get("type", "text"))
    options = None
    if lever_field.get("options"):
        options = [
            {"label": o.get("text"), "value": o.get("optionId") or o.get("text")}
            for o in lever_field["options"]
        ]

    out = {
        "id": fid,
        "label": label,
        "type": ftype,
        "lever_type": lever_field.get("type"),
        "required": required,
        "value": None,
        "source": None,
        "status": None,
        "matched_rule": None,
        "options": options,
    }

    # Build a synthetic Greenhouse-style "field" object so resolvers that
    # touch field.values still work.
    synth = {
        "name": fid,
        "type": ftype,
        "values": [{"label": o["label"], "value": o["value"]} for o in (options or [])],
    }

    resolver_key = gh.find_resolver(label)
    out["matched_rule"] = resolver_key
    if resolver_key:
        try:
            kind, value, source = gh.RESOLVERS[resolver_key](personal, synth)
        except Exception as e:
            kind, value, source = "unresolved", f"resolver raised: {e}", None
        if kind == "ok":
            out["value"] = value; out["status"] = "filled"; out["source"] = source
        elif kind == "decline":
            out["value"] = value; out["status"] = "declined"; out["source"] = source
        else:
            out["value"] = gh.UNRESOLVED; out["status"] = "unresolved"; out["source"] = value
    else:
        out["value"] = gh.UNRESOLVED; out["status"] = "unresolved"
        out["source"] = f"no LABEL_RULES match for label={label!r}"

    # Lever-specific common patterns we can answer with sensible defaults.
    if out["status"] == "unresolved":
        L = label.lower()
        # AI notetaker consent — default Yes (Cyrus is fine with it).
        if ("ai notetaker" in L or "ai notetakers" in L or "transcribe conversations" in L) and options:
            for opt in options:
                ol = (opt["label"] or "").strip().lower()
                if ol.startswith("yes") or "i consent" in ol or "i agree" in ol:
                    out["value"] = opt["label"]; out["status"] = "filled"
                    out["source"] = "lever_default (ai_notetaker_consent=Yes)"; return out
        # Language skills checkboxes — default English only.
        if ("language" in L and "skill" in L) and options:
            for opt in options:
                if "english" in (opt["label"] or "").lower():
                    out["value"] = [opt["label"]]; out["status"] = "filled"
                    out["source"] = "lever_default (languages=English)"; return out
        # Name pronunciation — default to first name.
        if "name pronunciation" in L or "how do you pronounce" in L:
            try:
                out["value"] = personal["identity"]["first_name"]
                out["status"] = "filled"; out["source"] = "lever_default (pronunciation=first_name)"
                return out
            except Exception:
                pass
        # "How did you hear about this opportunity?" — prefer LinkedIn, else a
        # neutral option. Required on many tenants (Palantir) and otherwise
        # silently blocks submit.
        if ("how did you hear" in L or "how do you hear" in L or
                "where did you hear" in L or "source of application" in L
                or "how were you referred" in L) and options:
            pref_order = ("linkedin", "job board", "company website", "website",
                          "online", "other", "social media")
            picked = None
            for key in pref_order:
                for opt in options:
                    if key in (opt["label"] or "").lower():
                        picked = opt["label"]; break
                if picked:
                    break
            if not picked:
                # first real (non-placeholder) option
                for opt in options:
                    ol = (opt["label"] or "").strip()
                    if ol and ol.lower() not in ("select...", "select", "-", "--", "choose"):
                        picked = ol; break
            if picked:
                out["value"] = picked; out["status"] = "filled"
                out["source"] = f"lever_default (how_did_you_hear -> {picked})"
                return out

    # Long-text essay questions — will be filled by cover_answer_generator
    # downstream. Mark as filled with a placeholder so they don't block dryrun.
    if out["status"] == "unresolved" and ftype == "textarea":
        out["value"] = "<<COVER_ANSWER>>"
        out["status"] = "filled"
        out["source"] = "lever_default (textarea → deferred to cover_answer_generator)"
        return out

    # Security clearance Yes/No mapping (resolver returns 'None' string).
    if (out["matched_rule"] == "security_clearance" and options
            and out["value"] in ("None", "none", None)):
        opt_labels = [o["label"] for o in options]
        L = label.lower()
        is_citizen = personal.get("work_authorization", {}).get("status", "").lower() == "us_citizen"
        if "hold" in L or "currently" in L:
            pick = "No"
        elif "eligible" in L or "obtain" in L:
            pick = "Yes" if is_citizen else "No"
        else:
            pick = "No"
        if pick in opt_labels:
            out["value"] = pick
            out["status"] = "filled"
            out["source"] = f"lever_default (security_clearance → {pick} based on label)"
            return out

    # EEO/demographic default decline (mirror greenhouse_dryrun behavior).
    if out["status"] == "unresolved" and is_eeo_label(label):
        # Pick a decline option if available.
        if options:
            for opt in options:
                if any(d.lower() in (opt["label"] or "").lower() for d in DECLINE_LABELS):
                    out["value"] = opt["label"]
                    out["status"] = "declined"
                    out["source"] = "eeo_default (matched decline option)"
                    out["compliance"] = "eeo"
                    return out
        out["value"] = "Decline To Self Identify"
        out["status"] = "declined"
        out["source"] = "eeo_default (no decline option found, freeform)"
        out["compliance"] = "eeo"
        return out

    # Sanity-check selects: ensure value is among options.
    if out["status"] == "filled" and ftype in ("multi_value_single_select", "multi_value_multi_select") and options:
        labels = [o["label"] for o in options]
        if out["value"] not in labels:
            out["status"] = "filled_needs_review"
            out["source"] = (out["source"] or "") + f" | NOTE: '{out['value']}' not literally in options"

    # LAST-RESORT for REQUIRED single-select/radio still unresolved: pick the
    # first real (non-placeholder) option so the form is submittable. This is
    # a deliberate, conservative default — only fires for required choice
    # fields with NO better mapping, and is logged as needs_review so it's
    # auditable. Without it, one unmapped required dropdown silently blocks the
    # entire Lever submit (observed: Palantir 817, 2026-06-03).
    if (out["status"] == "unresolved" and required and options
            and ftype in ("multi_value_single_select",)
            and not is_eeo_label(label)):
        for opt in options:
            ol = (opt["label"] or "").strip()
            if ol and ol.lower() not in ("select...", "select", "-", "--", "choose",
                                          "please select", "choose..."):
                out["value"] = ol
                out["status"] = "filled_needs_review"
                out["source"] = f"lever_default (required-select last-resort -> {ol})"
                return out

    return out


def resolve_standard_field(personal: dict, fid: str, label: str, ftype: str,
                            required: bool) -> dict:
    out = {
        "id": fid,
        "label": label,
        "type": ftype,
        "lever_type": None,
        "required": required,
        "value": None,
        "source": None,
        "status": None,
        "matched_rule": None,
        "options": None,
    }
    if ftype == "input_file":
        out["value"] = "<<RESUME_PDF_PATH>>"
        out["status"] = "filled"
        out["source"] = "lever_resume_input"
        return out
    resolver_key = gh.find_resolver(label)
    out["matched_rule"] = resolver_key
    if resolver_key:
        try:
            kind, value, source = gh.RESOLVERS[resolver_key](personal, {"name": fid, "type": ftype})
        except Exception as e:
            kind, value, source = "unresolved", f"resolver raised: {e}", None
        if kind == "ok":
            out["value"] = value; out["status"] = "filled"; out["source"] = source
        elif kind == "decline":
            out["value"] = value; out["status"] = "declined"; out["source"] = source
        else:
            out["value"] = gh.UNRESOLVED; out["status"] = "unresolved"; out["source"] = value
    else:
        out["value"] = gh.UNRESOLVED; out["status"] = "unresolved"
        out["source"] = f"no LABEL_RULES match for label={label!r}"
    return out


# ---------------------------------------------------------------------------
# Build dryrun
# ---------------------------------------------------------------------------

def build_dryrun(personal: dict, role_url: str) -> dict:
    org, job_id = parse_lever_url(role_url)
    apply_url, html = fetch_apply_html(org, job_id)
    cards = parse_cards(html)
    meta = parse_posting_meta(html)

    # Inject runtime context (company name) for cover essay resolvers.
    personal = dict(personal)
    personal["_company_name"] = (meta.get("og_title", "").split(" - ")[0]
                                  if meta.get("og_title") else org.title())
    tmpl_path = PROJECT_ROOT / "why-company-template.md"
    if tmpl_path.exists():
        raw = tmpl_path.read_text()
        if "---" in raw:
            raw = raw.split("---", 2)[-1]
        personal["_why_company_template"] = raw.strip()

    fields_out: list[dict] = []
    unresolved: list[dict] = []
    blockers: list[dict] = []

    # 1. Standard top-level fields
    for fid, label, ftype, required in STANDARD_FIELDS:
        entry = resolve_standard_field(personal, fid, label, ftype, required)
        fields_out.append(entry)
        if entry["status"] == "unresolved":
            unresolved.append({"id": fid, "label": label, "required": required,
                                "reason": entry["source"]})
            if required:
                blockers.append({"id": fid, "label": label, "reason": entry["source"]})

    # 2. Per-card supplementary fields
    for card in cards:
        card_text = card.get("text") or ""
        for idx, lf in enumerate(card.get("fields") or []):
            fid = card_field_id(card["_card_id"], idx)
            entry = resolve_card_field(personal, card_text, lf, fid)
            entry["card_text"] = card_text
            fields_out.append(entry)
            if entry["status"] == "unresolved":
                unresolved.append({"id": fid, "label": entry["label"],
                                    "required": entry["required"],
                                    "reason": entry["source"]})
                if entry["required"]:
                    blockers.append({"id": fid, "label": entry["label"],
                                      "reason": entry["source"]})

    # 3. EEO block (Lever's standard demographic questions live in named
    #    inputs like eeo[gender], eeo[race], etc. We can't enumerate them
    #    statically without parsing the page, but they're typically optional
    #    and the filler will set them to "decline" via JS at runtime.)
    # 2b. Posting-location select (multi-office postings). Lever renders a
    #     REQUIRED <select name="opportunityLocationId"> ("Which location are
    #     you applying for?") that is NOT a card and is NOT discovered by the
    #     card walker. US onsite/relocation is never a knockout (Cyrus relocates
    #     anywhere in the US) -> pick the first concrete option.
    for plf in parse_posting_location(html):
        fields_out.append(plf)

    eeo_fields = parse_eeo_fields(html)
    for ef in eeo_fields:
        entry = {
            "id": ef["id"],
            "label": ef["label"],
            "type": "multi_value_single_select",
            "lever_type": "eeo",
            "required": ef.get("required", False),
            "value": "Decline To Self Identify",
            "source": "eeo_default (lever EEO block)",
            "status": "declined",
            "matched_rule": None,
            "options": ef.get("options"),
            "compliance": "eeo",
        }
        fields_out.append(entry)

    counts = {
        "total_fields": len(fields_out),
        "filled": sum(1 for f in fields_out if f["status"] == "filled"),
        "filled_needs_review": sum(1 for f in fields_out if f["status"] == "filled_needs_review"),
        "declined": sum(1 for f in fields_out if f["status"] == "declined"),
        "unresolved": len(unresolved),
        "blockers": len(blockers),
    }

    return {
        "ats": "lever",
        "role_url": role_url,
        "apply_url": apply_url,
        "org": org,
        "job_id": job_id,
        "job_title": meta.get("og_title"),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ready_to_submit": counts["blockers"] == 0,
        "counts": counts,
        "fields": fields_out,
        "unresolved": unresolved,
        "blockers": blockers,
        "meta": meta,
    }


def parse_posting_location(html: str) -> list[dict]:
    """Extract the REQUIRED multi-office posting-location select
    (<select name="opportunityLocationId"> "Which location are you applying
    for?"). Lever shows this only on postings tied to multiple office
    locations; it is not a card and not part of STANDARD_FIELDS, so the card
    walker misses it and the runtime submit fails validation ("Please select a
    location"). US onsite/relocation is NEVER a knockout (Cyrus relocates
    anywhere in the US) -> pick the first concrete option. Returns a filled
    multi_value_single_select field (or [] when absent)."""
    m = re.search(r'<select name="opportunityLocationId".*?</select>', html, re.S)
    if not m:
        return []
    block = m.group(0)
    options = []
    for val, txt in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', block):
        label = html_mod.unescape(txt).strip()
        if not val or label.lower() in ("select...", "select", "-", "--", "choose", "choose..."):
            continue
        options.append({"label": label, "value": val})
    if not options:
        return []
    chosen = options[0]["label"]  # first concrete US office; relocation-OK
    return [{
        "id": "opportunityLocationId",
        "label": "Which location are you applying for?",
        "type": "multi_value_single_select",
        "lever_type": "dropdown",
        "required": True,
        "value": chosen,
        "source": "lever_posting_location (first US office; relocation-OK)",
        "status": "filled",
        "matched_rule": "posting_location",
        "options": options,
    }]


def parse_eeo_fields(html: str) -> list[dict]:
    """Best-effort extraction of EEO field names from the apply page.
    Returns a list of {id, label, options:[...]}."""
    out = []
    # Find all unique eeo[...] field names.
    names = sorted(set(re.findall(r'name="(eeo\[[^\]]+\])"', html)))
    for name in names:
        # Pull a label hint by looking for nearby <label>/<span> text — not
        # strictly necessary; the filler picks decline by JS. Use the bracket
        # key as the label.
        key = re.search(r'eeo\[([^\]]+)\]', name).group(1)
        label = key.replace("_", " ").title()
        out.append({"id": name, "label": label, "options": None, "required": False})
    return out


def write_dryrun(report: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f'lever-{report["org"]}-{report["job_id"]}.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Lever application dry-run spec generator (NO SUBMIT).")
    parser.add_argument("urls", nargs="*", help="One or more Lever role URLs (jobs.lever.co/<org>/<id>).")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if not PERSONAL_INFO_PATH.exists():
        print(f"ERROR: missing {PERSONAL_INFO_PATH}", file=sys.stderr)
        return 2
    personal = json.loads(PERSONAL_INFO_PATH.read_text())

    if not args.urls:
        parser.print_help()
        return 1

    rc = 0
    for url in args.urls:
        try:
            report = build_dryrun(personal, url)
            path = write_dryrun(report)
            if not args.quiet:
                c = report["counts"]
                ready = "READY" if report["ready_to_submit"] else f"BLOCKED({c['blockers']})"
                print(f"{ready:11} {report['org']}/{report['job_id'][:8]} -> {path.name}  "
                      f"filled={c['filled']} review={c['filled_needs_review']} "
                      f"declined={c['declined']} unresolved={c['unresolved']}")
        except Exception as e:
            rc = 1
            print(f"ERROR processing {url}: {type(e).__name__}: {e}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
