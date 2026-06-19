import inline_submit as s

def test_parse_gh_embed_for_token():
    u = "https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7923047"
    assert s.parse_gh_url(u) == ("stripe", "7923047")
    assert s.detect_ats(u) == "greenhouse"

def test_parse_gh_embed_token_first():
    u = "https://boards.greenhouse.io/embed/job_app?token=123&for=acme"
    assert s.parse_gh_url(u) == ("acme", "123")

def test_parse_gh_classic_still_works():
    assert s.parse_gh_url("https://job-boards.greenhouse.io/stripe/jobs/7923047") == ("stripe", "7923047")
