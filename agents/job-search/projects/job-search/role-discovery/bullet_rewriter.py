#!/usr/bin/env python3
"""
bullet_rewriter.py — LLM-driven bullet rewriter for the resume tailoring pipeline.

PRIMARY DIRECTIVE: Make Cyrus the top candidate for the role.

Reads a job's JD.md plus the master resume's bullet inventory, calls a model to
produce a STRICT JSON `rewrites.json` (per-role bullet lists + optional title
swaps + skills priority + tailoring notes), validates against light structural
guardrails (title-swap allowlist, per-role bullet count caps, valid JSON shape),
and writes the rewrites.json next to the JD plus a sibling tailoring-notes.md.

Optional: invoke tailor_resume to render the docx+pdf and run a page-fill loop
that asks the model to expand or tighten bullets until the result fits the
1-page envelope at high fill.

Usage:
  bullet_rewriter.py --org robinhood --job-id 7747728 [--family pm]
                     [--out <path>] [--render] [--max-loops 3]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Reuse static maps from tailor_resume.py
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from tailor_resume import (  # type: ignore
    APPS_DIR,
    PROJECT,
    ALLOWED_TITLE_LABELS,
    JOB_BULLETS,
    TITLE_PARA,
    detect_family,
    _soffice_user_install_args,
)

MASTER_MD = PROJECT / "resume" / "Cyrus_Shekari_Resume_master.md"
MASTER_DOCX = PROJECT / "resume" / "Cyrus_Shekari_Resume_master.docx"

# ---------------------------------------------------------------------------
# Bullet caps (2026-05-12): mins force the LLM to fill at least current slots;
# maxes allow extra bullets to use blank page space. Pro Painters joins the
# normal cap family (no longer LOCKED).
# Bullet caps (2026-05-12; mins raised 2026-05-31 to hit Cyrus's preferred
# density). Mins force the LLM to FILL bullets per role rather than stopping at
# a sparse 3 — the prior (3,5) mins left the page ~4 lines short of his liked
# samples. Higher mins push total bullets toward ~21–23 so the page packs full
# with 2-line bullets (the ≤280-char ceiling keeps each ≤2 lines). Maxes give
# the page-fill loop headroom to add one more where a role's JD warrants it.
# Bullet caps. Reverted 2026-05-31 (Cyrus steer) to last-night's working state:
# the 6-25 min bump made resumes overflow to page 2 + oscillate (worse fill,
# slower). Original mins produced clean 0.99-1.0 single-page resumes — that's
# the bar. ft (5,7); all others (3,5).
BULLET_CAPS = {
    "microsoft_ft":     (5, 7),
    "microsoft_2023":   (3, 5),
    "microsoft_2022":   (3, 6),
    "amazon_robotics":  (3, 5),
    "pro_painters":     (3, 6),
}

# Hard per-bullet character ceiling. Above ~290 chars a bullet wraps to a
# 3rd visual line at this font/width (empirically: 291 chars wrapped to 3 lines).
# 290 = the hard edge, one char under the observed 291 wrap point: fills bullets
# as full as possible while EVERY bullet stays ≤2 lines. (Cyrus ruling 2026-05-31:
# 290 not 280/285/300 — 300-310 reintroduces 3-liners; 280 under-fills.) Enforced
# in validate() (re-ask the model) AND hard-trimmed as a final net before render.
MAX_BULLET_CHARS = 290

# Reverse map: paragraph idx → role_key (for tailoring-notes diff display)
PARA_TO_ROLE = {pidx: role for role, idxs in JOB_BULLETS.items() for pidx in idxs}

# Role context blurbs for the prompt
ROLE_SCOPE = {
    "microsoft_ft":   "MSFT FT (Mar 2024–Present): Azure resilience/recovery validation, internal Resilience Automation Platform, AI agent for drill planning, partner integrations (Databricks/Walmart/SAP/NetApp), sovereign-cloud network isolation tests.",
    "microsoft_2023": "MSFT 2023 intern (May–Aug 2023): AI-driven code generation adoption, semantic search migration, intent-based YAML, user research with Azure service teams.",
    "microsoft_2022": "MSFT 2022 intern (May–Aug 2022): region launch automation, Power BI dashboards, cross-team prioritization frameworks.",
    "amazon_robotics":"Amazon Robotics intern (Aug–Dec 2023): legacy OS migration, agile ceremonies, CI/CD automation.",
    "pro_painters":   "Pro Painters intern (May 2021–May 2022): CRM/sales ops, GTM/digital marketing, profitability analysis.",
}


# ---------------------------------------------------------------------------
# Master inventory loaders

def load_master_bullets_from_docx() -> dict[int, str]:
    """Pull the original bullet text for every JOB_BULLETS paragraph index from the master docx."""
    from docx import Document  # type: ignore
    doc = Document(str(MASTER_DOCX))
    paras = doc.paragraphs
    out: dict[int, str] = {}
    for role, idxs in JOB_BULLETS.items():
        for pidx in idxs:
            out[pidx] = paras[pidx].text.strip()
    return out


def load_master_md() -> str:
    return MASTER_MD.read_text() if MASTER_MD.exists() else ""


# ---------------------------------------------------------------------------
# Prompt assembly

def build_prompt(jd_text: str, master_bullets: dict[int, str], family: str) -> str:
    role_blocks = []
    for role, idxs in JOB_BULLETS.items():
        cap_min, cap_max = BULLET_CAPS[role]
        allowed_titles = sorted(ALLOWED_TITLE_LABELS.get(role, []))
        bullets_block = "\n".join(f"  - {master_bullets[i]}" for i in idxs)
        role_blocks.append(
            f"### Role `{role}` (emit {cap_min}..{cap_max} bullets)\n"
            f"Scope: {ROLE_SCOPE[role]}\n"
            f"Allowed title labels: {allowed_titles or '(none — keep current)'}\n"
            f"Current master bullets:\n{bullets_block}\n"
        )

    skills_text = (
        "Master skills (free to reorder, add JD-relevant skills, or drop):\n"
        "- Technical: Azure, distributed systems, CI/CD, APIs, data pipelines, Power BI, YAML, SQL, Python\n"
        "- Program / Product: Technical Program Management, Product Requirements, Roadmapping, Cross-functional execution, Stakeholder management, Agile/Scrum, OKRs\n"
        "- AI / Automation: AI agents, Copilot Studio, workflow automation, semantic search, LLM-powered tools, process optimization, RAG, prompt engineering\n"
        "- Coursework: Data Structures, Algorithms, Databases, Artificial Intelligence, Machine Learning, Data Science\n"
    )

    structural_rules = """\
