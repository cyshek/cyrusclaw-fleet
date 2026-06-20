"""Tests for linkedin_db_crosslink_resolver -- DB-internal cross-source linking.

No network. Builds a tiny in-memory-ish tracker.db fixture per test and asserts
the resolver only rewrites stranded LinkedIn rows that have an UNAMBIGUOUS
same-company+title match to a direct-ATS row.
"""
import sqlite3
import json
import linkedin_db_crosslink_resolver as cl


def _make_db(tmp_path, rows):
    """rows: list of dicts with at least source_key, company, role, app_url,
    optionally status/applied_by/agent_notes. Returns the db path."""
    p = tmp_path / "tracker.db"
    con = sqlite3.connect(p)
    con.execute(
        "CREATE TABLE roles (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "source_key TEXT UNIQUE, company TEXT, role TEXT, app_url TEXT, status TEXT, "
        "applied_by TEXT, agent_notes TEXT)"
    )
    for r in rows:
        con.execute(
            "INSERT INTO roles (source_key, company, role, app_url, status, "
            "applied_by, agent_notes) VALUES (?,?,?,?,?,?,?)",
            (r.get("source_key"), r.get("company"), r.get("role"),
             r.get("app_url"), r.get("status"), r.get("applied_by"),
             r.get("agent_notes")),
        )
    con.commit()
    con.close()
    return p


def _run(db, apply=True):
    argv = ["--db", str(db), "--quiet"]
    if apply:
        argv.append("--apply")
    cl.main(argv)


# --- normalization ----------------------------------------------------------

def test_normalize_title_expands_pm_tpm():
    assert cl.normalize_title("PM, Growth") == "product manager growth"
    assert cl.normalize_title("TPM") == "technical program manager"
    assert cl.normalize_title("Product   Manager!!") == "product manager"


def test_norm_company():
    assert cl.norm_company("Foo, Inc.") == "fooinc"
    assert cl.norm_company("Net-flix") == "netflix"


# --- exact unique match resolves -------------------------------------------

def test_resolves_unique_company_title_match(tmp_path):
    db = _make_db(tmp_path, [
        {"source_key": "greenhouse:acme:1", "company": "Acme",
         "role": "Product Manager", "app_url": "https://boards.greenhouse.io/acme/jobs/1"},
        {"source_key": "linkedin:abc", "company": "Acme",
         "role": "Product Manager",
         "app_url": "https://www.linkedin.com/jobs/view/123"},
    ])
    _run(db)
    con = sqlite3.connect(db)
    li = con.execute("SELECT app_url, source_key, agent_notes FROM roles WHERE id=2").fetchone()
    # app_url rewritten to the direct-ATS URL...
    assert li[0] == "https://boards.greenhouse.io/acme/jobs/1"
    # ...but source_key PRESERVED (UNIQUE constraint; identity kept).
    assert li[1] == "linkedin:abc"
    assert "LINKEDIN-CROSSLINK" in li[2]


def test_pm_abbreviation_matches(tmp_path):
    # direct row says "Product Manager"; LinkedIn row says "PM" -> normalize match
    db = _make_db(tmp_path, [
        {"source_key": "ashby:beta:x", "company": "Beta",
         "role": "Product Manager, Core", "app_url": "https://jobs.ashbyhq.com/beta/x"},
        {"source_key": "linkedin:q", "company": "Beta",
         "role": "PM, Core", "app_url": "https://www.linkedin.com/jobs/view/9"},
    ])
    _run(db)
    con = sqlite3.connect(db)
    li = con.execute("SELECT app_url FROM roles WHERE id=2").fetchone()
    assert li[0] == "https://jobs.ashbyhq.com/beta/x"


# --- ambiguity & misses are NOT rewritten ----------------------------------

def test_ambiguous_two_distinct_urls_skipped(tmp_path):
    db = _make_db(tmp_path, [
        {"source_key": "greenhouse:acme:1", "company": "Acme",
         "role": "Product Manager", "app_url": "https://boards.greenhouse.io/acme/jobs/1"},
        {"source_key": "greenhouse:acme:2", "company": "Acme",
         "role": "Product Manager", "app_url": "https://boards.greenhouse.io/acme/jobs/2"},
        {"source_key": "linkedin:abc", "company": "Acme", "role": "Product Manager",
         "app_url": "https://www.linkedin.com/jobs/view/123"},
    ])
    _run(db)
    con = sqlite3.connect(db)
    li = con.execute("SELECT app_url FROM roles WHERE id=3").fetchone()
    # ambiguous -> left untouched (still LinkedIn)
    assert li[0] == "https://www.linkedin.com/jobs/view/123"


def test_no_direct_row_left_untouched(tmp_path):
    db = _make_db(tmp_path, [
        {"source_key": "linkedin:abc", "company": "Ghost", "role": "Product Manager",
         "app_url": "https://www.linkedin.com/jobs/view/123"},
    ])
    _run(db)
    con = sqlite3.connect(db)
    li = con.execute("SELECT app_url, agent_notes FROM roles WHERE id=1").fetchone()
    assert li[0] == "https://www.linkedin.com/jobs/view/123"
    assert li[1] is None  # not even noted


def test_closed_direct_row_not_reused(tmp_path):
    db = _make_db(tmp_path, [
        {"source_key": "greenhouse:acme:1", "company": "Acme",
         "role": "Product Manager", "app_url": "https://boards.greenhouse.io/acme/jobs/1",
         "status": "closed"},
        {"source_key": "linkedin:abc", "company": "Acme", "role": "Product Manager",
         "app_url": "https://www.linkedin.com/jobs/view/123"},
    ])
    _run(db)
    con = sqlite3.connect(db)
    li = con.execute("SELECT app_url FROM roles WHERE id=2").fetchone()
    assert li[0] == "https://www.linkedin.com/jobs/view/123"  # dead direct row not reused


