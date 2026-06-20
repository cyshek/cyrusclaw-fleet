"""Cyrus directive 2026-05-31: NEVER skip a "why do you want to work for
<company>" essay — fabricate a motivational answer instead of dropping the
field. Tests the label detector, the deterministic fallback, and the
merge-leftover backfill path in inline_submit.
"""
import sys, os
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import inline_submit as I


def test_why_company_label_detects_canonical_phrasings():
    yes = [
        "Why do you want to work for Acme?",
        "Why are you interested in this role?",
        "Why this company?",
        "Why us?",
        "What excites you most about joining us?",
        "What interests you about Thought Machine?",
        "What draws you to our team?",
        "Why do you want to join Acme?",
    ]
    for lbl in yes:
        assert I._is_why_company_label(lbl), f"should detect: {lbl}"


def test_why_company_label_ignores_non_motivational():
    no = [
        "Upload your resume",
        "What is your current salary expectation?",
        "First name",
        "How did you hear about us?",
        "",
    ]
    for lbl in no:
        assert not I._is_why_company_label(lbl), f"should NOT detect: {lbl}"


def test_fallback_never_empty_when_model_fails(monkeypatch):
    # Force the LLM path to fail so we exercise the deterministic template.
    def boom(*a, **k):
        raise RuntimeError("model offline")
    monkeypatch.setattr(I.subprocess, "run", boom)
    ans = I._fallback_why_company_answer(
        {"slug": "acme-123"},
        {"org": "acme", "job_title": "Forward Deployed Engineer"},
        "Why do you want to work for Acme?",
    )
    assert ans and len(ans.strip()) > 100
    assert "Acme" in ans
    low = ans.lower()
    # never leaks AI disclaimers
    for bad in ("as an ai", "language model", "claude", "chatgpt"):
        assert bad not in low


def test_fallback_uses_model_output_when_available(monkeypatch):
    class P:
        returncode = 0
        stdout = '{"outputs":[{"text":"Real generated why-company answer here, two paragraphs."}]}'
        stderr = ""
    monkeypatch.setattr(I.subprocess, "run", lambda *a, **k: P())
    ans = I._fallback_why_company_answer({"slug": "x-1"}, {"org": "x"}, "Why us?")
    assert ans == "Real generated why-company answer here, two paragraphs."


def test_leftover_essays_are_backfilled_not_dropped(monkeypatch):
    # Force deterministic fallback (no live model). The merge routes all
    # unfilled answerable essays through _fallback_essay_answer.
    def fake(plan, spec, label):
        return ("WHY-ANSWER" if I._is_why_company_label(label)
                else "ESSAY-ANSWER")
    monkeypatch.setattr(I, "_fallback_essay_answer", fake)
    # Build a minimal plan/spec mimicking the merge-leftover state: one
    # why-company essay, one general essay, and one PII field that must NOT
    # be answered with prose.
    plan = {
        "slug": "acme-123",
        "text_fields": {
            "fid_why": "<<why_company>>",
            "fid_other": "<<some_other_essay>>",
            "fid_email": "<<email>>",
        },
    }
    spec = {
        "org": "acme",
        "fields": [
            {"id": "fid_why", "label": "Why do you want to work for Acme?"},
            {"id": "fid_other", "label": "Describe a hard technical problem you solved"},
            {"id": "fid_email", "label": "Email address"},
        ],
    }
    import tempfile, pathlib
    with tempfile.TemporaryDirectory() as d:
        cover = pathlib.Path(d) / "cover_answers.md"
        cover.write_text("# none\n")  # no matching ## headings
        out = I.merge_cover_answers_into_plan(plan, spec, cover)
    # why-company essay backfilled:
    assert out["text_fields"].get("fid_why") == "WHY-ANSWER"
    # general essay ALSO backfilled now (answer everything a company asks):
    assert out["text_fields"].get("fid_other") == "ESSAY-ANSWER"
    # PII field left untouched (never fabricate prose into email/name/etc.):
    assert out["text_fields"].get("fid_email") == "<<email>>"
    # override source tags recorded:
    srcs = {o.get("source") for o in out.get("cover_overrides", [])}
    assert "why_company_fallback" in srcs
    assert "essay_fallback" in srcs


def test_answerable_essay_label_excludes_pii_and_structured():
    yes = [
        "Describe a hard technical problem you solved",
        "What is your management philosophy",
        "Your superpower",
        "Tell us something interesting",
        "Why do you want to work for Acme?",
    ]
    no = [
        "Email address", "First name", "LinkedIn URL", "Desired salary",
        "Are you authorized to work in the US", "Visa sponsorship",
        "How did you hear about us", "Resume", "ab",
    ]
    for lbl in yes:
        assert I._is_answerable_essay_label(lbl), f"should answer: {lbl}"
    for lbl in no:
        assert not I._is_answerable_essay_label(lbl), f"should NOT answer: {lbl}"


def test_answerable_essay_excludes_knockout_questions():
    # Integrity red line #3: location/relocation/clearance knockouts must be
    # answered TRUTHFULLY by the integrity-aware path, never fabricated here.
    knockouts = [
        "Are you currently located in the NYC metro area?",
        "Are you willing to relocate to San Francisco?",
        "Do you have an active security clearance?",
        "What is your current location?",
        "Which city do you live in?",
        "Where are you based?",
    ]
    for lbl in knockouts:
        assert not I._is_answerable_essay_label(lbl), f"knockout must NOT be fabricated: {lbl}"


def test_fallback_essay_routes_why_company(monkeypatch):
    monkeypatch.setattr(I, "_fallback_why_company_answer",
                        lambda plan, spec, label: "ROUTED-WHY")
    out = I._fallback_essay_answer({"slug": "x-1"}, {"org": "x"},
                                   "Why this company?")
    assert out == "ROUTED-WHY"


def test_fallback_essay_never_empty_when_model_fails(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("model offline")
    monkeypatch.setattr(I.subprocess, "run", boom)
    out = I._fallback_essay_answer(
        {"slug": "acme-1"}, {"org": "acme", "job_title": "PM"},
        "Describe a hard technical problem you solved")
    assert out and len(out.strip()) > 60
    low = out.lower()
    for bad in ("as an ai", "language model", "claude", "chatgpt"):
        assert bad not in low
