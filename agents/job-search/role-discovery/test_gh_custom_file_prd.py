"""Tests for the GH required-custom-file (PRD/product-brief) auto-fill path
shipped 2026-06-10 (ACLU 2660/2661/2662 cohort).

Pure: exercises the greenhouse_dryrun product_brief_file resolver + LABEL_RULES
match and the _gh_submit module surface. No browser / no LLM.
"""
import greenhouse_dryrun as gd
import _gh_submit as gs


def _personal():
    import json
    return json.loads(gd.PERSONAL_INFO_PATH.read_text())


def test_prd_label_rules_match_product_brief_file():
    rules = dict(gd.LABEL_RULES)
    # the ACLU phrasing must route to product_brief_file
    label = "please attach a prd or product brief for a product you've launched before."
    matched = None
    for needle, key in gd.LABEL_RULES:
        if needle in label:
            matched = key
            break
    assert matched == "product_brief_file", f"got {matched}"


def test_product_brief_resolver_input_file_is_nonblocking():
    p = _personal()
    fld = {"type": "input_file", "required": True}
    status, value, source = gd.r_product_brief_file(p, fld)
    assert status == "ok"  # NOT unresolved -> not a blocker
    assert "prd_brief_pdf" in value or "auto-generate" in value


def test_product_brief_resolver_text_fallback_is_truthful():
    p = _personal()
    fld = {"type": "textarea", "required": True}
    status, value, source = gd.r_product_brief_file(p, fld)
    assert status == "ok"
    # text fallback references a real resume product, no fabrication markers
    assert "Resilience Automation Platform" in value


def test_resolver_registered():
    assert "product_brief_file" in gd.RESOLVERS
    assert gd.RESOLVERS["product_brief_file"] is gd.r_product_brief_file


def test_gh_submit_exposes_custom_file_helpers():
    assert hasattr(gs, "detect_custom_required_file_inputs")
    assert hasattr(gs, "upload_custom_required_file")
