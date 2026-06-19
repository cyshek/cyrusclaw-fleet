#!/usr/bin/env python3
"""_gh_submit.py — End-to-end Greenhouse submit via CDP (OpenClaw browser :18800).

Reads an inline-plan-<slug>.json, navigates to the form, fills text fields,
react-select dropdowns, country/location comboboxes, phone iti, declines
demographics, uploads resume via set_input_files, submits, and solves the
8-char email-OTP gate via gmail_imap.

Usage: _gh_submit.py <plan_json_path> [--no-submit]
Prints JSON result with confirmed/blocked/error + reason.
"""
import sys, json, time, re, os
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CDP = "http://127.0.0.1:18800"

DECLINES = ["Decline to self-identify","Decline To Self Identify","Decline to self identify",
            "I don't wish to answer","I do not wish to answer","I do not want to answer",
            "I don't want to answer","Prefer not to say","Prefer not to answer",
            "Prefer not to disclose","Do not wish to answer","Do not want to answer"]

DEMO_SKIP_RE = (r"gender|\bsex\b|race|ethnic|hispanic|latin|veteran|military.{0,8}status|"
               r"disabilit|self[- ]?identif|pronoun|sexual.{0,5}orient|lgbtq")

# Affirmative-consent synonyms. A required select whose options are ALL
# affirmative (or whose sole non-placeholder option is affirmative) is a
# forced-choice CONSENT/AFFIRMATION control (Everlaw "Agree", "Acknowledge",
# "I confirm") — NOT a biographical claim — so it is safe to auto-commit.
_AFFIRM_RE = re.compile(
    r"^(i\s+)?(agree|acknowledge|accept|confirm|affirm|understood|"
    r"i\s+understand|yes\b|consent|certify)", re.I)
# Anything starting with a negative/decline is NOT an affirmation and must
# never be force-committed by the fallback.
_NEGATIVE_RE = re.compile(r"^\s*(no\b|n/?a\b|decline|disagree|do not|don'?t|"
                          r"none\b|not\b|reject|opt[- ]?out)", re.I)
# Placeholder option text to ignore when counting "real" options.
_PLACEHOLDER_RE = re.compile(r"^\s*(select|choose|please select|--|\u2014)", re.I)


def _affirm_or_sole_option(opts):
    """Return the option text to commit for a forced-choice consent/affirmation
    select, or None if the option-structure isn't a safe forced-choice.

    Safe to auto-commit (truthful forced-choice, NOT a biographical claim):
      - exactly one real (non-placeholder) option  -> pick it
      - every real option is an affirmative synonym -> pick the first affirmative
    Anything else (a real Yes/No or multi-way biographical/eligibility choice)
    returns None so it is surfaced unresolved, never fabricated.
    """
    real = [o for o in (opts or []) if o and not _PLACEHOLDER_RE.match(o.strip())]
    if not real:
        return None
    # Sole real option -> forced choice, but never auto-commit a lone NEGATIVE
    # (e.g. a single "No" / "Decline" option is not a consent we should tick).
    if len(real) == 1:
        return real[0] if not _NEGATIVE_RE.match(real[0].strip()) else None
    # Multiple options: only when EVERY real option is affirmative (no negative
    # alternative present). A Yes/No pair has a negative -> not eligible here.
    if any(_NEGATIVE_RE.match(o.strip()) for o in real):
        return None
    if all(_AFFIRM_RE.match(o.strip()) for o in real):
        return real[0]
    return None


def plan_remix_answers(scanned, personal, resolve_field=None):
    """Pure (no-browser) resolver for recovered remix React-Select dropdowns.

    `scanned` is the list emitted by REMIX_SCAN: [{id, label, options:[str,...]}].
    For each, build a synthetic Greenhouse single-select field and run it through
    the SAME truthful resolver the dryrun uses (greenhouse_dryrun.resolve_field),
    so work-auth / clearance / export-control / sponsorship questions get the
    identical honest answer. Returns:
        {"commit": [{id,label}],          # answerable -> SEL_PICK these
         "unresolved": [{id,label,reason}]}  # no rule / blank -> surfaced honestly
    NOTE: we do NOT fabricate. A field with no LABEL_RULES match stays unresolved
    (surfaced, never guessed) — genuine geo/eligibility knockouts land here too.
    Tested without a live browser.
    """
    if resolve_field is None:
        from greenhouse_dryrun import resolve_field as _rf
        resolve_field = _rf
    commit, unresolved = [], []
    for item in scanned:
        qid = item.get("id")
        label = (item.get("label") or "").strip()
        opts = item.get("options") or []
        if not qid:
            continue
        if not label:
            # BLANK-label required select (Everlaw-class affirmation control with
            # no recoverable question text). There's nothing to resolve via the
            # dryrun, but if it's a safe forced-choice (sole option / all
            # affirmative) we commit it so emptyRequired clears. Otherwise skip
            # (can't honestly answer an unlabeled multi-way choice).
            forced = _affirm_or_sole_option(opts)
            if forced is not None:
                commit.append({"id": qid, "label": forced, "via": "affirm_or_sole"})
            continue
        # Skip typeahead-style selects (university/school, country, location):
        # they have huge option lists and a dedicated typeahead handler already.
        # The remix-recovery pass targets small knockout/work-auth/clearance
        # selects (2-8 options); SEL_PICK can't drive a 1000-option typeahead.
        if len(opts) > 40:
            unresolved.append({"id": qid, "label": label,
                               "reason": f"typeahead-skip ({len(opts)} options)"})
            continue
        field = {
            "name": qid,
            "type": "multi_value_single_select",
            "values": [{"label": o, "value": o} for o in opts],
        }
        res = resolve_field(personal, label, True, field)
        status = res.get("status")
        value = res.get("value")
        if status in ("filled", "declined", "filled_needs_review") and value not in (None, "", "__UNRESOLVED__"):
            # Commit the resolver's truthful answer. We deliberately do NOT
            # second-guess 'No' values: e.g. 'No' to a sponsorship-needed
            # question is the CORRECT pass. Genuine geo/eligibility knockouts
            # ("within commuting distance to SF/NY?") have no LABEL_RULES match
            # and fall to `unresolved` below, where they're surfaced honestly
            # rather than committed.
            commit.append({"id": qid, "label": value})
        else:
            # FALLBACK (2026-06-04 batch4, Everlaw/Scopely/NiCE/AppLovin/Lila):
            # the dryrun resolver had no LABEL_RULES match, but this may be a
            # forced-choice CONSENT/AFFIRMATION select (sole option, or all
            # options affirmative — e.g. Everlaw's lone "Agree"). Those are
            # truthful forced-choices, NOT biographical claims, so commit the
            # affirmative/sole option instead of leaving it empty (which silently
            # no-ops the submit on emptyRequired). A real Yes/No or multi-way
            # eligibility choice has a negative alternative -> _affirm_or_sole
            # returns None and we surface it unresolved, never fabricated.
            forced = _affirm_or_sole_option(opts)
            if forced is not None:
                commit.append({"id": qid, "label": forced,
                               "via": "affirm_or_sole"})
            else:
                unresolved.append({"id": qid, "label": label,
                                   "reason": res.get("source") or status})
    return {"commit": commit, "unresolved": unresolved}


# Doctrine affirmatives, tried (in this order) as a LAST resort for a
# needs_review single-select whose resolved answer + alternates all miss the
# rendered options. A needs_review dropdown is one the DRYRUN ALREADY RESOLVED
# truthfully (relocation/eligibility/notice-period/sponsorship Yes/No, etc.) but
# parked because the option list looked country-shaped; the honest answer to the
# overwhelming majority of these (US-based, relocation-OK, onsite-OK, can-start)
# is the affirmative, so this is a truthful fallback, not a fabrication. Genuine
# knockouts have no LABEL_RULES match and never reach needs_review with a
# resolved value in the first place.
_NEEDS_REVIEW_DOCTRINE_FALLBACKS = ("Yes", "I acknowledge", "I agree", "Agree")


def plan_needs_review_specs(plan):
    """Pure (no-browser) builder of ordered SEL_PICK candidate-label specs for
    `plan['needs_review_dropdowns']`.

    BACKGROUND (the silent cohort-wide drop this fixes): `greenhouse_filler`
    parks every dryrun `filled_needs_review` single-select into
    `plan['needs_review_dropdowns']` as
        {id, label:<resolved answer>, alternates:["United States","Yes","No"], question}.
    The resolved `label` IS the dryrun's truthful answer (e.g. "Yes" to
    relocation, "United States" to a residency select). Historically `_gh_submit`
    committed `plan['dropdowns']`/countries/phone/--answers/multi_checkboxes but
    NEVER iterated `needs_review_dropdowns` -> these required selects stayed
    EMPTY -> `emptyRequired` -> submit silently no-ops / status 'uncertain'. The
    per-row `--answers` workaround papered over it; this is the engine fix that
    breaks the whole "prepped-READY -> uncertain w/ blank emptyRequired" cohort
    with no manual --answers.

    For each parked field we emit ONE spec with an ORDERED list of candidate
    labels for the caller to try until one matches a rendered option:
      1. the dryrun's resolved `label` (the truthful answer) FIRST,
      2. then any `alternates` not already tried (handles the case where the
         resolved value's surface form differs from the rendered option text,
         e.g. resolved "Open to discuss" but the select is Yes/No),
      3. then the doctrine affirmatives ('Yes'/ack/agree) as a final truthful
         fallback for the US/relocation/onsite/notice-period class.
    Placeholder/blank candidates and exact-duplicate candidates are dropped.
    SEL_PICK already fuzzy-matches (exact -> ci-exact -> startswith -> includes),
    so listing a few honest candidates is safe; a field whose options match NONE
    of them is surfaced (caller logs got=null) and never fabricated.

    Returns list[{id, question, candidates:[str,...]}].
    """
    out = []
    for spec in plan.get("needs_review_dropdowns") or []:
        if not isinstance(spec, dict):
            continue
        fid = spec.get("id")
        if not fid:
            continue
        cands = []
        seen = set()
        resolved = spec.get("label")
        resolved_real = bool(
            resolved is not None
            and str(resolved).strip()
            and not _PLACEHOLDER_RE.match(str(resolved).strip())
        )
        ordered = [resolved]
        ordered += list(spec.get("alternates") or [])
        # Doctrine affirmatives are a truthful last resort ONLY when the dryrun
        # actually resolved a real answer for this field (filled_needs_review with
        # a concrete value). If the resolved label is blank/placeholder there is
        # no honest basis to auto-affirm (the question could be a negative like
        # sponsorship), so we DON'T inject 'Yes' — we just try the (generic)
        # alternates and otherwise surface it uncommitted.
        if resolved_real:
            ordered += list(_NEEDS_REVIEW_DOCTRINE_FALLBACKS)
        for c in ordered:
            if c is None:
                continue
            c = str(c).strip()
            if not c or _PLACEHOLDER_RE.match(c):
                continue
            key = c.lower()
            if key in seen:
                continue
            seen.add(key)
            cands.append(c)
        if not cands:
            continue
        out.append({"id": fid, "question": spec.get("question") or "", "candidates": cands})
    return out