STRUCTURAL RULES (output shape — must follow exactly):

A. Title swaps: for each role you want to relabel, set title_swaps[role_key] to
   a label from the role's allowed list. Omit to keep the master title.

B. Bullet counts per role MUST fall within the listed cap [min, max]. The
   minimum forces you to fill at least the current slots; the maximum lets
   you add bullets to use blank page space when the JD warrants it.

C. Length goal: FILL THE PAGE to maximum density — match the examples Cyrus
   likes (visually full, ~1–1.5 lines above the bottom margin). Make MOST
   bullets FULL 2-line bullets: TARGET 250–290 chars each. HARD CEILING:
   ≤290 chars per bullet — a bullet MUST NEVER exceed 2 visual lines (anything
   ~291+ wraps to a 3rd line and is FORBIDDEN). Do NOT write short 1-line
   bullets to play it safe — a one-line bullet wastes vertical space; expand
   it with substantive JD-aligned detail until it is a near-full 2-liner
   (250–290 chars) WITHOUT crossing 290. Use the FULL bullet allowance for
   every role (emit each role's `max` count, not its `min`) so the page is
   packed. Bullets must be ONE sentence (or one sentence + a short clause),
   action-verb-led, JD-keyword-aware. No filler padding — add real substance
   (methodology, scope, customer/team context, why the impact mattered).

C1. Bold emphasis: wrap text you want bolded in **double asterisks**. Use
    bold sparingly to highlight the punch of each bullet — strictly 1–2
    short bold spans per bullet (a metric, an outcome word, a key noun).
    Anything you think a recruiter's eye should land on first is fair game,
    not just numbers. Do NOT bold whole sentences or clauses. Do NOT bold
    every adjective. If a bullet has no obvious punch, leave it un-bolded
    rather than forcing something. The `**...**` markers are stripped by
    the renderer; only what's between them becomes bold.

D. Preservation default: KEEP every master bullet's underlying content unless
   PAGE-FIT feedback explicitly tells you the page overflows. On the first
   pass, emit at least the role's `min` count — you may rewrite, but do not
   drop substance unnecessarily.

E. Output format: STRICT JSON only, exact shape (no markdown, no commentary,
   no trailing text):

   {
     "title_swaps": { "<role_key>": "<allowed label>", ... },
     "bullets": {
       "microsoft_ft":     ["bullet 1 text", "bullet 2 text", ...],
       "microsoft_2023":   ["...", ...],
       "microsoft_2022":   ["...", ...],
       "amazon_robotics":  ["...", ...],
       "pro_painters":     ["...", ...]
     },
     "skills_priority": ["...", "..."],
     "tailoring_notes": ["short note", "short note"]
   }

   `bullets` MUST contain an array for every role_key (microsoft_ft,
   microsoft_2023, microsoft_2022, amazon_robotics, pro_painters), even if
   you're keeping the master text — in that case echo the master bullets
   verbatim into the array.

F. Per-JD differentiation (MANDATORY): This resume must read as written
   specifically for THIS job, not a lightly reskinned generic. At least half
   the bullets across all roles must use vocabulary, tools, product areas, or
   outcome framing pulled directly from THIS JD — not just bolding the same
   words differently. If the JD calls out specific domains (e.g. "ads ranking",
   "AI infrastructure", "capacity planning"), at least one bullet per role must
   reference that domain in substance. Generic bullets ("led cross-functional
   teams", "defined roadmaps") are only acceptable when paired with JD-specific
   context. Your tailoring_notes must name at least 3 specific JD terms you
   actually wove in and WHERE (which role/bullet).
"""

    _FAMILY_GUIDANCE = {
        "pm":  "PM (product strategy, roadmaps, customer research, go-to-market).",
        "tpm": "TPM (technical program/project delivery, cross-team execution, eng-partnership).",
        "pgm": "PgM (program delivery, Agile execution, dependencies, stakeholder alignment).",
        "se":  "SE/SA (solutions engineering, customer-facing technical work, demos, pre-sales, integrations, value proofs).",
        "fde":  "FDE (forward-deployed engineering, on-site customer integrations, deployment, custom tooling, technical partnership).",
        "swe":  "SWE/SDE (software engineering IC — emphasize code, system design, implementation, shipped features, technical depth, scalability). "
               "Prefer the [se,fde]-tagged master bullets as the base framing (they are technical/delivery-focused) "
               "and push even harder on implementation detail, code ownership, and engineering impact.",
        "ml":   "ML Engineer (model development, experimentation, ML pipelines, model deployment, metrics/eval, data quality, MLOps). "
               "Use [se,fde]-tagged master bullets as base; emphasize ML/AI tooling, training runs, model lifecycle, "
               "and measurable model performance improvements.",
        "data": "Data Engineer/Scientist (data pipelines, ETL, warehouse, analytics, SQL, streaming, data quality, dashboards). "
               "Use [se,fde]-tagged master bullets as base; emphasize data infrastructure, pipeline reliability, "
               "query performance, and data-driven impact.",
    }
    family_guidance = _FAMILY_GUIDANCE.get(family, f"Role family: {family}.")

    return (
        "You are tailoring Cyrus Shekari's resume to win a specific role.\n\n"
        "PRIMARY DIRECTIVE: Make Cyrus the top candidate for this role. Rewrite\n"
        "the resume bullets so a recruiter or hiring manager reading the JD\n"
        "would think 'this person was built for this job.' Mirror the JD's\n"
        "vocabulary, surface the most relevant skills/tools/outcomes, and lead\n"
        "with strong action verbs.\n\n"
        f"Detected family: {family} — {family_guidance}\n\n"
        f"=== JOB DESCRIPTION ===\n{jd_text.strip()}\n\n"
        f"=== MASTER RESUME ROLES ===\n" + "\n".join(role_blocks) +
        f"\n{skills_text}\n"
        f"=== {structural_rules}\n"
        "Now emit STRICT JSON only."
    )


# ---------------------------------------------------------------------------
# Model invocation

from model_config import model_run_cmd  # inherits agent's current model by default


def call_model(prompt: str, timeout: int = 300) -> str:
    cmd = model_run_cmd(prompt)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"model CLI failed (rc={proc.returncode}); STDERR={proc.stderr[:1000]}")
    try:
        envelope = json.loads(proc.stdout)
    except Exception as e:
        raise RuntimeError(f"non-JSON envelope: {e}; head={proc.stdout[:500]}")
    outs = envelope.get("outputs") or []
    if not outs:
        raise RuntimeError(f"no outputs in envelope: {proc.stdout[:500]}")
    return outs[0].get("text") or ""


# ---------------------------------------------------------------------------
# Output JSON parsing + validation

def extract_json_object(raw: str) -> dict:
    """Extract the first balanced top-level JSON object from raw model text."""
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n", "", s)
        s = re.sub(r"\n```\s*$", "", s)
    start = s.find("{")
    if start < 0:
        raise ValueError(f"no JSON object found in model output: {raw[:300]}")
    depth = 0
    in_str = False
    esc = False
    end = -1
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
    if end < 0:
        raise ValueError("unbalanced JSON object in model output")
    return json.loads(s[start:end + 1])


def _trim_bullets_to_ceiling(rewrites: dict) -> int:
    """Hard-trim any bullet over MAX_BULLET_CHARS to a clean word boundary.
    Mutates rewrites['bullets'] in place. Returns the number of bullets trimmed.
    Guarantees no bullet renders a 3rd line regardless of model behavior."""
    bullets = rewrites.get("bullets")
    if not isinstance(bullets, dict):
        return 0
    count = 0
    for role, arr in bullets.items():
        if not isinstance(arr, list):
            continue
        for i, s in enumerate(arr):
            if not isinstance(s, str):
                continue
            t = s.strip()
            if len(t) <= MAX_BULLET_CHARS:
                continue
            # Cut at the last full word that fits under the ceiling.
            cut = t[:MAX_BULLET_CHARS]
            sp = cut.rfind(" ")
            if sp > 0:
                cut = cut[:sp]
            # Strip dangling punctuation/connectors left by the cut.
            cut = cut.rstrip(" ,;:-—–/&")
            # Drop a trailing orphan connector word (and, with, to, by, for...).
            words = cut.split()
            CONNECTORS = {"and","with","to","by","for","of","the","a","an","that","which","via","into","on","in","across"}
            if words and words[-1].lower() in CONNECTORS:
                words = words[:-1]
                cut = " ".join(words)
            # Balance an unclosed bold marker so the renderer doesn't bold the rest.
            if cut.count("**") % 2 == 1:
                cut = cut.rstrip("*").rstrip()
                # if we removed the closing of a span, drop the now-open opener too
                if cut.count("**") % 2 == 1:
                    cut = cut[:cut.rfind("**")].rstrip()
            arr[i] = cut
            count += 1
    return count


def validate(rewrites: dict, min_offset: int = 0) -> list[str]:
    """Validate model output. min_offset relaxes the per-role bullet floor (e.g.
    -1 during page-fit TIGHTENING so a role can shed one bullet to escape a
    2-page overflow). The floor never drops below 3 (the structural minimum for
    a credible role block)."""
    errors: list[str] = []

    if not isinstance(rewrites, dict):
        return ["top-level output is not a JSON object"]

    # Title swaps — labels must be in allowlist
    title_swaps = rewrites.get("title_swaps") or {}
    if not isinstance(title_swaps, dict):
        errors.append("title_swaps must be an object/dict")
        title_swaps = {}
    for role, label in title_swaps.items():
        allowed = ALLOWED_TITLE_LABELS.get(role)
        if allowed is None:
            errors.append(f"title_swaps[{role!r}] not a known role")
            continue
        if label not in allowed:
            errors.append(f"title_swaps[{role}] = {label!r} not in allowlist {sorted(allowed)}")

    # Bullets — per-role list with count in cap
    bullets = rewrites.get("bullets")
    if not isinstance(bullets, dict):
        errors.append("bullets must be an object keyed by role_key")
        bullets = {}
    for role in JOB_BULLETS.keys():
        cap_min, cap_max = BULLET_CAPS[role]
        cap_min = max(3, cap_min + min_offset)  # relaxable floor, never below 3
        arr = bullets.get(role)
        if arr is None:
            errors.append(f"bullets[{role!r}] is missing (must be an array of {cap_min}..{cap_max} strings)")
            continue
        if not isinstance(arr, list):
            errors.append(f"bullets[{role!r}] must be a list of strings")
            continue
        # Drop whitespace-only / empty entries before counting
        clean = [s for s in arr if isinstance(s, str) and s.strip()]
        n = len(clean)
        if not (cap_min <= n <= cap_max):
            errors.append(f"role {role}: bullet count {n} outside cap [{cap_min},{cap_max}]")
        # Hard 2-line ceiling: any bullet >290 chars wraps to a 3rd line.
        for i, s in enumerate(clean):
            if len(s.strip()) > MAX_BULLET_CHARS:
                errors.append(
                    f"role {role} bullet#{i+1}: {len(s.strip())} chars exceeds "
                    f"{MAX_BULLET_CHARS}-char 2-line ceiling — shorten to ≤{MAX_BULLET_CHARS} "
                    f"(it currently wraps to a 3rd line)")

    # Top-level shape (optional fields are tolerated)
    if "tailoring_notes" in rewrites and not isinstance(rewrites["tailoring_notes"], list):
        errors.append("tailoring_notes must be a list of strings if present")
    if "skills_priority" in rewrites and not isinstance(rewrites["skills_priority"], list):
        errors.append("skills_priority must be a list of strings if present")

    return errors


# ---------------------------------------------------------------------------
# Tailoring notes writer

def write_tailoring_notes(notes_path: Path, rewrites: dict,
                          master_bullets: dict[int, str]) -> None:
    title_swaps = rewrites.get("title_swaps") or {}
    bullets = rewrites.get("bullets") or {}
    notes = rewrites.get("tailoring_notes") or []

    lines = ["# Tailoring notes", ""]
    lines.append("## Title swaps applied")
    if title_swaps:
        for role, label in title_swaps.items():
            lines.append(f"- `{role}` → **{label}**")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Bullet rewrites per role")
    for role, idxs in JOB_BULLETS.items():
        arr = bullets.get(role) or []
        clean = [s for s in arr if isinstance(s, str) and s.strip()]
        lines.append(f"\n### `{role}` ({len(clean)} bullets emitted, master had {len(idxs)})")
        for i, txt in enumerate(clean, 1):
            lines.append(f"{i}. {txt}")
    lines.append("")

    if notes:
        lines.append("## Notes from the rewriter")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    notes_path.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Page-fill estimator (visual fill via pdftotext -bbox-layout)
#
# IMPORTANT (Cyrus 2026-05-31): the MASTER resume is the gold reference for
# both formatting AND length. The pipeline copies the master docx and keeps its
# 1.15 line spacing + tab stops, so a correct output renders at the SAME length
# as the master. Headless LibreOffice renders BOTH the master and correct
# outputs as a phantom "2 pages" (a few lines bleed past the page-1 boundary in
# LO even though Word shows 1 page). So a raw form-feed page COUNT is NOT a
# reliable overflow signal. Instead we measure TOTAL rendered text height
# (cumulative across whatever pages LO emits) and compare it to the master's
# total height: "overflow" = meaningfully TALLER than the master; "under-fill"
# = meaningfully SHORTER. The master itself is the 1.0 target.

def _total_text_height(pdf_path: Path) -> float:
    """Cumulative vertical extent of rendered text across all pages, in points.
    Treats LibreOffice's phantom page-2 bleed as continuous height so the master
    and a length-matched output compare apples-to-apples."""
    import re as _re
    bbox = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=60,
    ).stdout
    page_blocks = _re.findall(
        r'<page[^>]*height="([\d.]+)"[^>]*>(.*?)</page>', bbox, flags=_re.S
    )
    TOP_MARGIN = 14.4
    total = 0.0
    for ph_str, body in page_blocks:
        if not _re.search(r"\S", body):
            continue
        ph = float(ph_str)
        ymaxes = [float(m) for m in _re.findall(r'<word[^>]*yMax="([\d.]+)"', body)]
        if not ymaxes:
            continue
        # Height contributed by this page = bottom-most text minus top margin.
        total += max(0.0, max(ymaxes) - TOP_MARGIN)
    return total


_MASTER_HEIGHT_CACHE: dict[str, float] = {}


def _master_text_height() -> float:
    """Rendered total text height of the master one-pager (cached)."""
    key = "master"
    if key in _MASTER_HEIGHT_CACHE:
        return _MASTER_HEIGHT_CACHE[key]
    master_docx = HERE.parent / "resume" / "Cyrus_Shekari_Resume_master.docx"
    h = 0.0
    if master_docx.exists():
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run(
                ["soffice", *_soffice_user_install_args(),
                 "--headless", "--convert-to", "pdf",
                 "--outdir", td, str(master_docx)],
                capture_output=True, timeout=120,
            )
            pdf = Path(td) / (master_docx.stem + ".pdf")
            if pdf.exists():
                h = _total_text_height(pdf)
    _MASTER_HEIGHT_CACHE[key] = h
    return h


def page_fill(pdf_path: Path) -> tuple[float, int, int]:
    """Returns (fill_ratio, content_lines, est_pages).

    REVERTED 2026-05-31 to the ABSOLUTE single-page metric. Rationale: Cyrus's
    two preferred sample resumes (janestreet-702, sample_pm_cresta) use 1.0 line
    spacing + the 10780 right-tab and pack ~18–20 bullets to ~1.5 lines of bottom
    whitespace — strictly ONE page. The master-relative experiment drove the loop
    to EXCEED the master's length, producing 2-page output and 3-line bullets.
    The absolute metric below (fill vs a single page's usable height) plus the
    ≤290-char-per-bullet ceiling in build_prompt is what reproduces the liked
    samples. _total_text_height / _master_text_height are kept as unused helpers
    in case a future approach needs them, but page_fill no longer calls them.
    """
    return _abs_page_fill(pdf_path)


def _abs_page_fill(pdf_path: Path) -> tuple[float, int, int]:
    """Legacy absolute single-page fill (fallback when master ref unavailable)."""
    import re as _re
    txt_proc = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=60,
    )
    text = txt_proc.stdout
    pages_raw = text.split("\f")
    pages_nonempty = [p for p in pages_raw if any(ln.strip() for ln in p.splitlines())]
    est_pages = max(1, len(pages_nonempty))
    lines = sum(1 for ln in text.splitlines() if ln.strip())

    bbox_proc = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=60,
    )
    bbox_xml = bbox_proc.stdout
    page_blocks = _re.findall(
        r'<page[^>]*height="([\d.]+)"[^>]*>(.*?)</page>', bbox_xml, flags=_re.S
    )
    if not page_blocks:
        return (lines / (52 * est_pages), lines, est_pages)

    # Honest bottom-margin (14.4pt = 0.2in). Paired with the ≤290-char/bullet
    # ceiling (build_prompt) this is SAFE: the loop fills toward ~1–2 lines of
    # true bottom whitespace by ADDING ≤2-line bullets, and the char cap prevents
    # the 3-line overshoot that previously pushed 14.4 to a 2nd page. The earlier
    # 36pt value reserved ~3 lines as off-limits, so the loop stopped with ~4
    # lines of visible whitespace (too empty — Cyrus's liked samples sit ~1.5).
    TOP_MARGIN = 14.4
    # BOTTOM_MARGIN lowered 14.4->10.0 (2026-05-31, Cyrus-approved whitespace fix):
    # the honest typeable floor sits ~10pt from the edge, so a genuinely-full page
    # reads closer to 1.0 and the fill loop keeps adding one more fitting 2-line
    # bullet before declaring done. SAFE: the unconditional best-1-page revert
    # (see run()) still discards any 2-page overshoot, so this cannot spill to p2.
    BOTTOM_MARGIN = 10.0
    fills = []
    for ph_str, body in page_blocks:
        if not _re.search(r"\S", body):
            continue
        ph = float(ph_str)
        ymaxes = [float(m) for m in _re.findall(r'<word[^>]*yMax="([\d.]+)"', body)]
        if not ymaxes:
            continue
        text_bottom = max(ymaxes)
        usable = ph - TOP_MARGIN - BOTTOM_MARGIN
        used = max(0.0, text_bottom - TOP_MARGIN)
        fills.append(min(1.0, used / usable) if usable > 0 else 0.0)
    if not fills:
        return (lines / (52 * est_pages), lines, est_pages)
    fill = sum(fills) / len(fills)
    return fill, lines, est_pages


# ---------------------------------------------------------------------------
# Render via tailor_resume

def render_resume(org: str, job_id: str, out_dir: Path | None = None, suffix: str = "_v2", family: str | None = None) -> Path:
    out_dir = out_dir or (APPS_DIR / f"{org}-{job_id}")
    cmd = [sys.executable, str(HERE / "tailor_resume.py"), "--org", org, "--job-id", job_id,
           "--out-dir", str(out_dir), "--suffix", suffix]
    if family:
        cmd += ["--family", family]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(
            f"tailor_resume.py failed (rc={proc.returncode})\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}")
    pdf_path = out_dir / f"Cyrus_Shekari_Resume_{org}_{job_id}{suffix}.pdf"
    if not pdf_path.exists():
        raise RuntimeError(f"expected pdf not produced: {pdf_path}")
    return pdf_path


# ---------------------------------------------------------------------------
# Main

def run(org: str, job_id: str, family: str | None, out_path: Path | None,
        render: bool, max_loops: int, prefer_fuller: bool = False,
        out_dir: Path | None = None, suffix: str = "_v2") -> dict:
    """prefer_fuller is a no-op alias kept for back-compat; fullness is now
    the default goal (length rule C in the prompt).

    out_dir: staging directory for JD.md, rewrites.json, tailoring-notes.md,
    and rendered PDF. Defaults to APPS_DIR/{org}-{job_id} for back-compat.
    Pass an explicit path (e.g. a tmpdir) to keep all file I/O isolated from
    the main applications/queued/ tree — required for external/parallel callers.
    """
    _ = prefer_fuller  # noqa
    out_dir = out_dir or (APPS_DIR / f"{org}-{job_id}")
    jd_path = out_dir / "JD.md"
    if not jd_path.exists():
        raise FileNotFoundError(f"JD.md not found: {jd_path}")
    jd_text = jd_path.read_text()

    if not family:
        title_line = ""
        for ln in jd_text.splitlines():
            s = ln.strip().lstrip("#").strip()
            if s:
                title_line = s
                break
        family = detect_family(title_line)

    master_bullets = load_master_bullets_from_docx()

    out_path = out_path or (out_dir / "rewrites.json")
    notes_path = out_dir / "tailoring-notes.md"
    # Ensure staging dir exists (important when an external caller passes a tmpdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_prompt = build_prompt(jd_text, master_bullets, family)
    retry_validations = 0
    expand_threshold = 0.99  # we want ≥ 99% page fill (Cyrus: master hits 100%; 0.97 stopped too early, leaving ~3 lines of whitespace)

    last_errors: list[str] = []
    rewrites: dict | None = None
    candidate: dict | None = None
    for attempt in range(1, 4):
        prompt = base_prompt
        if last_errors:
            prompt += (
                "\n\n=== PRIOR ATTEMPT VIOLATED THESE RULES — FIX THEM ===\n"
                + "\n".join(f"- {e}" for e in last_errors)
                + "\nReturn corrected STRICT JSON only."
            )
        print(f"[bullet_rewriter] model attempt {attempt} (prompt {len(prompt)} chars)", file=sys.stderr)
        raw = call_model(prompt)
        try:
            candidate = extract_json_object(raw)
        except Exception as e:
            last_errors = [f"output was not valid JSON: {e}"]
            retry_validations += 1
            continue
        errors = validate(candidate)
        if not errors:
            rewrites = candidate
            break
        last_errors = errors
        retry_validations += 1
        print(f"[bullet_rewriter] validation failed: {errors}", file=sys.stderr)
    if rewrites is None:
        # All retries failed validation, but the only remaining errors are
        # over-length bullets (which the hard-trim below can fix). Rather than
        # raising, use the last candidate and let the trim safety-net handle it.
        # If `candidate` is still None (e.g. JSON parse failed every time),
        # there is nothing we can do and we re-raise.
        if candidate is None:
            raise RuntimeError(f"validation failed after retries: {last_errors}")
        # Only fall through if the remaining errors are EXCLUSIVELY char-ceiling
        # violations (the trim fixes those); re-raise for any other error type.
        non_trim_errors = [e for e in last_errors if "exceeds" not in e and "ceiling" not in e]
        if non_trim_errors:
            raise RuntimeError(f"validation failed after retries: {last_errors}")
        print(
            f"[bullet_rewriter] all retries exceeded ceiling-only; applying hard-trim fallback",
            file=sys.stderr,
        )
        rewrites = candidate

    # Final safety net: hard-trim any bullet still over the 2-line ceiling at a
    # word boundary so it can NEVER render a 3rd line, even if the model ignored
    # the prompt + validation re-asks. Trims at the last full word ≤MAX, drops a
    # dangling connector/comma, restores any unbalanced ** bold marker.
    trimmed = _trim_bullets_to_ceiling(rewrites)
    if trimmed:
        print(f"[bullet_rewriter] hard-trimmed {trimmed} over-ceiling bullet(s) to ≤{MAX_BULLET_CHARS} chars", file=sys.stderr)

    out_path.write_text(json.dumps(rewrites, indent=2) + "\n")
    write_tailoring_notes(notes_path, rewrites, master_bullets)
    print(f"[bullet_rewriter] wrote {out_path}", file=sys.stderr)
    print(f"[bullet_rewriter] wrote {notes_path}", file=sys.stderr)

    result = {
        "rewrites_path": str(out_path),
        "notes_path": str(notes_path),
        "title_swaps": rewrites.get("title_swaps", {}),
        "bullet_counts": {role: len([b for b in (rewrites.get("bullets") or {}).get(role, []) if isinstance(b, str) and b.strip()])
                          for role in JOB_BULLETS.keys()},
        "retry_validations": retry_validations,
    }

    if render:
        pdf_path = render_resume(org, job_id, out_dir=out_dir, suffix=suffix, family=family)
        fill, lines, pages = page_fill(pdf_path)
        result.update({"pdf": str(pdf_path), "page_fill": round(fill, 3),
                       "content_lines": lines, "est_pages": pages})

        # Track the BEST single-page result across all loops. The fill loop can
        # oscillate (add bullet -> overflow -> drop -> under-fill -> ...), and
        # the FINAL loop is often an overshoot in one direction. We want the
        # fullest result that still fit on ONE page, not whatever the last loop
        # happened to produce. Snapshot rewrites whenever we see a better
        # 1-page fill, and restore it at the end.
        import copy as _copy
        best_fill = fill if pages == 1 else -1.0
        best_rewrites = _copy.deepcopy(rewrites) if pages == 1 else None

        page_fit_retries = 0
        for loop in range(1, max_loops + 1):
            adjust = None
            if pages > 1:
                adjust = ("Resume overflows onto page %d (fill≈%.0f%% on the spilled page) — "
                          "TIGHTEN: shorten phrasing across bullets, and DROP the weakest "
                          "bullets within each role's [min, max] cap, until everything fits "
                          "on ONE page. Keep every bullet ≤2 visual lines.") % (pages, fill * 100)
            elif fill < expand_threshold:
                adjust = ("Resume under-fills the single page (≈%.0f%% visual fill) — "
                          "EXPAND existing bullets to fuller 2-line versions with substantive "
                          "JD-aligned detail. If still under-filled, ADD a bullet within each "
                          "role's cap. Fill the page but stay strictly 1 page — never spill "
                          "to page 2.") % (fill * 100)
            else:
                break
            print(f"[bullet_rewriter] page-fill loop {loop}: {adjust}", file=sys.stderr)
            sub_errors: list[str] = []
            new_rewrites = None
            for sub_attempt in range(1, 3):
                prompt = base_prompt + (
                    f"\n\n=== PAGE-FIT FEEDBACK ===\n{adjust}\n"
                    f"Current output had pages={pages}, fill≈{fill:.2f}.\n"
                )
                if sub_errors:
                    prompt += (
                        "\nPrior page-fit attempt violated:\n"
                        + "\n".join(f"- {e}" for e in sub_errors)
                        + "\nFix and retry. "
                    )
                prompt += "Return corrected STRICT JSON only."
                raw = call_model(prompt)
                try:
                    candidate = extract_json_object(raw)
                except Exception as e:
                    sub_errors = [f"output was not valid JSON: {e}"]
                    page_fit_retries += 1
                    continue
                errors = validate(candidate, min_offset=-1 if pages > 1 else 0)  # relaxed floor harmless w/ (3,5) mins; kept for overflow escape
                if not errors:
                    new_rewrites = candidate
                    break
                sub_errors = errors
                page_fit_retries += 1
                print(f"[bullet_rewriter] page-fit sub-attempt {sub_attempt} failed: {errors}", file=sys.stderr)
            if new_rewrites is None:
                print(f"[bullet_rewriter] page-fit gave up after retries; keeping previous", file=sys.stderr)
                break
            rewrites = new_rewrites
            _trim_bullets_to_ceiling(rewrites)  # enforce 2-line ceiling each loop
            out_path.write_text(json.dumps(rewrites, indent=2) + "\n")
            write_tailoring_notes(notes_path, rewrites, master_bullets)
            pdf_path = render_resume(org, job_id, out_dir=out_dir, suffix=suffix, family=family)
            fill, lines, pages = page_fill(pdf_path)
            result.update({
                "pdf": str(pdf_path), "page_fill": round(fill, 3),
                "content_lines": lines, "est_pages": pages,
                f"loop_{loop}_action": adjust,
                "bullet_counts": {role: len([b for b in (rewrites.get("bullets") or {}).get(role, []) if isinstance(b, str) and b.strip()])
                                  for role in JOB_BULLETS.keys()},
            })
            # Snapshot if this is the best single-page fill so far.
            if pages == 1 and fill > best_fill:
                best_fill = fill
                best_rewrites = _copy.deepcopy(rewrites)
        # Restore the best single-page result if the loop ended on a worse one
        # (overshoot/oscillation). Re-render so outputs match the chosen state.
        if best_rewrites is not None and (pages > 1 or fill < best_fill - 1e-9):
            print(f"[bullet_rewriter] restoring best 1-page result fill={best_fill:.3f} "
                  f"(final loop ended at fill={fill:.3f} pages={pages})", file=sys.stderr)
            rewrites = best_rewrites
            out_path.write_text(json.dumps(rewrites, indent=2) + "\n")
            write_tailoring_notes(notes_path, rewrites, master_bullets)
            pdf_path = render_resume(org, job_id, out_dir=out_dir, suffix=suffix, family=family)
            fill, lines, pages = page_fill(pdf_path)
            result.update({
                "pdf": str(pdf_path), "page_fill": round(fill, 3),
                "content_lines": lines, "est_pages": pages,
                "restored_best": True,
                "bullet_counts": {role: len([b for b in (rewrites.get("bullets") or {}).get(role, []) if isinstance(b, str) and b.strip()])
                                  for role in JOB_BULLETS.keys()},
            })
        result["page_fit_retries"] = page_fit_retries

        # --- Skills top-up pass (2026-06-16) ---
        # If after all loops we're still under 0.97 fill on a single page,
        # do one final LLM call asking ONLY to expand the Skills section.
        # Skills text wraps naturally and has no bullet-count cap, so this
        # is the safest lever to squeeze out the last 1-2 orphaned lines.
        TOPUP_THRESHOLD = 0.97
        if render and pages == 1 and fill < TOPUP_THRESHOLD:
            topup_prompt = (
                base_prompt
                + f"\n\n=== SKILLS TOP-UP ===\n"
                + f"The resume currently fills {fill*100:.0f}% of the page (target ≥97%). "
                + "The bullet sections are locked — do NOT change any bullets or title_swaps. "
                + "ONLY expand the skills_priority list: add more JD-relevant skills/tools "
                + "(reorder existing, add new terms from the JD) so the Skills section "
                + "takes up 1-2 more lines and fills the remaining whitespace. "
                + "Return the full corrected JSON with only skills_priority changed."
            )
            try:
                raw_topup = call_model(topup_prompt)
                topup_rewrites = extract_json_object(raw_topup)
                # Only accept if bullets unchanged (don't let LLM sneak in bullet changes)
                orig_bullets = rewrites.get("bullets", {})
                topup_bullets = topup_rewrites.get("bullets", {})
                bullets_unchanged = (orig_bullets == topup_bullets)
                if bullets_unchanged and not validate(topup_rewrites):
                    rewrites = topup_rewrites
                    out_path.write_text(json.dumps(rewrites, indent=2) + "\n")
                    write_tailoring_notes(notes_path, rewrites, master_bullets)
                    pdf_path = render_resume(org, job_id, out_dir=out_dir, suffix=suffix, family=family)
                    topup_fill, topup_lines, topup_pages = page_fill(pdf_path)
                    if topup_pages == 1 and topup_fill > fill:
                        fill, lines, pages = topup_fill, topup_lines, topup_pages
                        result.update({"pdf": str(pdf_path), "page_fill": round(fill, 3),
                                       "content_lines": lines, "est_pages": pages,
                                       "skills_topup": True})
                        print(f"[bullet_rewriter] skills top-up: fill {fill:.3f} → {topup_fill:.3f}", file=sys.stderr)
                    else:
                        # top-up overflowed or made it worse — revert
                        out_path.write_text(json.dumps(best_rewrites or rewrites, indent=2) + "\n")
                        print(f"[bullet_rewriter] skills top-up reverted (pages={topup_pages} fill={topup_fill:.3f})", file=sys.stderr)
            except Exception as e:
                print(f"[bullet_rewriter] skills top-up failed: {e}", file=sys.stderr)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--org", required=True)
    ap.add_argument("--job-id", required=True)
    ap.add_argument("--family", default=None, choices=["pm", "tpm", "pgm", "se", "fde", "swe", "ml", "data"])
    ap.add_argument("--out", default=None)
    ap.add_argument("--out-dir", default=None,
                    help="Staging directory for JD.md, rewrites.json, tailoring-notes.md, "
                         "and rendered PDF. Defaults to applications/queued/{org}-{job_id}/. "
                         "Set this to keep all I/O isolated from the main queue. "
                         "IMPORTANT: JD.md must already exist inside this directory "
                         "(the rewriter always reads <out-dir>/JD.md). "
                         "Stage it first: cp /path/to/JD.md <out-dir>/JD.md")
    ap.add_argument("--render", action="store_true",
                    help="Also render docx+pdf via tailor_resume.py and run page-fit loop.")
    ap.add_argument("--max-loops", type=int, default=6)
    ap.add_argument("--prefer-fuller", action="store_true",
                    help="No-op alias (fullness is the default goal now). Kept for back-compat.")
    ap.add_argument("--user-install", default=None,
                    help="Private LibreOffice profile dir; sets "
                         "-env:UserInstallation=file://<dir> on soffice renders "
                         "so concurrent renders don't collide on the shared LO "
                         "profile lock. Unset = historical behavior.")
    args = ap.parse_args()
    if args.user_install:
        os.environ["RESUME_LO_USER_INSTALL"] = args.user_install
    out = Path(args.out) if args.out else None
    explicit_out_dir = Path(args.out_dir) if args.out_dir else None
    result = run(args.org, args.job_id, args.family, out, args.render, args.max_loops,
                 prefer_fuller=args.prefer_fuller, out_dir=explicit_out_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
