#!/usr/bin/env python3
"""
cover_answer_generator.py — Generate `cover_answers.md` for an application packet.

NOTE ON NAMING: Despite the "cover" in the filename, this generator handles ALL
free-text application questions, not just cover letters. That includes:
  - Traditional cover letters (rare; most boards don't ask)
  - "Why [Company]?" / "Why this role?" prompts
  - Short essays ("Tell us about a project...")
  - Accommodations notes
  - "Anything else we should know?" / additional-info fields
  - Disclosures + free-text policy acknowledgements (e.g. Anthropic's AI policy)
Structured fields (yes/no, dropdowns, contact info, demographics) come from
`prefill.json`, not this module. Kept the historical filename to avoid breaking
the 99+ existing packets that already reference `cover_answers.md`.

Given an application slug (e.g. `robinhood-7747728`), reads:
  - applications/queued/<slug>/JD.md (or applications/submitted/<slug>/JD.md)
  - applications/dryrun/<dryrun-name>.json (form spec — we resolve slug→dryrun
    by trying <slug>.json first, then <org-letters-only>-<job_id>.json which
    handles `glean→gleanwork`, `scale-ai→scaleai`, etc.)
  - the tailored resume docx in the packet (Cyrus_Shekari_Resume_*_v2.docx),
    falling back to resume/Cyrus_Shekari_Resume_master.docx
  - personal-info.json (canonical candidate facts)

Identifies open-text/essay form questions among `fields[]`:
  - status == "unresolved" or "blocker"
  - type in {"input_text", "textarea"} AND label looks like an open-ended
    question (contains "?" OR "describe"/"why"/"tell us"/"share"/"explain"/
    "experience with"/"how would"/"what makes"/"interest" etc.)

Calls `openclaw capability model run` with the same envelope used by
bullet_rewriter.py and writes `cover_answers.md` into the packet folder.

Output AI-disclosure policy (set 2026-05-13, see MEMORY.md): answer "No" to
any "did you use AI in this application?" question across ALL companies
including Anthropic. NO transparency parentheticals, NO meta-commentary.

Usage:
  python cover_answer_generator.py --slug robinhood-7747728
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
_PI = json.loads((PROJECT / "personal-info.json").read_text())
_FULL_NAME = _PI["identity"]["first_name"] + " " + _PI["identity"]["last_name"]
QUEUED_DIR = PROJECT / "applications" / "queued"
SUBMITTED_DIR = PROJECT / "applications" / "submitted"
DRYRUN_DIR = PROJECT / "applications" / "dryrun"
PERSONAL_INFO = PROJECT / "personal-info.json"
MASTER_DOCX = PROJECT / "resume" / "Cyrus_Shekari_Resume_master.docx"

MODEL_CLI = None  # deprecated: use model_config.model_run_cmd() (inherits agent model)
from model_config import model_run_cmd

# Heuristics for open-ended essay questions
OPEN_QUESTION_HINTS = re.compile(
    r"\b(why|describe|tell us|share|explain|experience with|how would|how do you|"
    r"what makes|what excites|what draws|what interests|interested in|interest in|"
    r"what attracts|tell me|walk us|walk me|elaborate|provide additional|"
    r"additional information|please provide|please share|please describe|"
    r"please tell|please explain|in your own words|briefly|background|"
    r"point us|point me|show us|show me)\b",
    re.I,
)

# Skip patterns (not essay questions even if textarea)
SKIP_PATTERNS = re.compile(
    r"\b(resume|cv|cover letter|linkedin|website|github|portfolio|"
    r"how did you hear|where did you hear|referred by|"
    r"first name|last name|preferred name|email|phone|address|street|city|state|"
    r"zip|country|location|pronouns|gender|race|ethnic|veteran|disabilit|"
    r"hispanic|lgbtq|salary|compensation|currency|"
    r"start date|earliest start|notice period|"
    r"valid driver|background check|drug screen|felony|non-compete|"
    r"already applied|previously applied|previously employed|currently employed|"
    r"work authorized|sponsorship|visa|"
    r"latitude|longitude)\b",
    re.I,
)

# Branch fields like 'If you answered Yes ... please provide additional information'
BRANCH_FIELD_RE = re.compile(
    r"if you answered\s+[\"']?yes[\"']?|please provide additional information|"
    r"additional information here|if yes,? please|please elaborate.*above",
    re.I,
)

# AI-disclosure / acknowledgment question patterns
AI_DISCLOSURE_RE = re.compile(
    r"\b(used? ai|ai (tool|assistant|use|policy|partnership|guideline)|"
    r"chatgpt|claude|llm|generative ai|artificial intelligence|"
    r"genai|gen-ai)\b",
    re.I,
)
ACK_CONFIRM_RE = re.compile(
    r"\b(confirm|acknowledge|i understand|do you understand|i agree|"
    r"have you read)\b",
    re.I,
)

# Banned phrases (LLM transparency leaks) for validation
BANNED_PHRASES = [
    "as an ai",
    "i used ai",
    "claude",
    "chatgpt",
    "language model",
    "transparency:",
    "(used ai",
    "with ai assistance",
    "with the help of ai",
    "ai-generated",
    "generated by ai",
]


def resolve_packet_dir(slug: str) -> Path:
    for base in (QUEUED_DIR, SUBMITTED_DIR):
        p = base / slug
        if p.is_dir():
            return p
    raise FileNotFoundError(f"packet not found in queued/ or submitted/: {slug}")


def resolve_dryrun_path(slug: str) -> Path:
    """Slug is `{org}-{job_id}` where org may use hyphens AND job_id may be
    a UUID (which itself contains hyphens, for Ashby roles). Try literal
    filename first, then UUID-suffix split, then numeric-suffix split, then
    glob fallback."""
    direct = DRYRUN_DIR / f"{slug}.json"
    if direct.exists():
        return direct
    # Workday slugs are `{company}-{reqid.lower()}` e.g. intel-jr0283865-1.
    # Real dryrun filename is `workday-{tenant}-{REQID}.json` (REQID case-sensitive).
    # Try this BEFORE the generic glob fallback (which would otherwise match by
    # the trailing numeric segment and conflict with other tenants whose reqid
    # also ends in `-1`).
    wd_matches = list(DRYRUN_DIR.glob(f"workday-*.json"))
    if wd_matches:
        slug_low = slug.lower()
        for cand in wd_matches:
            # filename: workday-{tenant}-{REQID}.json
            stem = cand.stem  # workday-intel-JR0283865-1
            parts = stem.split("-", 2)  # ['workday', 'intel', 'JR0283865-1']
            if len(parts) == 3:
                tenant, reqid = parts[1], parts[2]
                cand_slug = f"{tenant}-{reqid}".lower()
                # match if slug ends with -{reqid.lower()} (handles company
                # name prefixes that differ from tenant, e.g. baker-hughes vs bakerhughes)
                if slug_low.endswith("-" + reqid.lower()) or slug_low == cand_slug:
                    return cand
    # Lever slugs are `{company}-{lv_jid[:8]}` (truncated UUID prefix). Real
    # dryrun filename is `lever-{lv_org}-{full_uuid}.json`. Glob by the 8-char prefix.
    short_m = re.search(r"-([0-9a-fA-F]{8})$", slug)
    if short_m:
        prefix = short_m.group(1)
        lever_matches = list(DRYRUN_DIR.glob(f"lever-*-{prefix}-*.json"))
        if len(lever_matches) == 1:
            return lever_matches[0]
        if len(lever_matches) > 1:
            raise FileNotFoundError(
                f"lever dryrun ambiguous for slug {slug}: {[m.name for m in lever_matches]}")
    # First try: UUID-suffix (Ashby) — match the trailing 36-char UUID.
    uuid_m = re.search(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$", slug)
    if uuid_m:
        job_id = uuid_m.group(1)
        org_part = slug[:uuid_m.start()].rstrip("-")
        collapsed = re.sub(r"[^A-Za-z0-9]", "", org_part)
        for cand in (DRYRUN_DIR / f"{org_part}-{job_id}.json",
                     DRYRUN_DIR / f"{collapsed}-{job_id}.json"):
            if cand.exists():
                return cand
        matches = list(DRYRUN_DIR.glob(f"*-{job_id}.json"))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise FileNotFoundError(
                f"dryrun ambiguous for slug {slug}: {[m.name for m in matches]}")
    # split on last hyphen → org, job_id (Greenhouse / numeric job_id case)
    if "-" in slug:
        idx = slug.rfind("-")
        org_part, job_id = slug[:idx], slug[idx + 1:]
        collapsed = re.sub(r"[^A-Za-z0-9]", "", org_part)
        alt = DRYRUN_DIR / f"{collapsed}-{job_id}.json"
        if alt.exists():
            return alt
        # Final fallback: any dryrun ending in -<job_id>.json
        matches = list(DRYRUN_DIR.glob(f"*-{job_id}.json"))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise FileNotFoundError(
                f"dryrun ambiguous for slug {slug}: {[m.name for m in matches]}")
    raise FileNotFoundError(f"dryrun spec not found for slug: {slug}")


def load_resume_text(packet_dir: Path) -> str:
    """Prefer tailored v2 docx in the packet; fall back to master."""
    from docx import Document  # type: ignore
    candidates = sorted(packet_dir.glob("Cyrus_Shekari_Resume_*_v2.docx"))
    docx_path = candidates[0] if candidates else MASTER_DOCX
    doc = Document(str(docx_path))
    paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paras)


def is_essay_question(field: dict) -> bool:
    """Return True iff this field is an open-ended essay/textarea that needs
    a generated answer."""
    ftype = (field.get("type") or "").lower()
    label = (field.get("label") or "").strip()
    if not label:
        return False
    # Skip select/file/hidden/checkbox
    if ftype not in ("textarea", "input_text"):
        return False
    if SKIP_PATTERNS.search(label):
        return False
    if BRANCH_FIELD_RE.search(label):
        return False
    # Skip fields that the dryrun already filled with an intentionally blank value
    status = (field.get("status") or "").lower()
    value = field.get("value")
    if status == "filled" and (value == "" or value is None):
        return False
    # Always include true textareas with non-trivial labels
    if ftype == "textarea" and len(label) > 10:
        return True
    # For input_text, include if label looks like a question OR is a REQUIRED
    # free-text field that isn't a known structured/PII/legal field. Cyrus
    # directive (2026-05-31): parse and answer EVERY open-ended question a
    # company asks, not just ones with a '?' or a hint keyword. SKIP_PATTERNS
    # (above) already excludes name/email/salary/visa/links/etc., so anything
    # left that's required and free-text is a real question we should answer.
    if "?" in label or OPEN_QUESTION_HINTS.search(label):
        return True
    if field.get("required") and len(label) >= 3:
        return True
    return False


def select_questions(spec: dict) -> list[dict]:
    """Pick essay questions from the dryrun spec. Returns list of
    {id, label, type, required}."""
    out = []
    seen_ids = set()
    for f in spec.get("fields") or []:
        if f.get("id") in seen_ids:
            continue
        if is_essay_question(f):
            out.append({
                "id": f.get("id"),
                "label": f.get("label", "").strip(),
                "type": f.get("type"),
                "required": bool(f.get("required")),
                "status": f.get("status"),
            })
            seen_ids.add(f.get("id"))
    return out


def classify_question(label: str) -> str:
    """Bucket: ai_disclosure | ack_confirm | why_company | open_essay."""
    if AI_DISCLOSURE_RE.search(label):
        return "ai_disclosure"
    # Pure acknowledgment confirmations (read & agree style)
    if ACK_CONFIRM_RE.search(label) and len(label) < 300:
        return "ack_confirm"
    if re.search(r"\b(why (do you (want|wish) to (work|join)|are you interested|"
                 r"this (role|company|team)|us|join)|what (interests|excites|draws|attracts) you)\b",
                 label, re.I):
        return "why_company"
    return "open_essay"


def build_prompt(jd_text: str, resume_text: str, personal_info: dict,
                 questions: list[dict], company: str, retry_violations: list[str] | None = None) -> str:
    pi_brief = json.dumps({
        "identity": personal_info.get("identity"),
        "contact": personal_info.get("contact"),
        "address": personal_info.get("address"),
        "work_authorization": personal_info.get("work_authorization"),
        "experience_summary": personal_info.get("experience_summary"),
        "education": personal_info.get("education"),
        "preferences": personal_info.get("preferences"),
    }, indent=2)

    q_block = []
    for i, q in enumerate(questions, 1):
        bucket = classify_question(q["label"])
        q_block.append(f"Q{i} [{bucket}{' / required' if q['required'] else ''}]: {q['label']}")
    questions_text = "\n\n".join(q_block)

    rules = f"""\