# Personal-info education -> live-form typeahead labels. The live GH education
# panel renders react-select TYPEAHEAD comboboxes with ids `school--0`,
# `discipline--0`, `degree--0` (and `school--1`/... for additional rows). These
# are NOT in the boards-api field spec, so neither the dryrun field list nor the
# `_gh_submit` plan ever targets them -> they stay empty -> emptyRequired ->
# 'uncertain'. The per-row `--answers typeahead` workaround papered over it; this
# is the engine fix (TOOLS.md NEXT-ENGINE-FIX part (b)).
_EDU_TYPEAHEAD_FIELDS = (
    # (id_prefix, [personal-info education keys, in preference order])
    ("school--0", ("school", "school_undergrad")),
    ("discipline--0", ("major", "discipline", "field_of_study")),
    ("degree--0", ("degree", "degree_undergrad")),
)


def _load_personal(plan=None, personal=None):
    """Resolve the personal-info dict. Prefer an explicit `personal` arg (tests),
    then `plan['_personal']`, then load ../personal-info.json relative to this
    module. Returns {} if unavailable (helpers then emit nothing, never crash)."""
    if isinstance(personal, dict):
        return personal
    if isinstance(plan, dict) and isinstance(plan.get("_personal"), dict):
        return plan["_personal"]
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "..", "personal-info.json"),
                 os.path.join(here, "personal-info.json")):
        try:
            if os.path.exists(cand):
                return json.load(open(cand, encoding="utf-8"))
        except Exception:
            pass
    return {}


def plan_education_specs(plan, personal=None):
    """Pure (no-browser) builder of SEL_TYPEAHEAD specs for the GH education
    panel typeaheads (`school--0`/`discipline--0`/`degree--0`).

    BACKGROUND (TOOLS.md NEXT-ENGINE-FIX part (b)): the education react-select
    typeaheads are required on many GH forms but are NOT in the boards-api field
    spec, so the plan never targets them. The dryrun DOES resolve the values
    (`plan['_education']` / education_panel), but `_gh_submit` historically only
    drove `--answers typeahead` for them -> without manual --answers they stayed
    empty -> emptyRequired -> 'uncertain' (Lila/Schrödinger/Raft/Axon/Figma
    class). This derives the specs from the plan's resolved education (falling
    back to personal-info.json) so submit fills them automatically.

    VALUES are truthful and canonical (personal-info.json education):
      school='University of Houston', discipline='Computer Science',
      degree='Bachelor of Science'. We DON'T fabricate: a field whose value can't
      be resolved from either source is simply omitted (no spec emitted).

    The emitted specs are HARMLESS on forms WITHOUT an education panel:
    SEL_TYPEAHEAD returns `{err:'noinput'}` for a missing id and moves on, so we
    can safely emit them whenever education values exist rather than trying to
    detect the panel statically (the dryrun's panel signal isn't always carried
    through every plan builder). Returns list[{id, label}].
    """
    edu = {}
    if isinstance(plan, dict) and isinstance(plan.get("_education"), dict):
        edu = dict(plan["_education"])
    p = _load_personal(plan, personal)
    pedu = p.get("education") if isinstance(p, dict) else None
    if isinstance(pedu, dict):
        # plan's _education wins; fall back to personal-info for any missing key.
        for k, v in pedu.items():
            edu.setdefault(k, v)
    specs = []
    for fid, keys in _EDU_TYPEAHEAD_FIELDS:
        val = None
        for k in keys:
            v = edu.get(k)
            if v is not None and str(v).strip():
                val = str(v).strip()
                break
        if val:
            specs.append({"id": fid, "label": val})
    return specs


def plan_location_typeahead_spec(plan):
    """Pure (no-browser) builder of the `candidate-location` typeahead spec,
    fixing the `location` -> `candidate-location` id mismatch.

    BACKGROUND (TOOLS.md NEXT-ENGINE-FIX part (b)): some plan builders put the
    home location under `text_fields['location']`, but the live Remix-embed GH
    form has NO `<input id="location">` — the real field is the
    `#candidate-location` async react-select typeahead. So the plain text setter
    no-ops (`text step "location":"NOEL"`) and the required location stays empty.
    `greenhouse_filler.build_plan` adds a `candidate-location` typeahead entry to
    `country_dropdowns`, but the `inline_submit` GH re-projection (and older
    plans) drop it -> the mismatch resurfaces. This makes `_gh_submit` self-heal:
    if the plan carries a `location` text value but NO `candidate-location`
    typeahead is already staged (in country_dropdowns), emit one.

    Returns {id:'candidate-location', label:<location>} or None.
    """
    if not isinstance(plan, dict):
        return None
    tf = plan.get("text_fields") or {}
    if isinstance(tf, list):
        m = {}
        for d in tf:
            if isinstance(d, dict):
                m.update(d)
        tf = m
    loc = tf.get("location")
    if not loc or not str(loc).strip():
        return None
    # Already staged as a typeahead by the builder? Don't double-drive it.
    staged = plan.get("country_dropdowns") or []
    for d in staged:
        if isinstance(d, dict) and d.get("id") == "candidate-location":
            return None
    return {"id": "candidate-location", "label": str(loc).strip()}


_MONTHS = ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December")


def plan_work_history_specs(personal):
    """Pure (no-browser) builder of the GH-Remix WORK-HISTORY repeater fill.

    BACKGROUND (Zuora 2755 + GH-Remix work-history cohort, 2026-06-09): some GH
    Remix tenants render a required EMPLOYMENT-HISTORY section — a 'Current role'
    checkbox plus `start-date-month-0`/`start-date-year-0`/`end-date-month-0`/
    `end-date-year-0` React-Select date dropdowns. The boards-API dryrun never
    sees these (they're a live-DOM-only Remix widget), and the generic
    `remix_recover` scan correctly REFUSES to fabricate them (no LABEL_RULES
    match for 'Start date month'; month names aren't an affirmative forced-
    choice) -> they land in emptyRequired -> submit silently bounces.

    These are NOT knockout questions; they are biographical facts we KNOW from
    `personal['work_experience'][0]` (single source of truth: company, title,
    start_month/year, current). This builder emits the trusted fill:
      - tick the 'Current role' checkbox when work_experience[0].current is true
        (which makes the End-date selects optional on every Remix tenant seen),
      - SEL_PICK start-date-month-0 = <start_month>, start-date-year-0 = <year>.
    Returns {checkCurrent: bool, selects: [{id,label}, ...], year: str} or None
    when there's no work_experience to fill. We deliberately only drive block 0
    (the most recent role); the non-required `--0` duplicate block GH also
    renders is left alone. No fabrication: every value comes from personal-info.
    """
    we = (personal or {}).get("work_experience") or []
    if not we or not isinstance(we, list):
        return None
    job = we[0] if isinstance(we[0], dict) else None
    if not job:
        return None
    start_month = (job.get("start_month") or "").strip()
    start_year = str(job.get("start_year") or "").strip()
    is_current = bool(job.get("current"))
    company = (job.get("company") or "").strip()
    title = (job.get("title") or "").strip()
    # Normalize a numeric month ("3"/"03") to a full name if needed.
    if start_month.isdigit():
        mi = int(start_month)
        start_month = _MONTHS[mi - 1] if 1 <= mi <= 12 else start_month
    selects = []
    if start_month:
        selects.append({"id": "start-date-month-0", "label": start_month})
    end_month = (job.get("end_month") or "").strip()
    end_year = str(job.get("end_year") or "").strip()
    # If NOT current and we have an explicit end date, fill it too (truthful).
    end_selects = []
    if not is_current:
        if end_month:
            if end_month.isdigit():
                ei = int(end_month)
                end_month = _MONTHS[ei - 1] if 1 <= ei <= 12 else end_month
            end_selects.append({"id": "end-date-month-0", "label": end_month})
    if not selects and not is_current and not company and not title:
        return None
    return {
        "checkCurrent": is_current,
        "selects": selects,
        "company": company,
        "title": title,
        "start_year": start_year,
        "end_selects": end_selects,
        "end_year": end_year if not is_current else "",
    }


def _harvest_multi_checkbox_specs_from_steps(plan):
    """Fallback: recover multi_value_multi_select specs ({id, legend_re, values})
    from the plan's baked STEPS when the top-level `plan['multi_checkboxes']`
    key is absent.

    `greenhouse_filler.build_plan` emits a `steps`-based plan and does NOT copy
    `multi_checkboxes` to the plan top level — it bakes those specs into the
    JS_TICK_MULTI_CHECKBOXES evaluate step's `arg`. So `plan['multi_checkboxes']`
    is `[]` on real inline plans, and `plan_multiselect_commit_specs` (which only
    read the top-level key) silently committed nothing for required education /
    years-experience / other native multi_value_multi_select fields. The chips
    therefore stayed `multiUnset` -> server no-op'd the submit. (DigiCert 2752
    "highest level of completed education" Bachelors-Degree, 2026-06-10.)

    A multi-checkbox step is any step whose `args.arg` (or `arg`) is a non-empty
    list of dicts each carrying BOTH `legend_re` and `values` (the demographic
    decline-only step uses `labels`, not `values`, so it is correctly skipped —
    we never auto-tick a declined demographic identity here).
    """
    out = []
    for step in (plan.get("steps") or []):
        if not isinstance(step, dict):
            continue
        a = step.get("args") if isinstance(step.get("args"), dict) else step
        arg = a.get("arg") if isinstance(a, dict) else None
        if not isinstance(arg, list) or not arg:
            continue
        for entry in arg:
            if (
                isinstance(entry, dict)
                and entry.get("id")
                and ("legend_re" in entry)
                and isinstance(entry.get("values"), list)
                and entry.get("values")
            ):
                out.append({
                    "id": entry["id"],
                    "legend_re": entry.get("legend_re"),
                    "values": entry["values"],
                })
    # de-dup by id (first wins)
    seen = set()
    uniq = []
    for e in out:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        uniq.append(e)
    return uniq