def test_already_applied_linkedin_row_skipped(tmp_path):
    db = _make_db(tmp_path, [
        {"source_key": "greenhouse:acme:1", "company": "Acme",
         "role": "Product Manager", "app_url": "https://boards.greenhouse.io/acme/jobs/1"},
        {"source_key": "linkedin:abc", "company": "Acme", "role": "Product Manager",
         "app_url": "https://www.linkedin.com/jobs/view/123", "applied_by": "auto"},
    ])
    _run(db)
    con = sqlite3.connect(db)
    li = con.execute("SELECT app_url FROM roles WHERE id=2").fetchone()
    assert li[0] == "https://www.linkedin.com/jobs/view/123"  # already applied -> untouched


def test_idempotent_second_run_noop(tmp_path):
    db = _make_db(tmp_path, [
        {"source_key": "greenhouse:acme:1", "company": "Acme",
         "role": "Product Manager", "app_url": "https://boards.greenhouse.io/acme/jobs/1"},
        {"source_key": "linkedin:abc", "company": "Acme", "role": "Product Manager",
         "app_url": "https://www.linkedin.com/jobs/view/123"},
    ])
    _run(db)
    con = sqlite3.connect(db)
    first = con.execute("SELECT app_url, source_key FROM roles WHERE id=2").fetchone()
    con.close()
    _run(db)  # second run: the CROSSLINK note now excludes it
    con = sqlite3.connect(db)
    second = con.execute("SELECT app_url, source_key FROM roles WHERE id=2").fetchone()
    assert first == second


def test_dry_run_does_not_write(tmp_path):
    db = _make_db(tmp_path, [
        {"source_key": "greenhouse:acme:1", "company": "Acme",
         "role": "Product Manager", "app_url": "https://boards.greenhouse.io/acme/jobs/1"},
        {"source_key": "linkedin:abc", "company": "Acme", "role": "Product Manager",
         "app_url": "https://www.linkedin.com/jobs/view/123"},
    ])
    _run(db, apply=False)
    con = sqlite3.connect(db)
    li = con.execute("SELECT app_url, agent_notes FROM roles WHERE id=2").fetchone()
    assert li[0] == "https://www.linkedin.com/jobs/view/123"
    assert li[1] is None


# --- blocklist policy (Microsoft/Amazon skipped; Google allowed) ------------

def test_microsoft_row_not_touched(tmp_path):
    db = _make_db(tmp_path, [
        {"source_key": "microsoft:x", "company": "Microsoft",
         "role": "Product Manager",
         "app_url": "https://careers.microsoft.com/jobs/1"},
        {"source_key": "linkedin:abc", "company": "Microsoft", "role": "Product Manager",
         "app_url": "https://www.linkedin.com/jobs/view/123"},
    ])
    _run(db)
    con = sqlite3.connect(db)
    li = con.execute("SELECT app_url FROM roles WHERE id=2").fetchone()
    assert li[0] == "https://www.linkedin.com/jobs/view/123"  # Cyrus-handled, untouched


def test_google_row_is_resolved(tmp_path):
    # Google is discovery-only but in scope (un-blocked 2026-06-08), so its URL
    # should still be improved.
    db = _make_db(tmp_path, [
        {"source_key": "https://www.google.com/about/careers/applications/jobs/results/999",
         "company": "Google", "role": "Product Manager",
         "app_url": "https://www.google.com/about/careers/applications/jobs/results/999"},
        {"source_key": "linkedin:abc", "company": "Google", "role": "Product Manager",
         "app_url": "https://www.linkedin.com/jobs/view/123"},
    ])
    _run(db)
    con = sqlite3.connect(db)
    li = con.execute("SELECT app_url FROM roles WHERE id=2").fetchone()
    assert li[0].startswith("https://www.google.com/about/careers")


# --- source_key is PRESERVED (UNIQUE constraint) even when direct row stores
#     a raw-URL source_key ---

def test_raw_url_direct_source_key_still_preserves_linkedin_key(tmp_path):
    # The matched direct row stores the URL itself as source_key (a real pattern
    # for ~1200 rows). We still only rewrite app_url; the LinkedIn row keeps its
    # own unique linkedin:<id> key (copying the URL-key would also be wrong).
    db = _make_db(tmp_path, [
        {"source_key": "https://boards.greenhouse.io/securitize/jobs/417",
         "company": "Securitize", "role": "Onboarding Product Manager",
         "app_url": "https://job-boards.greenhouse.io/securitize/jobs/417"},
        {"source_key": "linkedin:abc", "company": "Securitize",
         "role": "Onboarding Product Manager",
         "app_url": "https://www.linkedin.com/jobs/view/123"},
    ])
    _run(db)
    con = sqlite3.connect(db)
    row = con.execute("SELECT app_url, source_key FROM roles WHERE id=2").fetchone()
    assert row[0] == "https://job-boards.greenhouse.io/securitize/jobs/417"
    assert row[1] == "linkedin:abc"  # preserved


def test_looks_like_canonical_source_key_helper():
    assert cl._looks_like_canonical_source_key("greenhouse:acme:1") is True
    assert cl._looks_like_canonical_source_key("ashby:beta:x") is True
    assert cl._looks_like_canonical_source_key("https://x.com/y") is False
    assert cl._looks_like_canonical_source_key("http://x") is False
    assert cl._looks_like_canonical_source_key("") is False
    assert cl._looks_like_canonical_source_key(None) is False