ANSWER POLICY (mandatory — read carefully):

1. Voice: {_FULL_NAME}, first person, conversational, professional but NOT
   corporate-stiff. Direct, specific, plainspoken. Avoid em dashes; use commas
   or regular dashes. Do not start with "I am writing to" or other letter-y
   openings. Do not gush.

2. Truth: every biographical claim, number, company name (of past
   employers), project, title, and date MUST come from the resume text or
   personal-info.json provided below. DO NOT invent metrics, customer names,
   projects, titles, dates, or employment history. If a question asks about
   factual experience Cyrus has no resume evidence for, write a brief honest
   answer that pivots to adjacent real experience. EXCEPTION: for
   motivational "why this company / why this role" framing (rule 5), you may
   present plausible inferred enthusiasm and company-specific interest as
   Cyrus's own — that is not a biographical fact and is explicitly allowed.

3. AI-disclosure questions (bucket = "ai_disclosure"): answer EXACTLY "No."
   on its own line. NO transparency parentheticals. NO meta-commentary. NO
   "but I confirm understanding". Just: No.

4. Acknowledgment / confirmation (bucket = "ack_confirm"): answer with a
   single short affirmative sentence ("Yes — confirmed." or "Yes, I
   understand and agree."). Do NOT mention AI.

5. "Why <company>" / interest questions (bucket = "why_company"): 2 short
   paragraphs. ALWAYS produce a confident, specific, enthusiastic answer —
   never skip, never hedge, never say you lack information about the company.
   First paragraph: connect Cyrus's actual resume work (specific project +
   specific outcome — these MUST be real) to what the JD/role is asking for.
   Second paragraph: state concrete, plausible reasons this company
   specifically appeals to him (its mission, product area, market, or
   technical bet, inferred from the JOB DESCRIPTION above). You MAY assert
   genuine-sounding enthusiasm and company-specific motivation here even
   where the resume gives no direct evidence — infer reasonable interest
   from the JD and present it as Cyrus's own. Keep it grounded and natural,
   not effusive. Do NOT invent fake resume facts (projects, metrics,
   employers); the fabrication latitude is ONLY for the motivational "why
   this company" framing, not for biographical claims.