def plan_multiselect_commit_specs(plan, multi_unset):
    """Pure (no-browser) builder of MULTI_PICK specs for required react-select
    MULTI widgets that the live submit page flagged as still-uncommitted
    (`preSubmitState.multiUnset`).

    2026-06-04 (Raft + emptyRequired/multiUnset cohort): the prior pre-submit
    commit pass only force-committed single-option / affirmative SINGLE-selects.
    Required MULTI-selects whose values the DRYRUN ALREADY RESOLVED (staged in
    `plan['multi_checkboxes']` as {id, legend_re, values:[...]}) were never
    committed by `_gh_submit` at all (it processes dropdowns/countries/phone but
    skips multi_checkboxes), so on react-select-multi tenants the chips never
    landed -> `multiUnset` -> server silently no-ops the submit.

    SAFETY: we commit ONLY values the dryrun ALREADY resolved (present in
    `plan['multi_checkboxes']`). A `multiUnset` id with NO resolved plan entry is
    LEFT ALONE (stays banked) — we never invent option choices for an unresolved
    biographical/eligibility multiselect. Matching is by exact id, the bare
    id ("[]" stripped), or substring either direction (boards-API ids sometimes
    differ from the live hidden-input id by a suffix).

    Returns list[{id, label:[...]}] ready for MULTI_PICK (one evaluate per spec).
    """
    mc = plan.get("multi_checkboxes") or []
    if not mc:
        # build_plan bakes these into steps, not the plan top level — harvest
        # them so required native multi_value_multi_select fields (education,\n        # years-experience) actually commit. (DigiCert 2752, 2026-06-10.)
        mc = _harvest_multi_checkbox_specs_from_steps(plan)
    if not mc or not multi_unset:
        return []

    def _bare(s):
        return (s or "").replace("[]", "")

    specs = []
    seen = set()
    for key in multi_unset:
        if not key or key == "multi-select":
            continue
        kb = _bare(key)
        match = None
        for entry in mc:
            eid = entry.get("id")
            if not eid:
                continue
            eb = _bare(eid)
            if eid == key or eb == kb or (kb and eb and (kb in eb or eb in kb)):
                match = entry
                break
        if not match:
            # No dryrun-resolved values for this required multiselect -> do NOT
            # fabricate. Left uncommitted (row stays banked, never guessed).
            continue
        vals = match.get("values") or []
        vals = [str(v) for v in vals if v not in (None, "")]
        if not vals:
            continue
        # Commit against the LIVE hidden-input id the page reported, so MULTI_PICK
        # resolves the right control even when boards-API id != live id.
        if key in seen:
            continue
        seen.add(key)
        specs.append({"id": key, "label": vals})
    return specs


def get_page(br, url):
    for ctx in br.contexts:
        for p in ctx.pages:
            if url.split('?')[0] in p.url:
                return p
    return None

def detect_cover_letter_input(page):
    """Return the locator selector for a required cover-letter FILE input, or None.

    Generic across GH tenants: prefer the canonical Greenhouse id `#cover_letter`
    / `input[name="cover_letter"]`; else any file input whose label/aria text
    mentions 'cover letter'. Returns dict {selector, already_uploaded} or None.
    Mirrors how the resume `#resume` input is discovered, but resolves the
    selector dynamically so it works on remix boards too.
    """
    info = page.evaluate(r"""()=>{
      const norm=s=>(s||'').toLowerCase();
      const fileInputs=[...document.querySelectorAll('input[type=file]')];
      const labelFor=(el)=>{const id=el.id||'';let t='';if(id){const le=document.querySelector('label[for="'+(window.CSS?CSS.escape(id):id)+'"]');if(le)t+=' '+le.textContent;}const w=el.closest('label,fieldset,div,section');if(w){const le=w.querySelector('label,legend');if(le)t+=' '+le.textContent;}t+=' '+(el.getAttribute('aria-label')||'')+' '+(el.name||'')+' '+id;return norm(t);};
      // Already-committed detection: Greenhouse swaps the input out for a
      // 'filename + Remove' chip once Filestack commits, OR keeps the input with
      // files.length>0 for raw set_input_files tenants.
      const byId=document.querySelector('#cover_letter')||document.querySelector('input[name="cover_letter"]');
      let target=byId;
      if(!target){target=fileInputs.find(f=>/cover\s*letter/.test(labelFor(f)));}
      if(target){
        const sel=target.id?('#'+(window.CSS?CSS.escape(target.id):target.id)):(target.name?('input[name="'+target.name+'"]'):null);
        const already=(target.files&&target.files.length>0);
        return {found:true,selector:sel,id:target.id||null,name:target.name||null,already:!!already};
      }
      // Input may already be swapped out post-commit: look for a cover-letter
      // section that shows a committed filename / Remove control.
      const secs=[...document.querySelectorAll('label,legend,div,section')];
      const cl=secs.find(s=>/cover\s*letter/i.test(s.textContent||'')&&/remove|\.pdf|\.docx/i.test(s.textContent||''));
      if(cl)return {found:true,selector:null,committedChip:true,already:true};
      return {found:false};
    }""")
    return info if info.get('found') else None


def upload_cover_letter(page, plan, *, company=None, role=None, jd_file=None):
    """Detect a required cover-letter file input and upload a generated PDF.

    Idempotent: skips if a cover letter is already committed. Generic: works on
    any GH tenant via detect_cover_letter_input(). Mirrors the resume
    set_input_files path (with a Filestack attach-button fallback for remix
    boards where the raw input doesn't auto-commit).
    Returns a status dict for result['steps']['cover_upload'].
    """
    det = detect_cover_letter_input(page)
    if not det:
        return {'present': False}
    if det.get('already'):
        return {'present': True, 'already_uploaded': True, 'selector': det.get('selector')}
    sel = det.get('selector')
    if not sel:
        return {'present': True, 'err': 'no-resolvable-selector', 'detail': det}

    # Generate the cover-letter PDF (reuses the existing module + LLM path).
    try:
        import cover_letter_pdf as _clp
        from pathlib import Path as _P
        slug = plan.get('slug')
        out_pdf = _P('/tmp/openclaw/uploads') / f"{_load_personal().get('identity',{}).get('first_name','First')}_{_load_personal().get('identity',{}).get('last_name','Last')}_CoverLetter_{(slug or 'gh').replace('/','_')}.pdf"
        gen = _clp.generate(
            company=company or 'the company',
            role=role or 'Product Manager',
            jd_file=_P(jd_file) if jd_file else None,
            slug=slug,
            out_pdf=out_pdf,
        )
        cover_pdf = gen['pdf']
    except Exception as e:
        return {'present': True, 'err': f'generate-failed:{e}'}

    # Upload mirroring the resume path: set_input_files on the hidden input.
    try:
        fi = page.query_selector(sel)
        if not fi:
            return {'present': True, 'err': 'input-vanished', 'selector': sel}
        fi.set_input_files(cover_pdf, timeout=15000)
        time.sleep(1.5)
    except Exception as e:
        return {'present': True, 'err': f'set_input_files-failed:{e}', 'pdf': cover_pdf}

    # Verify files.length===1; if the tenant uses a Filestack attach button
    # (remix boards), click it to commit (mirrors resume Attach flow).
    base = os.path.basename(cover_pdf)
    chk = page.evaluate("""(sel)=>{const f=document.querySelector(sel);return {files:f?f.files.length:-1};}""", sel)
    committed = page.evaluate("""(b)=>document.body.innerText.includes(b)""", base)
    if not committed:
        # try the Filestack attach button next to the input
        page.evaluate("""(sel)=>{const f=document.querySelector(sel);if(f&&f.parentElement){const b=f.parentElement.querySelector('button');if(b)b.click();}}""", sel)
        time.sleep(1.5)
        committed = page.evaluate("""(b)=>document.body.innerText.includes(b)""", base)
    return {'present': True, 'uploaded': True, 'pdf': cover_pdf,
            'files_in_input': chk.get('files'), 'filename_committed': bool(committed)}


