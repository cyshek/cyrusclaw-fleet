"""Offline tests for the JobRight discovery adapter (adapters/jobright.py).

Parses a SAVED real __NEXT_DATA__ fixture (test_fixtures/) — NO network. Asserts:
  - field extraction (company from companyResult, title, location, posted_at)
  - source_key stability via jobId (jobright:<jobId>) through tracker_merger
  - recency field (posted_at) populated from publishTime
  - discovery-only / manual-apply tagging
  - the discovery wrapper URL shape (jobright.ai/jobs/info/<id>)
  - tracker_merger tags jobright rows manual-apply + discovery-only

Run: cd projects/job-search/role-discovery && .venv/bin/python -m pytest test_jobright_adapter.py -q
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from adapters import jobright  # noqa: E402
import tracker_merger  # noqa: E402

FIXTURE = HERE / "test_fixtures" / "jobright_product_design_next_data.json"


@pytest.fixture(scope="module")
def next_data():
    assert FIXTURE.exists(), f"fixture missing: {FIXTURE}"
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def roles(next_data):
    rs = jobright.parse_jobs(next_data)
    assert rs, "parse_jobs returned no roles from the fixture"
    return rs


def test_extracts_thirty_jobs(roles):
    # The captured fixture page held 30 listing objects.
    assert len(roles) == 30


def test_every_row_has_core_fields(roles):
    for r in roles:
        assert r.company, "company must be populated (from companyResult.companyName)"
        assert r.title, "title must be populated"
        assert r.source == "jobright"
        assert r.raw.get("job_id"), "jobId must be present"


def test_company_name_comes_from_company_result(roles):
    # jobResult.companyName is EMPTY on the public pages; the adapter must read
    # companyResult.companyName. Verify a known sample (Vivint, first item).
    companies = {r.company for r in roles}
    assert "Vivint" in companies
    # No row should fall back to an empty company.
    assert all(r.company.strip() for r in roles)


def test_recency_field_populated(roles):
    # posted_at must be derived from publishTime (date part), for every row.
    assert all(r.posted_at for r in roles), "posted_at (recency) must be populated"
    # ISO date shape YYYY-MM-DD
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", r.posted_at) for r in roles)
    # The raw publish_time should retain the full UTC timestamp for freshness.
    assert all(r.raw.get("publish_time") for r in roles)


def test_apply_link_is_wrapper(roles):
    # Discovery-only: 100% jobright.ai/jobs/info/<id> wrapper, never a direct ATS.
    for r in roles:
        assert r.url.startswith("https://jobright.ai/jobs/info/"), r.url
        # 24-hex Mongo ObjectId in the path
        assert re.search(r"/jobs/info/[0-9a-fA-F]{24}", r.url), r.url
        # tracking query stripped
        assert "?" not in r.url


def test_discovery_only_tag_on_raw(roles):
    for r in roles:
        flags = r.raw.get("flags", "")
        assert "manual-apply" in flags
        assert "discovery-only" in flags


def test_source_key_stable_via_jobid(roles):
    # tracker_merger.role_to_db_row must mint jobright:<jobId> from the wrapper
    # URL (raw is dropped at to_dict() time, mirroring the linkedin precedent),
    # and it must be idempotent (same input -> same key).
    for r in roles:
        row = tracker_merger.role_to_db_row(r.to_dict())
        expected = f"jobright:{r.raw['job_id']}"
        assert row["source_key"] == expected, (row["source_key"], expected)
        # idempotent
        row2 = tracker_merger.role_to_db_row(r.to_dict())
        assert row2["source_key"] == expected


def test_source_keys_unique_per_listing(roles):
    keys = [tracker_merger.role_to_db_row(r.to_dict())["source_key"] for r in roles]
    assert len(set(keys)) == len(keys), "source_keys must be unique per listing"
    assert all(k.startswith("jobright:") for k in keys)


def test_merger_marks_jobright_discovery_only():
    # The merger's discovery-only source set must include 'jobright' so these
    # wrapper rows never enter the auto-submit/burndown queue. We assert against
    # the actual source code (the set is an inline literal in main()).
    src = (HERE / "tracker_merger.py").read_text(encoding="utf-8")
    assert '"jobright"' in src
    # the discovery-only source set line includes jobright alongside google etc.
    m = re.search(r'in \{[^}]*"jobright"[^}]*\}', src)
    assert m, "jobright must be in the discovery-only source set"
    assert "google" in m.group(0) and "tiktok" in m.group(0)


def test_parse_jobs_handles_empty_and_malformed():
    # Robustness: no crash on empty / malformed shapes.
    assert jobright.parse_jobs({}) == []
    assert jobright.parse_jobs({"props": {}}) == []
    assert jobright.parse_jobs({"props": {"pageProps": {"defaultData": []}}}) == []
    # item missing jobResult is skipped, not fatal
    bad = {"props": {"pageProps": {"defaultData": [{"companyResult": {"companyName": "X"}}]}}}
    assert jobright.parse_jobs(bad) == []


def test_extract_next_data_roundtrip():
    html = (
        '<html><head>'
        '<script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"pageProps":{"defaultData":[]}}}'
        '</script></head></html>'
    )
    data = jobright.extract_next_data(html)
    assert data == {"props": {"pageProps": {"defaultData": []}}}
    assert jobright.extract_next_data("<html>no script</html>") is None
    assert jobright.extract_next_data("") is None


def test_default_category_slugs_present():
    # The static slug list (derived from the live sitemap) must be non-empty
    # and well-formed; these feed the weekly crawl.
    assert len(jobright.DEFAULT_CATEGORY_SLUGS) >= 10
    assert "product-design" in jobright.DEFAULT_CATEGORY_SLUGS
    assert all(re.fullmatch(r"[a-z0-9-]+", s) for s in jobright.DEFAULT_CATEGORY_SLUGS)
