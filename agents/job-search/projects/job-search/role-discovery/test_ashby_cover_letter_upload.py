"""Tests for the Ashby cover-letter-upload helpers added 2026-06-09 for the
Cinder 2588 cohort (`upload_cover_letter_if_required` support functions).

The live Ashby form's required 'Cover Letter' FILE input is never enumerated by
the static dryrun (needs_essay=0) yet the server bounces submit with
'Missing entry for required field: Cover Letter'. The fix detects the input,
generates a tailored PDF, and uploads it via an [id="..."] attribute selector
(Ashby file-input UUIDs start with a digit -> invalid `#id` selector). These
tests cover the pure helpers (the browser path is exercised live).
"""
import _ashby_runner as a


def test_infer_company_from_plain_slug():
    assert a._infer_company_from_slug("cinder-2c483a08-7d94-4901-babb-5cbd880ce949") == "Cinder"


def test_infer_company_strips_ashby_prefix():
    assert a._infer_company_from_slug("ashby-cinder_2c483a08") == "Cinder"
    assert a._infer_company_from_slug("ashby_speak-abc123") == "Speak"


def test_infer_company_empty_fallback():
    assert a._infer_company_from_slug("") == "the company"


def test_helper_is_callable():
    assert callable(a.upload_cover_letter_if_required)


if __name__ == "__main__":
    import sys
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {fn.__name__}: {exc}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