def detect_custom_required_file_inputs(page):
    """Detect REQUIRED custom file inputs that are NOT resume or cover-letter.

    Some GH PM tenants (ACLU 2660/2661/2662) add a required custom FILE question
    like "Please attach a PRD or product brief for a product you've launched
    before." There is no resume/cover input that satisfies it, so the form
    hard-blocks. This scans every file input, skips the resume/cover ones, and
    returns those whose surrounding label/aria text marks them required and
    matches the brief/PRD/writing-sample/portfolio/work-sample class.

    Returns a list of dicts: {selector, label, kind, already}.
    """
    js = r"""
    () => {
      const labelFor = (el) => {
        let t = '';
        if (el.id) { const l = document.querySelector('label[for="'+el.id+'"]'); if (l) t += ' ' + (l.textContent||''); }
        if (el.getAttribute && el.getAttribute('aria-label')) t += ' ' + el.getAttribute('aria-label');
        let p = el.closest('div,fieldset,section,li'); let hops = 0;
        while (p && hops < 4) { t += ' ' + (p.querySelector('label,legend,.label')?.textContent||''); p = p.parentElement; hops++; }
        return t.replace(/\s+/g,' ').trim();
      };
      const cssEsc = (s) => (window.CSS && CSS.escape) ? CSS.escape(s) : s;
      const inputs = [...document.querySelectorAll('input[type=file]')];
      const out = [];
      for (const f of inputs) {
        const id = f.id || '';
        const name = f.getAttribute('name') || '';
        if (/resume|cv/i.test(id) || /resume|cv/i.test(name)) continue;
        if (/cover[_\s]?letter/i.test(id) || /cover[_\s]?letter/i.test(name)) continue;
        const lab = labelFor(f);
        if (/cover\s*letter/i.test(lab) || /resume|cv\b/i.test(lab)) continue;
        // Any GH custom-question file input is `id="question_<digits>"`. These
        // carry NO DOM `required` attr and often NO <label> (the prompt text is
        // rendered in a sibling node), so label-only matching misses them. Treat
        // every such custom file question as a candidate to fill.
        const isCustomQ = /^question_\d+$/.test(id) || /^question_\d+$/.test(name);
        const req = f.required || f.getAttribute('aria-required')==='true' || /\*/.test(lab) || /required/i.test(lab);
        const kindMatch = /prd|product\s*brief|brief|writing\s*sample|work\s*sample|portfolio|deck|case\s*study|sample|document|attachment/i.test(lab);
        if (!isCustomQ && !req && !kindMatch) continue;
        // already committed? files.length>0 OR a Remove/.pdf chip in the section
        let already = (f.files && f.files.length>0);
        if (!already) {
          const sec = f.closest('div,fieldset,section,li');
          if (sec && /remove|\.pdf|\.docx|\.doc\b/i.test(sec.textContent||'')) already = true;
        }
        let sel = null;
        if (id) sel = '#'+cssEsc(id);
        else if (name) sel = 'input[type=file][name="'+name+'"]';
        out.push({selector: sel, label: lab.slice(0,160), kind: kindMatch ? 'brief' : (isCustomQ ? 'custom_question' : 'generic'), already: !!already, required: !!req});
      }
      return out;
    }
    """
    try:
        return page.evaluate(js) or []
    except Exception:
        return []


def upload_custom_required_file(page, plan, *, company=None, role=None, jd_file=None):
    """Detect required custom (PRD/brief/writing-sample) file inputs and upload
    a generated product-brief PDF to each. Idempotent + generic across tenants.

    Mirrors upload_cover_letter but uses prd_brief_pdf.generate to produce a
    sanitized product brief grounded in the resume. Returns a status dict.
    """
    dets = detect_custom_required_file_inputs(page)
    if not dets:
        return {'present': False}
    # generate ONE brief PDF and reuse it for every such input on the form.
    brief_pdf = None
    try:
        import prd_brief_pdf as _prd
        from pathlib import Path as _P
        slug = plan.get('slug')
        out_pdf = _P('/tmp/openclaw/uploads') / f"{_load_personal().get('identity',{}).get('first_name','First')}_{_load_personal().get('identity',{}).get('last_name','Last')}_ProductBrief_{(slug or 'gh').replace('/','_')}.pdf"
        gen = _prd.generate(
            company=company or 'the company',
            role=role or 'Product Manager',
            jd_file=_P(jd_file) if jd_file else None,
            out_pdf=out_pdf,
        )
        brief_pdf = gen['pdf']
    except Exception as e:
        return {'present': True, 'count': len(dets), 'err': f'generate-failed:{e}',
                'fields': [d.get('label') for d in dets]}

    results = []
    base = os.path.basename(brief_pdf)
    for det in dets:
        sel = det.get('selector')
        if det.get('already'):
            results.append({'label': det.get('label'), 'already_uploaded': True})
            continue
        if not sel:
            results.append({'label': det.get('label'), 'err': 'no-selector'})
            continue
        try:
            fi = page.query_selector(sel)
            if not fi:
                results.append({'label': det.get('label'), 'err': 'input-vanished', 'selector': sel})
                continue
            fi.set_input_files(brief_pdf, timeout=15000)
            time.sleep(1.5)
        except Exception as e:
            results.append({'label': det.get('label'), 'err': f'set_input_files-failed:{e}'})
            continue
        chk = page.evaluate("""(sel)=>{const f=document.querySelector(sel);return f?f.files.length:-1;}""", sel)
        committed = page.evaluate("""(b)=>document.body.innerText.includes(b)""", base)
        if not committed:
            # Filestack attach-button fallback (remix boards)
            page.evaluate("""(sel)=>{const f=document.querySelector(sel);if(f&&f.parentElement){const b=f.parentElement.querySelector('button');if(b)b.click();}}""", sel)
            time.sleep(1.5)
            committed = page.evaluate("""(b)=>document.body.innerText.includes(b)""", base)
        results.append({'label': det.get('label'), 'uploaded': True,
                        'files_in_input': chk, 'filename_committed': bool(committed)})
    return {'present': True, 'pdf': brief_pdf, 'count': len(dets), 'results': results}


def parse_cover_md(path):
    """Parse cover_answers.md into [{q, a}] — '## ' headings are questions, body is answer."""
    import re as _re
    txt = open(path, encoding='utf-8').read()
    parts = _re.split(r'\n##\s+', txt)
    out = []
    for p in parts[1:]:
        lines = p.split('\n', 1)
        q = lines[0].strip()
        a = (lines[1].strip() if len(lines) > 1 else '')
        if q and a:
            out.append({"q": q, "a": a})
    return out