6. Open essay (bucket = "open_essay"): 2-3 short paragraphs unless the
   question is narrow ("Briefly describe…") in which case 1 tight
   paragraph (3-5 sentences). Lead with the most relevant concrete
   experience. Quantify when the resume gives you a number.

7. Banned: do not write "as an AI", "I used AI", "Claude", "ChatGPT",
   "language model", "transparency:", or any AI-related disclaimer in any
   open answer.

8. Output: STRICT JSON only, no markdown fences, exact shape:

   {
     "answers": [
       { "question": "<verbatim question text>", "answer": "<answer text>" },
       ...
     ]
   }

   Emit one entry per question, in the order shown, using the exact
   question text from the prompt as the "question" value.
"""

    prompt = (
        f"You are writing first-person application answers for {_FULL_NAME}, "
        f"applying to {company}.\n\n"
        f"=== JOB DESCRIPTION ===\n{jd_text.strip()}\n\n"
        f"=== CANDIDATE FACTS (personal-info.json excerpt) ===\n{pi_brief}\n\n"
        f"=== TAILORED RESUME TEXT ===\n{resume_text.strip()}\n\n"
        f"=== QUESTIONS TO ANSWER ===\n{questions_text}\n\n"
        f"=== {rules}\n"
    )
    if retry_violations:
        prompt += (
            "\n=== PRIOR ATTEMPT VIOLATED THESE RULES — FIX THEM ===\n"
            + "\n".join(f"- {v}" for v in retry_violations)
            + "\nReturn corrected STRICT JSON only.\n"
        )
    prompt += "Now emit STRICT JSON only."
    return prompt


def call_model(prompt: str, timeout: int = 300) -> str:
    cmd = model_run_cmd(prompt)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"model CLI failed (rc={proc.returncode}); STDERR={proc.stderr[:1000]}")
    try:
        envelope = json.loads(proc.stdout)
    except Exception as e:
        raise RuntimeError(f"non-JSON envelope: {e}; head={proc.stdout[:500]}")
    outs = envelope.get("outputs") or []
    if not outs:
        raise RuntimeError(f"no outputs in envelope: {proc.stdout[:500]}")
    return outs[0].get("text") or ""


def extract_json_object(raw: str) -> dict:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n", "", s)
        s = re.sub(r"\n```\s*$", "", s)
    start = s.find("{")
    if start < 0:
        raise ValueError(f"no JSON object found: {raw[:300]}")
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
        raise ValueError("unbalanced JSON")
    return json.loads(s[start:end + 1])


def validate(parsed: dict, questions: list[dict]) -> list[str]:
    """Return list of violations. Empty = OK."""
    violations: list[str] = []
    answers = parsed.get("answers")
    if not isinstance(answers, list):
        return ["top-level 'answers' must be a list"]
    if len(answers) != len(questions):
        violations.append(f"expected {len(questions)} answers, got {len(answers)}")
    for i, ans in enumerate(answers):
        if not isinstance(ans, dict):
            violations.append(f"answers[{i}] not an object")
            continue
        text = (ans.get("answer") or "").strip()
        if not text:
            violations.append(f"answers[{i}] empty answer")
            continue
        low = text.lower()
        for bad in BANNED_PHRASES:
            if bad in low:
                violations.append(
                    f"answers[{i}] contains banned phrase '{bad}' — "
                    f"AI-disclosure leak. Rewrite without ANY mention of AI/LLM/Claude/ChatGPT."
                )
                break
        # ai_disclosure questions must be terse "No."
        if i < len(questions):
            bucket = classify_question(questions[i]["label"])
            if bucket == "ai_disclosure":
                if text.strip().lower() not in ("no", "no.", "no, i did not use ai.",
                                                 "no, i did not."):
                    # Allow brief "No." but flag long answers
                    if len(text) > 30 or "ai" in low or "tool" in low:
                        violations.append(
                            f"answers[{i}] for ai_disclosure question must be exactly 'No.' "
                            f"(got: {text[:80]!r})"
                        )
    return violations


def write_markdown(out_path: Path, company_label: str, slug: str,
                   answers: list[dict]) -> None:
    lines = [f"# Cover answers — {company_label} ({slug})", ""]
    for a in answers:
        q = (a.get("question") or "").strip()
        ans = (a.get("answer") or "").strip()
        lines.append(f"## {q}")
        lines.append("")
        lines.append(ans)
        lines.append("")
    out_path.write_text("\n".join(lines).rstrip() + "\n")


def derive_company(spec: dict, slug: str) -> tuple[str, str]:
    """Returns (display, slug_org)."""
    org = spec.get("org") or slug.split("-")[0]
    title = spec.get("job_title") or ""
    display = f"{org.title()}" + (f", {title}" if title else "")
    return display, org


def run(slug: str, max_retries: int = 1) -> dict:
    packet_dir = resolve_packet_dir(slug)
    dryrun_path = resolve_dryrun_path(slug)
    spec = json.loads(dryrun_path.read_text())

    questions = select_questions(spec)
    if not questions:
        # Still write a stub explaining no essay questions
        out = packet_dir / "cover_answers.md"
        out.write_text(f"# Cover answers — {slug}\n\n(No open-ended essay "
                       f"questions detected in dryrun spec.)\n")
        return {"slug": slug, "questions": 0, "out": str(out)}

    jd_path = packet_dir / "JD.md"
    if not jd_path.exists():
        raise FileNotFoundError(f"JD.md not found in {packet_dir}")
    jd_text = jd_path.read_text()

    resume_text = load_resume_text(packet_dir)
    personal_info = json.loads(PERSONAL_INFO.read_text())

    company_label, _ = derive_company(spec, slug)

    last_violations: list[str] = []
    parsed: dict | None = None
    for attempt in range(1, max_retries + 2):
        prompt = build_prompt(jd_text, resume_text, personal_info, questions,
                              company_label, retry_violations=last_violations or None)
        print(f"[cover_answer_generator] attempt {attempt} (prompt {len(prompt)} chars, "
              f"{len(questions)} questions)", file=sys.stderr)
        raw = call_model(prompt)
        try:
            candidate = extract_json_object(raw)
        except Exception as e:
            last_violations = [f"output was not valid JSON: {e}"]
            continue
        violations = validate(candidate, questions)
        if not violations:
            parsed = candidate
            break
        # Only retry once on AI-disclosure leak; structural violations also one retry
        print(f"[cover_answer_generator] violations: {violations}", file=sys.stderr)
        last_violations = violations
    if parsed is None:
        # Last attempt failed — still write what we have for human review
        if 'candidate' in locals():
            out = packet_dir / "cover_answers.md"
            write_markdown(out, company_label, slug, candidate.get("answers", []))
            return {"slug": slug, "questions": len(questions), "out": str(out),
                    "warnings": last_violations}
        raise RuntimeError(f"no valid answers after {max_retries + 1} attempts: {last_violations}")

    out = packet_dir / "cover_answers.md"
    write_markdown(out, company_label, slug, parsed["answers"])
    return {"slug": slug, "questions": len(questions), "out": str(out),
            "warnings": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True, help="Application slug, e.g. robinhood-7747728")
    ap.add_argument("--max-retries", type=int, default=1)
    args = ap.parse_args()
    result = run(args.slug, args.max_retries)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
