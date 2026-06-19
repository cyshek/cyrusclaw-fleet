#!/usr/bin/env python3
"""Helper: produce an enriched submit plan for a slug.

Reads:
  - applications/dryrun/<dryrun>.json (via cover_answer_generator's resolver)
  - applications/queued/<slug>/cover_answers.md
  - applications/queued/<slug>/Cyrus_Shekari_Resume_*_v2.pdf

Outputs a JSON plan to stdout with:
  - url
  - text_fields (with cover answers injected for matching question IDs)
  - dropdowns
  - country_dropdowns
  - phone_iti
  - needs_review_dropdowns
  - resume_path (tailored PDF, copied to /tmp/openclaw/uploads/)
  - declined_demo
  - cover_questions_matched: list of (qid, question, answer_chars)
  - cover_questions_unmatched: list of question texts that couldn't be mapped
  - essay_textareas: extra essay textareas in the dryrun whose label matched a cover answer
"""
from __future__ import annotations
import json, sys, re, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cover_answer_generator import resolve_packet_dir, resolve_dryrun_path  # type: ignore
from greenhouse_filler import build_plan  # type: ignore

UPLOADS = Path("/tmp/openclaw/uploads")


def parse_cover_md(md: str) -> list[dict]:
    """Return list of {question, answer}."""
    out = []
    blocks = re.split(r"^## ", md, flags=re.M)
    for b in blocks[1:]:  # skip the H1 preamble
        lines = b.strip().splitlines()
        if not lines:
            continue
        q = lines[0].strip()
        ans = "\n".join(lines[1:]).strip()
        if ans:
            out.append({"question": q, "answer": ans})
    return out


def normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).strip()


def match_cover_to_field(cover_q: str, fields: list[dict]) -> str | None:
    """Find the field id whose label best matches the cover question."""
    cq_norm = normalize(cover_q)
    cq_words = set(cq_norm.split())
    best_id, best_score = None, 0.0
    for f in fields:
        lbl = f.get("label") or ""
        ftype = f.get("type") or ""
        if ftype not in ("input_text", "textarea"):
            continue
        lbl_norm = normalize(lbl)
        if not lbl_norm:
            continue
        # Exact substring containment is strongest
        if cq_norm in lbl_norm or lbl_norm in cq_norm:
            score = 1.0
        else:
            lbl_words = set(lbl_norm.split())
            inter = cq_words & lbl_words
            score = len(inter) / max(1, len(cq_words | lbl_words))
        if score > best_score:
            best_score, best_id = score, f.get("id")
    if best_score >= 0.5:
        return best_id
    return None


def stage_resume(packet_dir: Path) -> Path:
    pdfs = sorted(packet_dir.glob("Cyrus_Shekari_Resume_*_v2.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"no tailored resume PDF in {packet_dir}")
    src = pdfs[0]
    UPLOADS.mkdir(parents=True, exist_ok=True)
    dst = UPLOADS / src.name
    shutil.copy2(src, dst)
    return dst


def main():
    slug = sys.argv[1]
    packet_dir = resolve_packet_dir(slug)
    dryrun_path = resolve_dryrun_path(slug)
    spec = json.loads(dryrun_path.read_text())
    plan = build_plan(spec)

    # Stage tailored resume
    pdf = stage_resume(packet_dir)
    plan["resume_path"] = str(pdf)

    # Inject cover answers
    cover_path = packet_dir / "cover_answers.md"
    cover = parse_cover_md(cover_path.read_text()) if cover_path.exists() else []
    matched, unmatched = [], []
    fields_by_id = {f["id"]: f for f in spec["fields"]}
    for c in cover:
        qid = match_cover_to_field(c["question"], spec["fields"])
        if qid:
            plan["text_fields"][qid] = c["answer"]
            matched.append({"qid": qid, "question": c["question"][:80],
                            "answer_chars": len(c["answer"]),
                            "field_label": fields_by_id.get(qid, {}).get("label", "")[:80]})
        else:
            unmatched.append(c["question"][:120])

    plan["cover_questions_matched"] = matched
    plan["cover_questions_unmatched"] = unmatched
    plan["slug"] = slug
    plan["dryrun_path"] = str(dryrun_path)
    print(json.dumps(plan, indent=2, default=str))


if __name__ == "__main__":
    main()