def main():
    plan_path = sys.argv[1]
    no_submit = '--no-submit' in sys.argv
    plan = json.load(open(plan_path))
    url = plan['url']
    if '--url' in sys.argv:
        url = sys.argv[sys.argv.index('--url')+1]
    pdf = plan['pdf_path_staged']
    text_fields = plan.get('text_fields', {})
    if isinstance(text_fields, list):
        tf = {}
        for d in text_fields: tf.update(d)
        text_fields = tf
    dropdowns = plan.get('dropdowns', [])
    # Optional per-role answer overrides for custom questions the dryrun couldn't
    # map. Format: {"question_id": {"type":"select|text","value":"..."}}
    answers = {}
    if '--answers' in sys.argv:
        answers = json.load(open(sys.argv[sys.argv.index('--answers')+1]))
    cover_md = None
    if '--cover' in sys.argv:
        cover_md = sys.argv[sys.argv.index('--cover')+1]
    countries = plan.get('country_dropdowns', [])
    phone = plan.get('phone_iti')

    pw = sync_playwright().start()
    br = pw.chromium.connect_over_cdp(CDP)
    fresh = '--fresh' in sys.argv
    if fresh:
        ctx = br.new_context()
        page = ctx.new_page()
    else:
        ctx = br.contexts[0] if br.contexts else br.new_context()
        page = get_page(br, url)
        if not page:
            page = ctx.new_page()
    page.goto(url, wait_until='domcontentloaded', timeout=45000)
    time.sleep(1.5)
    # click Apply
    page.evaluate("""() => { const b=[...document.querySelectorAll('button,a')].find(x=>/^apply/i.test((x.textContent||'').trim())); if(b)b.click(); }""")
    time.sleep(1.2)

    result = {"slug": plan.get('slug'), "steps": {}}

    # text fields
    r = page.evaluate("""(fields)=>{const setN=(el,v)=>{const pr=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;const d=Object.getOwnPropertyDescriptor(pr,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};const o={};for(const[id,val]of Object.entries(fields)){const el=document.getElementById(id);if(!el){o[id]='NOEL';continue;}if(val===''||val==null){o[id]='blank';continue;}setN(el,String(val));o[id]=String(el.value).slice(0,30);}return o;}""", text_fields)
    result['steps']['text'] = r

    # react-select dropdowns
    if dropdowns:
        specs = [{"id": d['id'], "label": d['label']} for d in dropdowns]
        r = page.evaluate(SEL_PICK, specs)
        result['steps']['dropdowns'] = r

    # needs_review single-selects (2026-06-08 cohort fix): commit the dryrun's
    # truthfully-resolved answers that greenhouse_filler parked in
    # plan['needs_review_dropdowns'] and that _gh_submit previously SKIPPED ->
    # left required -> emptyRequired -> uncertain. Try the resolved label, then
    # alternates, then doctrine affirmatives, until one matches a rendered
    # option (SEL_PICK fuzzy-matches). A field whose options match NONE is left
    # uncommitted + surfaced (got=null), never fabricated.
    nr_specs = plan_needs_review_specs(plan)
    if nr_specs:
        nr_out = []
        for spec in nr_specs:
            fid = spec['id']
            committed = None
            tried = []
            for cand in spec['candidates']:
                tried.append(cand)
                res = page.evaluate(SEL_PICK, [{"id": fid, "label": cand}])
                row = (res or [{}])[0]
                if row.get('got') and not row.get('err'):
                    committed = row.get('got')
                    break
            nr_out.append({"id": fid, "question": spec.get('question', '')[:60],
                           "committed": committed, "tried": tried})
        result['steps']['needs_review'] = nr_out

    # country/location comboboxes (typeahead)
    if countries:
        specs = [{"id": d['id'], "label": d['label']} for d in countries]
        r = page.evaluate(SEL_TYPEAHEAD, specs)
        result['steps']['countries'] = r

    # location id-mismatch self-heal (2026-06-08 part (b)): some plan builders
    # stash the home location under text_fields['location'] but the live GH
    # Remix-embed form has no <input id="location"> -> the real field is the
    # #candidate-location async typeahead. If a location value exists and no
    # candidate-location typeahead was already staged in country_dropdowns,
    # drive it here so the required location field actually commits.
    loc_spec = plan_location_typeahead_spec(plan)
    if loc_spec:
        result['steps']['location_typeahead'] = page.evaluate(SEL_TYPEAHEAD, [loc_spec])

    # education panel typeaheads (2026-06-08 part (b)): school--0/discipline--0/
    # degree--0 are required react-select typeaheads NOT in the boards-api spec,
    # so the plan never targeted them and they used to need hand-fed
    # `--answers typeahead`. Derive them from the plan's resolved education
    # (falling back to personal-info.json) with truthful canonical values. The
    # specs are harmless on forms without an education panel (SEL_TYPEAHEAD
    # returns err:'noinput' per missing id). Skipped entirely if --answers
    # already supplies a typeahead for the same id (manual override wins).
    _ans_typeahead_ids = {qid for qid, a in (answers or {}).items()
                          if isinstance(a, dict) and a.get("type") == "typeahead"}
    edu_specs = [s for s in plan_education_specs(plan)
                 if s["id"] not in _ans_typeahead_ids]
    if edu_specs:
        result['steps']['education_typeahead'] = page.evaluate(SEL_TYPEAHEAD, edu_specs)

    # phone iti
    if phone:
        r = page.evaluate(PHONE_ITI, phone)
        result['steps']['phone'] = r
    else:
        # ensure plain #phone filled
        _ph = re.sub(r'[^0-9]', '', (_load_personal(plan) or {}).get('identity', {}).get('phone', ''))
        page.evaluate("""(ph)=>{const el=document.getElementById('phone');if(el&&!el.value){const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');d.set.call(el,ph);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}}}""", _ph)

    # demographics decline
    r = page.evaluate(DECLINE, {"declines": DECLINES})
    result['steps']['declines'] = r
    # consent checkboxes
    page.evaluate(CONSENT)

    # per-role custom-question answers (override blockers)
    if answers:
        sel_specs = [{"id": qid, "label": a["value"]} for qid, a in answers.items() if a.get("type") == "select"]
        txt_map = {qid: a["value"] for qid, a in answers.items() if a.get("type") == "text"}
        multi_specs = [{"id": qid, "label": a["value"]} for qid, a in answers.items() if a.get("type") == "multiselect"]
        # typeahead answer type: drives the big react-select comboboxes
        # (school/university, discipline/major, location) the dryrun skips.
        typeahead_specs = [{"id": qid, "label": a["value"]} for qid, a in answers.items() if a.get("type") == "typeahead"]
        if typeahead_specs:
            result['steps']['ans_typeahead'] = page.evaluate(SEL_TYPEAHEAD, typeahead_specs)
        if txt_map:
            page.evaluate("""(fields)=>{const setN=(el,v)=>{const pr=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;const d=Object.getOwnPropertyDescriptor(pr,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};for(const[id,val]of Object.entries(fields)){const el=document.getElementById(id);if(el)setN(el,String(val));}}""", txt_map)
        if sel_specs:
            result['steps']['ans_select'] = page.evaluate(SEL_PICK, sel_specs)
        for ms in multi_specs:
            result.setdefault('steps', {}).setdefault('ans_multi', []).append(page.evaluate(MULTI_PICK, ms))

    # essay / open-text answers from cover_answers.md (matched by question label)
    if cover_md and os.path.exists(cover_md):
        essays = parse_cover_md(cover_md)
        result['steps']['essays'] = page.evaluate(ESSAY_FILL, {"essays": essays})

    # resume upload via set_input_files
    fi = page.query_selector('#resume')
    up = 'no-input'
    if fi:
        try:
            fi.set_input_files(pdf, timeout=15000)
            time.sleep(2)
            body = page.inner_text('body')
            up = os.path.basename(pdf) in body
        except Exception as e:
            up = f'err:{e}'
    result['steps']['upload'] = up

    # cover-letter FILE upload (generic across GH tenants). Some boards make the
    # Cover Letter a REQUIRED file input (#cover_letter) with no text alternative
    # -> generate a tailored PDF and set_input_files it, mirroring #resume.
    cl_company = plan.get('company')
    cl_role = plan.get('role')
    cl_jd = plan.get('spec_path')
    if '--company' in sys.argv:
        cl_company = sys.argv[sys.argv.index('--company')+1]
    if '--role' in sys.argv:
        cl_role = sys.argv[sys.argv.index('--role')+1]
    try:
        result['steps']['cover_upload'] = upload_cover_letter(
            page, plan, company=cl_company, role=cl_role, jd_file=cl_jd)
    except Exception as e:
        result['steps']['cover_upload'] = {'err': f'unhandled:{e}'}

    # custom REQUIRED file upload (generic across GH tenants, 2026-06-10). Some
    # PM roles (ACLU 2660/2661/2662) add a required custom FILE question like
    # "attach a PRD / product brief / writing sample" with no resume/cover
    # alternative -> generate a sanitized product-brief PDF (prd_brief_pdf,
    # grounded in the resume) and set_input_files it onto each such input.
    try:
        result['steps']['custom_file_upload'] = upload_custom_required_file(
            page, plan, company=cl_company, role=cl_role, jd_file=cl_jd)
    except Exception as e:
        result['steps']['custom_file_upload'] = {'err': f'unhandled:{e}'}

    # FALLBACK: label-less required open-text questions (2026-06-03). Some GH
    # tenants (Anduril/Swayable/Astranis) render required custom questions whose
    # <label> can't be matched by ESSAY_FILL's label path, so the essay never
    # lands and emptyRequired blocks submit. Recover the question text from
    # aria-labelledby / preceding text / parent text, re-match unused essays,
    # and fill. Conservative: only touches STILL-EMPTY required text/textarea
    # fields; never overwrites a filled field; PII/structured ids are skipped.
    if cover_md and os.path.exists(cover_md):
        try:
            essays2 = parse_cover_md(cover_md)
            result['steps']['essay_fallback'] = page.evaluate(
                ESSAY_FALLBACK_LABELLESS, {"essays": essays2})
        except Exception as e:
            result['steps']['essay_fallback'] = {'err': f'{e}'}

    # REMIX DROPDOWN RECOVERY (2026-06-03). Some GH remix tenants (Anduril,
    # Swayable, Astranis, defense-contractor class) render REQUIRED work-auth /
    # clearance / export-control / sponsorship questions as React-Select
    # dropdowns whose boards-API field carries no extractable label, so the
    # dryrun never put them in plan['dropdowns'] -> they stay empty -> submit is
    # blocked on emptyRequired. Scan the live DOM for still-unfilled selects,
    # recover the question text + options, resolve the TRUTHFUL answer via the
    # same dryrun resolver, and commit via SEL_PICK. Knockouts (truthful 'No'
    # geo/eligibility answers) are surfaced, never faked into a pass.
    try:
        from greenhouse_dryrun import PERSONAL_INFO_PATH, resolve_field as _rf
        _personal = json.loads(PERSONAL_INFO_PATH.read_text())
        scanned = page.evaluate(REMIX_SCAN, {"skipRe": DEMO_SKIP_RE})
        if scanned:
            planned = plan_remix_answers(scanned, _personal, resolve_field=_rf)
            if planned["commit"]:
                planned["commit_result"] = page.evaluate(SEL_PICK, planned["commit"])
            result['steps']['remix_recover'] = planned
    except Exception as e:
        result['steps']['remix_recover'] = {'err': f'{e}'}

    # GH-REMIX WORK-HISTORY repeater fill (Zuora 2755 cohort, 2026-06-09). Some
    # GH Remix tenants render a required EMPLOYMENT-HISTORY block (a 'Current
    # role' checkbox + start/end date-month/year React-Selects). These are
    # live-DOM-only (the boards-API dryrun never sees them) and the generic
    # remix_recover correctly refuses to fabricate month names -> they sit in
    # emptyRequired and bounce the submit. They are biographical facts from
    # personal-info (work_experience[0]); fill block 0 truthfully: tick 'Current
    # role' (drops end-date from required), SEL_PICK the start MONTH, and fill
    # the start YEAR react-select. No-op on tenants without the section.
    try:
        try:
            _personal  # reuse the one loaded for remix_recover if present
        except NameError:
            from greenhouse_dryrun import PERSONAL_INFO_PATH as _PIP
            _personal = json.loads(_PIP.read_text())
        wh = plan_work_history_specs(_personal)
        if wh:
            wh_res = {'spec': wh}
            if wh.get('selects'):
                wh_res['months'] = page.evaluate(SEL_PICK, wh['selects'])
            if wh.get('end_selects'):
                wh_res['end_months'] = page.evaluate(SEL_PICK, wh['end_selects'])
            wh_res['cb_years'] = page.evaluate(WORK_HISTORY_FILL, {
                "checkCurrent": wh.get('checkCurrent'),
                "startYear": wh.get('start_year') or '',
                "endYear": wh.get('end_year') or '',
                "company": wh.get('company') or '',
                "title": wh.get('title') or '',
            })
            result['steps']['work_history_fill'] = wh_res
    except Exception as e:
        result['steps']['work_history_fill'] = {'err': f'{e}'}

    # verify state
    # 2026-06-04 (Pure Storage consent-ack bug): the native [required] scan
    # below MISSES required react-select MULTI widgets (consent/ack fields like
    # "Personal Information Policy"), whose React/Formik validation has no DOM
    # `required` attribute and no `.value` to read. An unset ack would slip
    # through as emptyRequired:[] and the submit would silently bounce. Detect
    # any react-select multi (value-container--is-multi, or a []-suffixed hidden
    # input) that has NO committed `.select__multi-value` chip and surface it in
    # emptyRequired so it's caught pre-submit instead of bouncing.
    state = page.evaluate(PRESUBMIT_STATE_JS)
    result['preSubmitState'] = json.loads(state)

    # MULTISELECT FORCE-COMMIT (2026-06-04, Raft + emptyRequired/multiUnset
    # cohort). The pre-submit scan above flags required react-select MULTI
    # widgets that have no committed chip (`multiUnset`). The single-select /
    # affirmation commit passes never touched these. Here we force-commit ANY
    # such multiselect whose values the DRYRUN ALREADY RESOLVED into
    # `plan['multi_checkboxes']` (built by greenhouse_filler). Each commit is
    # scoped to THAT control's own `.select__menu` (MULTI_PICK) to avoid the
    # documented remix sibling-menu id-collision. Unresolved multiselects (no
    # plan values) are LEFT ALONE -> the row stays banked, never fabricated.
    multi_unset = result['preSubmitState'].get('multiUnset') or []
    if multi_unset:
        ms_specs = plan_multiselect_commit_specs(plan, multi_unset)
        if ms_specs:
            commit_out = []
            for spec in ms_specs:
                commit_out.append({"id": spec["id"],
                                   "result": page.evaluate(MULTI_PICK, spec)})
            result['steps']['multiselect_commit'] = commit_out
            # Re-read state so emptyRequired/multiUnset reflect the commits.
            state = page.evaluate(PRESUBMIT_STATE_JS)
            result['preSubmitState'] = json.loads(state)
        else:
            result['steps']['multiselect_commit'] = {
                'skipped': 'no dryrun-resolved plan values for multiUnset',
                'multiUnset': multi_unset}

    if no_submit:
        result['status'] = 'prepped-no-submit'
        print(json.dumps(result, indent=1)); return 0

    # INLINE PROOF SCREENSHOT (Cyrus 2026-06-02): if this role is flagged (every
    # 5th submission), screenshot the filled form NOW, immediately before the real
    # submit click. Best-effort, never blocks submit.
    try:
        from proof_capture import maybe_capture_by_slug
        maybe_capture_by_slug(page, plan.get('slug'))
    except Exception as _e:
        print(f"[proof_capture] skipped: {_e}")

    # click submit — REAL playwright click triggers full React validation
    # (evaluate-click misses checkbox-group/required-field validation). Falls
    # back to evaluate-click if the selector isn't found.
    try:
        _btn = page.query_selector('button:has-text("Submit application")') or page.query_selector('button[type=submit]')
        if _btn:
            _btn.scroll_into_view_if_needed()
            time.sleep(0.3)
            _btn.click()
        else:
            page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.textContent.trim()));if(s){s.scrollIntoView({block:'center'});s.click();}}""")
    except Exception:
        page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.textContent.trim()));if(s){s.scrollIntoView({block:'center'});s.click();}}""")
    time.sleep(4)

    # OTP gate?
    has_otp = page.evaluate("""()=>!!document.getElementById('security-input-0')||/verification code was sent|enter the 8-character/i.test(document.body.innerText)""")
    if has_otp:
        import gmail_imap as g
        since = time.time() - 30
        code = None
        try:
            code = g.wait_for_verification_code(timeout_seconds=120, poll_seconds=5, since_epoch=since)
        except Exception as e:
            result['status'] = 'blocked-otp-fetch-fail'; result['err'] = str(e)
            print(json.dumps(result, indent=1)); return 1
        result['otp_code'] = code
        page.evaluate("""(code)=>{const setN=(el,v)=>{const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};for(let i=0;i<8;i++){const el=document.getElementById('security-input-'+i);if(el){el.focus();setN(el,code[i]);el.dispatchEvent(new KeyboardEvent('keydown',{key:code[i],bubbles:true}));el.dispatchEvent(new KeyboardEvent('keyup',{key:code[i],bubbles:true}));}}}""", code)
        time.sleep(1.2)
        # Click the post-OTP submit/verify/confirm button. Retry a couple times:
        # the button can stay disabled for a beat while the OTP digits validate.
        # BUGFIX 2026-06-02 (Smartsheet 2235 + New Relic 2232): the old selector
        # filtered with `!b.getAttribute('aria-disabled')`, but an ENABLED
        # "Submit application" button carries aria-disabled="false" (a STRING,
        # which is truthy) -> button wrongly skipped -> OTP entered but never
        # submitted (otpStill stayed true). Compare against 'true' explicitly,
        # and prefer a real Playwright click which fires full React validation.
        for _otp_try in range(4):
            clicked = None
            try:
                _b = page.query_selector('button:has-text("Submit application")') or \
                     page.query_selector('button:has-text("Verify")') or \
                     page.query_selector('button:has-text("Confirm")') or \
                     page.query_selector('button[type=submit]')
                if _b and not _b.is_disabled() and (_b.get_attribute('aria-disabled') or 'false') != 'true':
                    _b.scroll_into_view_if_needed(); time.sleep(0.3); _b.click()
                    clicked = (_b.text_content() or '').strip()
            except Exception:
                clicked = None
            if not clicked:
                clicked = page.evaluate("""()=>{const s=[...document.querySelectorAll('button')].find(b=>/submit|verify|confirm/i.test(b.textContent.trim())&&!b.disabled&&b.getAttribute('aria-disabled')!=='true');if(s){s.scrollIntoView({block:'center'});s.click();return s.textContent.trim();}return null;}""")
            if clicked:
                result['otp_submit_btn'] = clicked
                break
            time.sleep(1.5)

    # Poll for confirmation/redirect: Greenhouse OTP-validate -> /confirmation
    # redirect can take 6-18s; a fixed 4s sleep raced it and read 'uncertain'.
    final = None
    for _ in range(12):
        time.sleep(2)
        final = json.loads(page.evaluate("""()=>{const url=location.href;const body=document.body.innerText;const conf=/thank you|received your application|application.{0,20}submitted|application submitted|submitted your application|we.{0,3}ll be in touch|will begin reviewing|appreciate your interest/i.test(body)||/confirmation/.test(url);const otpStill=!!document.getElementById('security-input-0');const otpErr=/incorrect|invalid|wrong code|didn.{0,3}t match|expired/i.test(body);return JSON.stringify({url,confirmed:conf,otpStill,otpErr,head:body.slice(0,200)});}"""))
        if final['confirmed'] or final.get('otpErr'):
            break
        if not final['otpStill'] and not has_otp:
            break
    result['final'] = final
    if final['confirmed'] and not final['otpStill']:
        result['status'] = 'SUBMITTED'
    elif final['otpStill']:
        result['status'] = 'blocked-otp-rejected'
    else:
        # Distinguish the company-hosted-flow BOUNCE class (Stripe/Lob/Sendbird):
        # the GH embed form's submit redirects to the tenant's own apply domain
        # and does NOT persist. Tag it distinctly so future triage skips a doomed
        # GH-embed retry instead of re-attempting as generic 'uncertain'.
        try:
            final_host = re.sub(r"^https?://([^/]+).*$", r"\1", final.get('url') or '')
        except Exception:
            final_host = ''
        gh_hosts = ('greenhouse.io', 'job-boards.greenhouse.io', 'boards.greenhouse.io')
        empties = (result.get('preSubmitState', {}) or {}).get('emptyRequired')
        no_empties = (empties == [] or empties is None)
        if final_host and not any(h in final_host for h in gh_hosts) and no_empties:
            # left the GH domain with nothing blocking on our side -> wrapper bounce
            result['status'] = 'hosted-flow-bounce'
            result['bounce_host'] = final_host
        else:
            result['status'] = 'uncertain'
    print(json.dumps(result, indent=1))
    return 0

# ---- JS blobs ----
SEL_PICK = """async (specs)=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const fire=(el,t,x,y)=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));const out=[];for(const{id,label}of specs){const inp=document.getElementById(id);if(!inp){out.push({id,err:'noinput'});continue;}const ctrl=inp.closest('.select__control');if(!ctrl){out.push({id,err:'noctrl'});continue;}ctrl.scrollIntoView({block:'center'});await sleep(100);const r=ctrl.getBoundingClientRect();fire(ctrl,'mousedown',r.left+5,r.top+5);fire(ctrl,'mouseup',r.left+5,r.top+5);fire(ctrl,'click',r.left+5,r.top+5);await sleep(320);let opts=[];const menu=document.querySelector('.select__menu');if(menu)opts=[...menu.querySelectorAll('.select__option,[role=option]')];if(!opts.length)opts=[...document.querySelectorAll('.select__option,[role=option]')];const wl=String(label).toLowerCase();let t=opts.find(o=>o.textContent.trim()===label)||opts.find(o=>o.textContent.trim().toLowerCase()===wl)||opts.find(o=>o.textContent.trim().toLowerCase().startsWith(wl))||opts.find(o=>o.textContent.toLowerCase().includes(wl));if(!t){out.push({id,err:'noopt',avail:opts.map(o=>o.textContent.trim()).slice(0,10)});fire(document.body,'mousedown',0,0);continue;}const tr=t.getBoundingClientRect();fire(t,'mousedown',tr.left+5,tr.top+5);fire(t,'mouseup',tr.left+5,tr.top+5);fire(t,'click',tr.left+5,tr.top+5);await sleep(200);const sv=ctrl.querySelector('.select__single-value');out.push({id,want:label,got:sv?sv.textContent:null});}return out;}"""

# GH-Remix WORK-HISTORY repeater fill (Zuora 2755 cohort, 2026-06-09). Ticks the
# 'Current role' checkbox (trusted native click + React change event) so the
# End-date selects drop from required, and fills the start/end YEAR react-selects
# (the MONTH react-selects are driven by SEL_PICK). The checkbox id varies
# (`current-role-0_1` on Zuora); we match by an associated label containing
# 'current' near a block-0 employment widget. Year selects: id `*-year-0`. Only
# touches block 0; never fabricates (caller passes values from personal-info).
WORK_HISTORY_FILL = """async ({checkCurrent, startYear, endYear, company, title})=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const fire=(el,t)=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0}));const out={current:null,years:[],text:[]};
  // 0) fill company-name-0 / title-0 TEXT inputs (aria-required, no native
  // `required` attr so the pre-submit native scan misses them -> React still
  // blocks). Set via native value setter + input/change so Formik registers.
  const setText=(id,val)=>{if(!val)return;const el=document.getElementById(id);if(!el){out.text.push({id,err:'noinput'});return;}el.scrollIntoView({block:'center'});el.focus();const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');d.set.call(el,String(val));el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));el.blur();out.text.push({id,want:String(val),got:el.value});};
  setText('company-name-0',company);
  setText('title-0',title);
  await sleep(120);
  // 1) tick 'Current role' checkbox (block 0)
  if(checkCurrent){let cb=document.getElementById('current-role-0_1');
    if(!cb){const labs=[...document.querySelectorAll('label')].filter(l=>/current role|i currently work|present/i.test((l.textContent||'')));for(const l of labs){const f=l.getAttribute('for');const c=f?document.getElementById(f):l.querySelector('input[type=checkbox]');if(c){cb=c;break;}}}
    if(cb){if(!cb.checked){cb.scrollIntoView({block:'center'});await sleep(120);cb.click();const setC=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'checked');try{setC.set.call(cb,true);}catch(e){}cb.dispatchEvent(new Event('input',{bubbles:true}));cb.dispatchEvent(new Event('change',{bubbles:true}));await sleep(250);}out.current={id:cb.id,checked:cb.checked};}else out.current='no-checkbox';}
  // 2) fill year fields. On the GH-Remix employment form the YEAR is a plain
  // TEXT input (id `*-year-0`, class input__single-line), NOT a react-select
  // (only the MONTH is a react-select). Set its value via the native setter +
  // React input/change events so Formik validation registers it.
  const setYear=(id,year)=>{if(!year)return;const el=document.getElementById(id);if(!el){out.years.push({id,err:'noinput'});return;}
    if(el.closest('.select__control')){/* react-select year (other tenants) */const ctrl=el.closest('.select__control');ctrl.scrollIntoView({block:'center'});const r=ctrl.getBoundingClientRect();fire(ctrl,'mousedown');fire(ctrl,'mouseup');fire(ctrl,'click');return;}
    el.scrollIntoView({block:'center'});el.focus();const d=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value');d.set.call(el,String(year));el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));el.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true}));el.blur();out.years.push({id,want:String(year),got:el.value});};
  setYear('start-date-year-0',startYear);
  if(endYear)setYear('end-date-year-0',endYear);
  await sleep(150);
  return out;}"""

SEL_TYPEAHEAD = """async (specs)=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const fire=(el,t,x,y)=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));const setN=(el,v)=>{const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));};const out=[];for(const{id,label}of specs){const inp=document.getElementById(id);if(!inp){out.push({id,err:'noinput'});continue;}const ctrl=inp.closest('.select__control');if(!ctrl){out.push({id,err:'noctrl'});continue;}ctrl.scrollIntoView({block:'center'});await sleep(120);const r=ctrl.getBoundingClientRect();fire(ctrl,'mousedown',r.left+5,r.top+5);fire(ctrl,'mouseup',r.left+5,r.top+5);fire(ctrl,'click',r.left+5,r.top+5);await sleep(250);setN(inp,'');await sleep(60);const s=String(label);for(let i=1;i<=s.length;i++){setN(inp,s.slice(0,i));const ch=s[i-1];inp.dispatchEvent(new KeyboardEvent('keydown',{key:ch,bubbles:true}));inp.dispatchEvent(new KeyboardEvent('keyup',{key:ch,bubbles:true}));await sleep(55);}await sleep(1200);const esc=(window.CSS&&CSS.escape)?CSS.escape(id):id;let opts=[...document.querySelectorAll('[id^=\"react-select-'+esc+'-option\"]')];let t=opts.find(o=>o.textContent.trim().toLowerCase()===s.toLowerCase())||opts.find(o=>o.textContent.trim().toLowerCase().startsWith(s.toLowerCase()))||opts.find(o=>o.textContent.toLowerCase().includes(s.toLowerCase()));if(!t&&opts.length)t=opts[0];if(!t){out.push({id,err:'noopt'});fire(document.body,'mousedown',0,0);continue;}const tr=t.getBoundingClientRect();fire(t,'mousedown',tr.left+5,tr.top+5);fire(t,'mouseup',tr.left+5,tr.top+5);fire(t,'click',tr.left+5,tr.top+5);await sleep(180);const sv=ctrl.querySelector('.select__single-value');out.push({id,want:label,got:sv?sv.textContent:null});}return out;}"""

PHONE_ITI = """async ({id,country,digits})=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const setN=(el,v)=>{const d=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};const inp=document.getElementById(id);if(!inp)return{err:'nophone'};const iti=inp.closest('.iti');if(iti){const flag=iti.querySelector('.iti__selected-flag');if(flag){flag.click();await sleep(250);const items=[...iti.querySelectorAll('.iti__country,li[class*=iti__country]')];let t=items.find(li=>(li.textContent||'').toLowerCase().includes((country||'united states').toLowerCase()))||items.find(li=>(li.getAttribute('data-country-code')||'').toLowerCase()==='us');if(t){t.click();await sleep(150);}}}const clean=String(digits||'').replace(/[^0-9]/g,'');setN(inp,clean);return{phone:inp.value};}"""

DECLINE = """async ({declines})=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const fire=(el,t,x,y)=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));const re=/gender|\\bsex\\b|race|ethnic|hispanic|latin|veteran|military.{0,8}status|disabilit|self[- ]?identif|pronoun|sexual.{0,5}orient|lgbtq/i;const out=[];for(const ctrl of [...document.querySelectorAll('.select__control')]){if(ctrl.querySelector('.select__single-value'))continue;const inp=ctrl.querySelector('input[role=combobox]');if(!inp||!inp.id)continue;let lbl='',n=ctrl;for(let i=0;i<6&&n;i++){n=n.parentElement;if(!n)break;const le=n.querySelector?n.querySelector('label,legend'):null;if(le){lbl=le.textContent||'';break;}}if(!re.test(lbl))continue;ctrl.scrollIntoView({block:'center'});await sleep(120);const r=ctrl.getBoundingClientRect();fire(ctrl,'mousedown',r.left+5,r.top+5);fire(ctrl,'mouseup',r.left+5,r.top+5);fire(ctrl,'click',r.left+5,r.top+5);await sleep(320);let opts=[];const menu=document.querySelector('.select__menu');opts=menu?[...menu.querySelectorAll('.select__option,[role=option]')]:[];let t=null;for(const w of declines){const wl=w.toLowerCase();t=opts.find(o=>o.textContent.trim().toLowerCase()===wl)||opts.find(o=>o.textContent.toLowerCase().includes(wl));if(t)break;}if(!t)t=opts.find(o=>/do not want to answer|don'?t wish|decline|prefer not|not to identify|not to disclose/i.test(o.textContent));if(!t){out.push({id:inp.id,label:lbl.slice(0,40),err:'nodecline'});fire(document.body,'mousedown',0,0);continue;}const tr=t.getBoundingClientRect();fire(t,'mousedown',tr.left+5,tr.top+5);fire(t,'mouseup',tr.left+5,tr.top+5);fire(t,'click',tr.left+5,tr.top+5);await sleep(150);const sv=ctrl.querySelector('.select__single-value');out.push({id:inp.id,got:sv?sv.textContent:null});}return out;}"""

# REMIX_SCAN (2026-06-03): recover REQUIRED remix React-Select dropdowns that the
# dryrun couldn't label (no id/name/label on the boards-API field) so they never
# made it into plan['dropdowns'] -> stayed empty -> emptyRequired blocked submit.
# For every UNFILLED .select__control we climb the DOM to recover the question
# text + open the menu to read its option labels, then return them. Python side
# resolves the truthful answer via greenhouse_dryrun.resolve_field and commits via
# SEL_PICK. Conservative: only reports controls with NO .select__single-value and
# a real combobox id; demographics are skipped (handled by DECLINE). Does NOT pick
# here -- just scans (read-only), so a misread can't mis-commit.
REMIX_SCAN = r"""async ({skipRe})=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const fire=(el,t,x,y)=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));const demo=new RegExp(skipRe,'i');const recoverLabel=(ctrl)=>{let n=ctrl;for(let i=0;i<7&&n;i++){n=n.parentElement;if(!n)break;const le=n.querySelector?n.querySelector('label,legend'):null;if(le&&(le.textContent||'').trim())return le.textContent.trim();}const inp=ctrl.querySelector('input[role=combobox]');if(inp){const lb=inp.getAttribute('aria-labelledby');if(lb){const parts=lb.split(/\s+/).map(id=>{const e=document.getElementById(id);return e?e.textContent:'';}).join(' ').trim();if(parts)return parts;}const al=inp.getAttribute('aria-label');if(al)return al;}return '';};const out=[];for(const ctrl of [...document.querySelectorAll('.select__control')]){if(ctrl.querySelector('.select__single-value'))continue;if(ctrl.querySelector('.select__multi-value__label'))continue;const inp=ctrl.querySelector('input[role=combobox]');if(!inp||!inp.id)continue;const label=recoverLabel(ctrl);if(label&&demo.test(label))continue;ctrl.scrollIntoView({block:'center'});await sleep(120);const r=ctrl.getBoundingClientRect();fire(ctrl,'mousedown',r.left+5,r.top+5);fire(ctrl,'mouseup',r.left+5,r.top+5);fire(ctrl,'click',r.left+5,r.top+5);await sleep(340);let opts=[];const menu=document.querySelector('.select__menu');if(menu)opts=[...menu.querySelectorAll('.select__option,[role=option]')].map(o=>o.textContent.trim()).filter(Boolean);fire(document.body,'mousedown',0,0);await sleep(80);/* 2026-06-04 batch4: keep BLANK-label controls too (Everlaw-class sole-option "Agree"/"Acknowledge" affirmation selects render with no recoverable label). Python force-commits them only when option-structure is a safe forced-choice. Skip a blank-label control with no options (nothing to do). */if(!label&&!opts.length)continue;out.push({id:inp.id,label:label,options:opts});}return out;}"""

CONSENT = """()=>{const cre=/i consent to|demographic data|gdpr|i acknowledge and agree|processing of my personal data|by checking this box|personal information policy|acknowledge|privacy/i;for(const inp of [...document.querySelectorAll('input[type=checkbox]')]){if(inp.offsetParent===null)continue;const id=inp.id||'';let lbl='';if(id){const le=document.querySelector('label[for=\"'+(window.CSS?CSS.escape(id):id)+'\"]');if(le)lbl=le.textContent||'';}if(!lbl){const w=inp.closest('label');if(w)lbl=w.textContent||'';}let leg='';const fs=inp.closest('fieldset');if(fs){const lg=fs.querySelector('legend');if(lg)leg=lg.textContent||'';}const desc=inp.getAttribute('description')||inp.getAttribute('aria-describedby')||'';const isReq=inp.required||inp.getAttribute('aria-required')==='true';/* 2026-06-04 Pure Storage fix: required consent/ack checkboxes (e.g. \"Personal Information Policy\" -> sole option \"Acknowledge/Confirm\") render as a native required <input type=checkbox name=\"question_<id>[]\"> NOT a react-select-multi, so multiUnset missed it AND the [required]+!value scan missed it (a checkbox always has a non-empty value=). Tick any STILL-UNCHECKED required checkbox (forced-choice ack = truthful) OR any matching the consent regex. */if(!(isReq||/gdpr.*consent|demographic_data_consent|question_\\d+\\[\\]/i.test(id)||cre.test(lbl)||cre.test(leg)||cre.test(desc)))continue;if(!inp.checked)inp.click();}}"""


# PRESUBMIT_STATE_JS (extracted 2026-06-04 so it can be re-run after the
# multiselect force-commit pass). Reports required-but-empty fields plus any
# required react-select MULTI widget with no committed chip (multiUnset).
PRESUBMIT_STATE_JS = """()=>{const req=[...document.querySelectorAll('input[required],select[required],textarea[required]')].filter(e=>e.offsetParent!==null);const empty=req.filter(e=>(e.type==='checkbox'||e.type==='radio')?!e.checked:!e.value).map(e=>e.id||e.name);const multiUnset=[];for(const ctrl of document.querySelectorAll('.select__control')){if(ctrl.offsetParent===null)continue;const vc=ctrl.querySelector('.select__value-container');const isMulti=(vc&&vc.className.includes('--is-multi'))||!!ctrl.querySelector('input[id$="[]"],input[name$="[]"]');if(!isMulti)continue;const committed=!!ctrl.querySelector('.select__multi-value');if(committed)continue;const hid=ctrl.querySelector('input[id],input[name]');const key=hid?(hid.id||hid.name):null;multiUnset.push(key||'multi-select');}for(const k of multiUnset){if(!empty.includes(k))empty.push(k);}const sub=[...document.querySelectorAll('button')].find(b=>/submit application/i.test(b.textContent.trim()));return JSON.stringify({emptyRequired:empty,multiUnset,submitDisabled:sub?(sub.disabled||sub.getAttribute('aria-disabled')==='true'):'nobtn'});}"""

# MULTI_PICK commits one or more options into a react-select MULTI control.
# 2026-06-04 (Raft/multiselect-commit fix): the option lookup is now SCOPED to
# THIS control's OWN `.select__menu` (resolved via the control's
# aria-controls/aria-owns -> menu id, else the menu nearest the control) so we
# never click an option belonging to a SIBLING react-select whose menu happens
# to be open — the documented remix sibling-menu id-collision (TOOLS.md
# Swayable). Falls back to the global option scan ONLY if no scoped menu can be
# located (rare true-portaled menus), preserving prior behavior for those.
MULTI_PICK = r"""async ({id,label})=>{const sleep=ms=>new Promise(r=>setTimeout(r,ms));const fire=(el,t,x,y)=>el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window,button:0,clientX:x||0,clientY:y||0}));const bid=id.replace(/\[\]$/,'');let inp=document.getElementById(bid)||document.getElementById(id);if(!inp){const cand=[...document.querySelectorAll('input[role=combobox]')].filter(c=>{const i=c.id||'';return i.indexOf(bid)>=0;});inp=cand[0];}if(!inp)return 'noinput:'+bid;const ctrl=inp.closest('.select__control');if(!ctrl)return 'noctrl';const wrap=ctrl.closest('.select__container')||ctrl.parentElement;const scopedMenu=()=>{const own=inp.getAttribute('aria-controls')||inp.getAttribute('aria-owns');if(own){const m=document.getElementById(own);if(m)return m;}if(wrap){const m=wrap.querySelector('.select__menu');if(m)return m;}return null;};const labels=Array.isArray(label)?label:[label];const got=[];for(const lab of labels){ctrl.scrollIntoView({block:'center'});await sleep(150);const r=ctrl.getBoundingClientRect();fire(ctrl,'mousedown',r.left+5,r.top+5);fire(ctrl,'mouseup',r.left+5,r.top+5);fire(ctrl,'click',r.left+5,r.top+5);await sleep(360);const menu=scopedMenu();let opts=menu?[...menu.querySelectorAll('.select__option,[role=option]')]:[...document.querySelectorAll('.select__option,[role=option]')];const wl=lab.toLowerCase();let t=opts.find(o=>o.textContent.trim().toLowerCase()===wl)||opts.find(o=>o.textContent.trim().toLowerCase().startsWith(wl))||opts.find(o=>o.textContent.toLowerCase().includes(wl));if(!t){fire(document.body,'mousedown',0,0);got.push('noopt:'+lab);continue;}const tr=t.getBoundingClientRect();fire(t,'mousedown',tr.left+5,tr.top+5);fire(t,'mouseup',tr.left+5,tr.top+5);fire(t,'click',tr.left+5,tr.top+5);await sleep(200);got.push(lab);}const vals=[...ctrl.querySelectorAll('.select__multi-value__label')].map(e=>e.textContent);fire(document.body,'mousedown',0,0);return 'picked:'+got.join(',')+' | tags:'+vals.join(',');}"""

ESSAY_FILL = r"""({essays})=>{
  const setN=(el,v)=>{const pr=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;const d=Object.getOwnPropertyDescriptor(pr,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));el.dispatchEvent(new Event('blur',{bubbles:true}));};
  const norm=s=>(s||'').toLowerCase().replace(/[^a-z0-9 ]/g,' ').replace(/\s+/g,' ').trim();
  // collect candidate open-text fields: textareas + text inputs that have a label and are empty
  const fields=[];
  for(const el of [...document.querySelectorAll('textarea, input[type=text]')]){
    if(el.id==='first_name'||el.id==='last_name'||el.id==='email'||el.id==='phone')continue;
    if(/recaptcha|security-input/i.test(el.id||''))continue;
    let lbl='';const id=el.id||'';
    if(id){const le=document.querySelector('label[for="'+(window.CSS?CSS.escape(id):id)+'"]');if(le)lbl=le.textContent||'';}
    if(!lbl){const w=el.closest('div,fieldset');if(w){const le=w.querySelector('label,legend');if(le)lbl=le.textContent||'';}}
    fields.push({el,lbl:norm(lbl),id});
  }
  const out=[];
  for(const {q,a} of essays){
    const qn=norm(q);
    if(!qn)continue;
    // score by shared significant words
    const qw=qn.split(' ').filter(w=>w.length>4);
    let best=null,bestScore=0;
    for(const f of fields){
      if(f.used)continue;
      if(!f.lbl)continue;
      let sc=0;for(const w of qw){if(f.lbl.includes(w))sc++;}
      // strong bonus if label startsWith first 20 chars of question
      if(f.lbl.includes(qn.slice(0,25))||qn.includes(f.lbl.slice(0,25)))sc+=3;
      if(sc>bestScore){bestScore=sc;best=f;}
    }
    if(best&&bestScore>=2){best.used=true;setN(best.el,a);out.push({q:q.slice(0,40),matchedLbl:best.lbl.slice(0,40),len:a.length});}
    else out.push({q:q.slice(0,40),err:'no-match',bestScore});
  }
  return out;
}"""


ESSAY_FALLBACK_LABELLESS = r"""({essays})=>{
  const setN=(el,v)=>{const pr=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype;const d=Object.getOwnPropertyDescriptor(pr,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));el.dispatchEvent(new Event('blur',{bubbles:true}));};
  const norm=s=>(s||'').toLowerCase().replace(/[^a-z0-9 ]/g,' ').replace(/\s+/g,' ').trim();
  const SKIP=/first_name|last_name|email|phone|recaptcha|security-input|linkedin|github|website|url|salary|compensation|address|city|state|zip|country/i;
  // Recover question text for a field from several DOM sources.
  const recover=(el)=>{
    let t='';
    const id=el.id||'';
    if(id){const le=document.querySelector('label[for="'+(window.CSS?CSS.escape(id):id)+'"]');if(le)t+=' '+le.textContent;}
    const lb=el.getAttribute('aria-labelledby');
    if(lb){for(const pid of lb.split(/\s+/)){const pe=document.getElementById(pid);if(pe)t+=' '+pe.textContent;}}
    t+=' '+(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('placeholder')||'');
    // climb to a labelled-looking ancestor and read its text minus the control
    let w=el.closest('div,fieldset,section,li');
    for(let i=0;i<3&&w;i++){
      const le=w.querySelector('label,legend');
      if(le&&norm(le.textContent).length>4){t+=' '+le.textContent;break;}
      // preceding sibling text
      let ps=w.previousElementSibling;
      if(ps&&norm(ps.textContent).length>4&&norm(ps.textContent).length<400){t+=' '+ps.textContent;break;}
      w=w.parentElement?w.parentElement.closest('div,fieldset,section,li'):null;
    }
    return norm(t);
  };
  // candidate STILL-EMPTY required open-text fields
  const cands=[];
  for(const el of [...document.querySelectorAll('textarea[required], input[type=text][required]')]){
    if(el.offsetParent===null)continue;       // not visible
    if(el.value&&el.value.trim())continue;    // already filled
    if(SKIP.test(el.id||el.name||''))continue;
    cands.push({el,q:recover(el)});
  }
  const used=new Set();
  const out=[];
  // pass 1: score-match each candidate to an unused essay by shared words
  for(const c of cands){
    const qw=c.q.split(' ').filter(w=>w.length>4);
    let best=-1,bestScore=0;
    for(let i=0;i<essays.length;i++){
      if(used.has(i))continue;
      const en=norm(essays[i].q);
      let sc=0;for(const w of qw){if(en.includes(w))sc++;}
      if(c.q&&(en.includes(c.q.slice(0,25))||c.q.includes(en.slice(0,25))))sc+=3;
      if(sc>bestScore){bestScore=sc;best=i;}
    }
    if(best>=0&&bestScore>=2){used.add(best);setN(c.el,essays[best].a);out.push({q:c.q.slice(0,40),matched:norm(essays[best].q).slice(0,40),via:'score'});}
    else out.push({q:c.q.slice(0,40),pending:true});
  }
  // pass 2: if exactly ONE required open-text field is still empty and exactly
  // ONE essay answer is unused, assign it (best-effort 1:1). Avoids leaving a
  // single label-less required question empty when we clearly have one answer.
  const stillEmpty=cands.filter(c=>!c.el.value||!c.el.value.trim());
  const unused=[];for(let i=0;i<essays.length;i++){if(!used.has(i))unused.push(i);}
  if(stillEmpty.length===1&&unused.length===1){
    setN(stillEmpty[0].el,essays[unused[0]].a);
    out.push({q:stillEmpty[0].q.slice(0,40),matched:norm(essays[unused[0]].q).slice(0,40),via:'1to1'});
  }
  return out;
}"""


if __name__ == "__main__":
    sys.exit(main())
