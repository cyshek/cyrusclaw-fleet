"""Tests for jobright_resolve_apply.py.

All HTTP calls are mocked — NO live network in these tests.

Coverage:
  - resolve_apply_url: Greenhouse (token preserved), amazon.jobs, JobDiva, TriNetHire
  - UTM stripping (utm_source=jobright removed; token= preserved)
  - HTTP 401 → JobRightAuthError
  - success:false → None
  - Missing fields → None
  - Still-wrapper URL guard → None
  - classify_ats: greenhouse/ashby/lever/workday/rippling/bamboohr/smartrecruiters/workable/eightfold/unknown
  - run_batch: greenhouse URL -> status='' (queued); unknown/amazon host -> status='manual-apply'
  - Cookie loading: env var takes priority; falls back to file; returns None if neither
  - _extract_job_id: correct extraction and None on malformed
  - strip_utm_params: utm_source stripped, token= preserved, no-query fast path
  - dry_run: prints but does NOT write to DB

Run:
  cd projects/job-search/role-discovery
  .venv/bin/python -m pytest test_jobright_resolve_apply.py -q
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import jobright_resolve_apply as jr


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(status_code: int, body=None):
    resp = MagicMock()
    resp.status_code = status_code
    if body is not None:
        resp.json.return_value = body
    else:
        resp.json.return_value = {}
    return resp


def _success_body(job_id="abc123", original_url="", apply_link=""):
    return {
        "success": True,
        "errorCode": 10000,
        "result": {
            "jobDetail": {
                "jobResult": {
                    "jobId": job_id,
                    "jobTitle": "Solutions Architect",
                    "originalUrl": original_url,
                    "applyLink": apply_link,
                }
            }
        },
    }


def _make_db(tmp_path: Path, app_url: str = "https://jobright.ai/jobs/info/6a2b1572d3ec8317fe146faa",
             source_key: str = "jobright:6a2b1572d3ec8317fe146faa",
             status: str = "manual-apply") -> Path:
    db_path = tmp_path / "tracker.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE roles (
            id INTEGER PRIMARY KEY,
            source_key TEXT, company TEXT, role TEXT,
            status TEXT, app_url TEXT, flags TEXT,
            applied_by TEXT, applied_on TEXT,
            prep_status TEXT, agent_notes TEXT
        )
    """)
    conn.execute(
        "INSERT INTO roles (id,source_key,company,role,status,app_url) VALUES (?,?,?,?,?,?)",
        (1, source_key, "Acme Corp", "Solutions Engineer", status, app_url),
    )
    conn.commit()
    conn.close()
    return db_path


# ── classify_ats ─────────────────────────────────────────────────────────────

class TestDbPathAnchoring:
    """Regression: DB_PATH must point at the PROJECT ROOT tracker.db, not the
    role-discovery/ dir. A stale 0-byte role-discovery/tracker.db once shadowed
    the real 2.9MB DB, so the default-path resolver found 0 eligible rows and
    silently no-op'd. (bugfix 2026-06-13)"""

    def test_db_path_is_project_root_not_script_dir(self):
        # HERE = .../role-discovery ; the real DB is its PARENT / tracker.db
        assert jr.DB_PATH == jr.PROJ_DIR / "tracker.db"
        assert jr.DB_PATH.parent == jr.PROJ_DIR
        # must NOT resolve inside the script's own dir
        assert jr.DB_PATH != jr.HERE / "tracker.db"
        assert jr.DB_PATH.parent.name != "role-discovery"

    def test_session_file_also_project_root(self):
        # sibling sanity: the cookie file lives at the project root too
        assert jr.SESSION_FILE == jr.PROJ_DIR / ".jobright-session"


class TestClassifyAts:
    def test_greenhouse(self):
        assert jr.classify_ats("https://boards.greenhouse.io/acme/jobs/123456") == "greenhouse"

    def test_greenhouse_embed(self):
        assert jr.classify_ats(
            "https://boards.greenhouse.io/embed/job_app?for=acme&token=abc123456"
        ) == "greenhouse"

    def test_ashby(self):
        assert jr.classify_ats("https://jobs.ashbyhq.com/acme/abc-def-ghi-jkl-mno") == "ashby"

    def test_lever(self):
        assert jr.classify_ats("https://jobs.lever.co/acme/abc-def-1234") == "lever"

    def test_workday(self):
        assert jr.classify_ats("https://acme.wd1.myworkdayjobs.com/en-US/careers/job/123") == "workday"

    def test_workday_wd5(self):
        assert jr.classify_ats("https://bigco.wd5.myworkdayjobs.com/careers") == "workday"

    def test_rippling(self):
        assert jr.classify_ats("https://ats.rippling.com/acme/jobs/abc-123") == "rippling"

    def test_bamboohr(self):
        assert jr.classify_ats("https://acme.bamboohr.com/careers/42") == "bamboohr"

    def test_smartrecruiters(self):
        assert jr.classify_ats("https://careers.smartrecruiters.com/Acme/12345") == "smartrecruiters"

    def test_workable(self):
        assert jr.classify_ats("https://apply.workable.com/acme/j/XYZ123/") == "workable"

    def test_eightfold(self):
        assert jr.classify_ats("https://acme.eightfold.ai/careers/job/123") == "eightfold"

    def test_amazon_jobs_unknown(self):
        assert jr.classify_ats("https://www.amazon.jobs/en/jobs/12345") == "unknown"

    def test_jobdiva_unknown(self):
        assert jr.classify_ats("https://www1.jobdiva.com/portal/?a=applytoposition") == "unknown"

    def test_trinethire_unknown(self):
        assert jr.classify_ats("https://app.trinethire.com/companies/123/jobs/456") == "unknown"

    def test_jobright_wrapper_unknown(self):
        assert jr.classify_ats("https://jobright.ai/jobs/info/6a2b1572d3ec8317fe146faa") == "unknown"

    def test_empty_string_unknown(self):
        assert jr.classify_ats("") == "unknown"

    def test_none_unknown(self):
        assert jr.classify_ats(None) == "unknown"


# ── strip_utm_params ──────────────────────────────────────────────────────────

class TestStripUtmParams:
    def test_strips_utm_source(self):
        url = "https://boards.greenhouse.io/co/jobs/123?utm_source=jobright"
        assert jr.strip_utm_params(url) == "https://boards.greenhouse.io/co/jobs/123"

    def test_preserves_greenhouse_token(self):
        url = "https://boards.greenhouse.io/embed/job_app?for=acme&token=abc123&utm_source=jobright"
        result = jr.strip_utm_params(url)
        assert "token=abc123" in result
        assert "utm_source" not in result

    def test_preserves_non_utm_params(self):
        url = "https://www.amazon.jobs/en/jobs/123?utm_source=jobright&mode=job_posting"
        result = jr.strip_utm_params(url)
        assert "mode=job_posting" in result
        assert "utm_source" not in result

    def test_no_query_fastpath(self):
        url = "https://example.com/jobs/apply"
        assert jr.strip_utm_params(url) == url

    def test_empty_string(self):
        assert jr.strip_utm_params("") == ""

    def test_strips_utm_medium_and_campaign(self):
        url = "https://jobs.lever.co/co/abc?utm_medium=board&utm_campaign=x"
        result = jr.strip_utm_params(url)
        assert "utm_medium" not in result
        assert "utm_campaign" not in result

    def test_strips_utm_id_and_ref(self):
        url = "https://jobs.ashbyhq.com/co/abc?utm_id=123&ref=jobright&other=keep"
        result = jr.strip_utm_params(url)
        assert "utm_id" not in result
        assert "ref=" not in result
        assert "other=keep" in result


# ── resolve_apply_url: success cases ─────────────────────────────────────────

class TestResolveApplyUrlSuccess:
    SESSION = "test-session-id-abc"

    @patch("jobright_resolve_apply._session")
    def test_greenhouse_url_with_token_preserved(self, mock_session):
        gh_url = "https://boards.greenhouse.io/embed/job_app?for=acme&token=TOKEN123&utm_source=jobright"
        mock_session.get.return_value = _mock_response(200, _success_body("jid1", original_url=gh_url))
        result = jr.resolve_apply_url("jid1", self.SESSION)
        assert result is not None
        assert "token=TOKEN123" in result
        assert "utm_source" not in result
        assert "greenhouse.io" in result

    @patch("jobright_resolve_apply._session")
    def test_amazon_jobs_url(self, mock_session):
        amz_url = "https://www.amazon.jobs/en/jobs/2888000?utm_source=jobright"
        mock_session.get.return_value = _mock_response(200, _success_body("jid2", original_url=amz_url))
        result = jr.resolve_apply_url("jid2", self.SESSION)
        assert result is not None
        assert "amazon.jobs" in result
        assert "utm_source" not in result

    @patch("jobright_resolve_apply._session")
    def test_jobdiva_url(self, mock_session):
        jdv_url = "https://www1.jobdiva.com/portal/?a=applytoposition&jobid=999"
        mock_session.get.return_value = _mock_response(200, _success_body("jid3", original_url=jdv_url))
        result = jr.resolve_apply_url("jid3", self.SESSION)
        assert result is not None
        assert "jobdiva.com" in result

    @patch("jobright_resolve_apply._session")
    def test_trinethire_url(self, mock_session):
        tri_url = "https://app.trinethire.com/companies/123/jobs/456"
        mock_session.get.return_value = _mock_response(200, _success_body("jid4", original_url=tri_url))
        result = jr.resolve_apply_url("jid4", self.SESSION)
        assert result is not None
        assert "trinethire.com" in result

    @patch("jobright_resolve_apply._session")
    def test_fallback_to_apply_link_when_original_url_missing(self, mock_session):
        """When originalUrl is empty, uses applyLink."""
        body = _success_body("jid5", original_url="", apply_link="https://jobs.lever.co/co/abc")
        mock_session.get.return_value = _mock_response(200, body)
        result = jr.resolve_apply_url("jid5", self.SESSION)
        assert result is not None
        assert "lever.co" in result

    @patch("jobright_resolve_apply._session")
    def test_request_uses_session_cookie(self, mock_session):
        mock_session.get.return_value = _mock_response(
            200, _success_body("jidX", original_url="https://jobs.ashbyhq.com/co/uuid")
        )
        jr.resolve_apply_url("jidX", "MY_SESSION_ID")
        headers = mock_session.get.call_args.kwargs.get("headers", {})
        assert "SESSION_ID=MY_SESSION_ID" in headers.get("Cookie", "")


# ── resolve_apply_url: error / edge cases ─────────────────────────────────────

class TestResolveApplyUrlErrors:
    SESSION = "test-session-id-abc"

    @patch("jobright_resolve_apply._session")
    def test_401_raises_auth_error(self, mock_session):
        mock_session.get.return_value = _mock_response(401)
        with pytest.raises(jr.JobRightAuthError, match="401"):
            jr.resolve_apply_url("jidA", self.SESSION)

    @patch("jobright_resolve_apply._session")
    def test_403_raises_auth_error(self, mock_session):
        mock_session.get.return_value = _mock_response(403)
        with pytest.raises(jr.JobRightAuthError, match="403"):
            jr.resolve_apply_url("jidB", self.SESSION)

    @patch("jobright_resolve_apply._session")
    def test_success_false_returns_none(self, mock_session):
        body = {"success": False, "errorCode": 10000, "result": None}
        mock_session.get.return_value = _mock_response(200, body)
        assert jr.resolve_apply_url("jidC", self.SESSION) is None

    @patch("jobright_resolve_apply._session")
    def test_missing_result_returns_none(self, mock_session):
        body = {"success": True, "errorCode": 10000, "result": {}}
        mock_session.get.return_value = _mock_response(200, body)
        assert jr.resolve_apply_url("jidD", self.SESSION) is None

    @patch("jobright_resolve_apply._session")
    def test_missing_job_result_returns_none(self, mock_session):
        body = {"success": True, "errorCode": 10000, "result": {"jobDetail": {}}}
        mock_session.get.return_value = _mock_response(200, body)
        assert jr.resolve_apply_url("jidE", self.SESSION) is None

    @patch("jobright_resolve_apply._session")
    def test_empty_urls_returns_none(self, mock_session):
        body = _success_body("jidF", original_url="", apply_link="")
        mock_session.get.return_value = _mock_response(200, body)
        assert jr.resolve_apply_url("jidF", self.SESSION) is None

    @patch("jobright_resolve_apply._session")
    def test_still_wrapper_url_returns_none(self, mock_session):
        """API returns a jobright.ai URL even when authed — guard returns None."""
        body = _success_body("jidG", original_url="https://jobright.ai/jobs/info/6a2b1572d3ec8317fe146faa")
        mock_session.get.return_value = _mock_response(200, body)
        assert jr.resolve_apply_url("jidG", self.SESSION) is None

    @patch("jobright_resolve_apply._session")
    def test_non_json_response_raises_resolve_error(self, mock_session):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("Expecting value")
        mock_session.get.return_value = resp
        with pytest.raises(jr.JobRightResolveError, match="Non-JSON"):
            jr.resolve_apply_url("jidH", self.SESSION)

    @patch("jobright_resolve_apply._session")
    def test_network_error_raises_resolve_error(self, mock_session):
        import requests as req_lib
        mock_session.get.side_effect = req_lib.ConnectionError("timeout")
        with pytest.raises(jr.JobRightResolveError, match="Network error"):
            jr.resolve_apply_url("jidI", self.SESSION)

    @patch("jobright_resolve_apply._session")
    def test_unexpected_http_status_raises_resolve_error(self, mock_session):
        mock_session.get.return_value = _mock_response(500)
        with pytest.raises(jr.JobRightResolveError, match="500"):
            jr.resolve_apply_url("jidJ", self.SESSION)

    @patch("jobright_resolve_apply._session")
    def test_error_code_10001_raises_auth_error(self, mock_session):
        body = {"success": False, "errorCode": 10001, "result": None}
        mock_session.get.return_value = _mock_response(200, body)
        with pytest.raises(jr.JobRightAuthError, match="10001"):
            jr.resolve_apply_url("jidK", self.SESSION)


# ── _extract_job_id ───────────────────────────────────────────────────────────

class TestExtractJobId:
    def test_extracts_valid(self):
        assert jr._extract_job_id("jobright:6a2b1572d3ec8317fe146faa") == "6a2b1572d3ec8317fe146faa"

    def test_non_jobright_key(self):
        assert jr._extract_job_id("greenhouse:boards.greenhouse.io/co/jobs/123") is None

    def test_empty(self):
        assert jr._extract_job_id("") is None

    def test_none(self):
        assert jr._extract_job_id(None) is None


# ── load_session_id ───────────────────────────────────────────────────────────

class TestLoadSessionId:
    def test_env_var_takes_priority(self, tmp_path, monkeypatch):
        monkeypatch.setenv("JOBRIGHT_SESSION_ID", "env-session-val")
        session_file = tmp_path / ".jobright-session"
        session_file.write_text("file-session-val")
        monkeypatch.setattr(jr, "SESSION_FILE", session_file)
        assert jr.load_session_id() == "env-session-val"

    def test_falls_back_to_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("JOBRIGHT_SESSION_ID", raising=False)
        session_file = tmp_path / ".jobright-session"
        session_file.write_text("file-session-val\n")
        monkeypatch.setattr(jr, "SESSION_FILE", session_file)
        assert jr.load_session_id() == "file-session-val"

    def test_returns_none_if_neither(self, tmp_path, monkeypatch):
        monkeypatch.delenv("JOBRIGHT_SESSION_ID", raising=False)
        monkeypatch.setattr(jr, "SESSION_FILE", tmp_path / ".nonexistent")
        assert jr.load_session_id() is None

    def test_strips_whitespace_from_env(self, monkeypatch):
        monkeypatch.setenv("JOBRIGHT_SESSION_ID", "  trimmed-val  ")
        assert jr.load_session_id() == "trimmed-val"

    def test_empty_env_falls_through_to_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("JOBRIGHT_SESSION_ID", "")
        session_file = tmp_path / ".jobright-session"
        session_file.write_text("file-only")
        monkeypatch.setattr(jr, "SESSION_FILE", session_file)
        assert jr.load_session_id() == "file-only"


# ── run_batch host-classification routing ─────────────────────────────────────

class TestRunBatchClassification:
    """Key invariant: known-ATS -> status=''; unknown -> status='manual-apply'."""

    @patch("jobright_resolve_apply._session")
    def test_greenhouse_url_sets_status_to_empty(self, mock_session, tmp_path):
        """Greenhouse resolved URL -> status='' (enters auto-submit queue)."""
        gh_url = "https://boards.greenhouse.io/embed/job_app?for=acme&token=TOKEN123"
        mock_session.get.return_value = _mock_response(
            200, _success_body("6a2b1572d3ec8317fe146faa", original_url=gh_url)
        )
        db_path = _make_db(tmp_path)
        result = jr.run_batch("test-session", db_path=db_path)
        assert result["resolved_auto"] == 1
        assert result["resolved_manual"] == 0
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT status, app_url FROM roles WHERE id=1").fetchone()
        conn.close()
        assert row[0] == "", f"Expected status='', got {row[0]!r}"
        assert "greenhouse.io" in row[1]

    @patch("jobright_resolve_apply._session")
    def test_unknown_ats_host_keeps_manual_apply_status(self, mock_session, tmp_path):
        """Amazon.jobs (unknown ATS) -> status stays 'manual-apply', url updated."""
        amz_url = "https://www.amazon.jobs/en/jobs/2888000"
        mock_session.get.return_value = _mock_response(
            200, _success_body("6a2b1572d3ec8317fe146faa", original_url=amz_url)
        )
        db_path = _make_db(tmp_path)
        result = jr.run_batch("test-session", db_path=db_path)
        assert result["resolved_manual"] == 1
        assert result["resolved_auto"] == 0
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT status, app_url FROM roles WHERE id=1").fetchone()
        conn.close()
        assert row[0] == "manual-apply"
        assert "amazon.jobs" in row[1]

    @patch("jobright_resolve_apply._session")
    def test_dry_run_does_not_write_to_db(self, mock_session, tmp_path):
        """dry_run=True must not modify tracker.db."""
        gh_url = "https://boards.greenhouse.io/acme/jobs/9999"
        mock_session.get.return_value = _mock_response(
            200, _success_body("6a2b1572d3ec8317fe146faa", original_url=gh_url)
        )
        db_path = _make_db(tmp_path)
        result = jr.run_batch("test-session", dry_run=True, db_path=db_path)
        assert result["resolved_auto"] == 1
        # DB must be unchanged
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT status, app_url FROM roles WHERE id=1").fetchone()
        conn.close()
        assert row[0] == "manual-apply"
        assert "jobright.ai" in row[1]

    @patch("jobright_resolve_apply._session")
    def test_idempotent_skips_already_resolved(self, mock_session, tmp_path):
        """Rows with a non-jobright.ai app_url are not re-processed."""
        db_path = _make_db(
            tmp_path,
            app_url="https://boards.greenhouse.io/acme/jobs/9999",
            status="",
        )
        result = jr.run_batch("test-session", db_path=db_path)
        assert result["eligible"] == 0
        mock_session.get.assert_not_called()

    @patch("jobright_resolve_apply._session")
    def test_auth_error_aborts_batch(self, mock_session, tmp_path):
        """JobRightAuthError aborts the entire batch immediately."""
        mock_session.get.return_value = _mock_response(401)
        db_path = _make_db(tmp_path)
        result = jr.run_batch("bad-session", db_path=db_path)
        assert any(e["error"] == "auth-fail" for e in result["errors"])

    @patch("jobright_resolve_apply._session")
    def test_no_url_counts_as_failed(self, mock_session, tmp_path):
        """API success:false -> failed counter, no DB write."""
        body = {"success": False, "errorCode": 10000, "result": None}
        mock_session.get.return_value = _mock_response(200, body)
        db_path = _make_db(tmp_path)
        result = jr.run_batch("test-session", db_path=db_path)
        assert result["failed"] == 1
        assert result["resolved_auto"] == 0
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT status FROM roles WHERE id=1").fetchone()
        conn.close()
        assert row[0] == "manual-apply"

    @patch("jobright_resolve_apply._session")
    def test_ashby_url_sets_status_to_empty(self, mock_session, tmp_path):
        ashby_url = "https://jobs.ashbyhq.com/acme/abc-def-1234-5678-uuid"
        mock_session.get.return_value = _mock_response(
            200, _success_body("6a2b1572d3ec8317fe146faa", original_url=ashby_url)
        )
        db_path = _make_db(tmp_path)
        result = jr.run_batch("test-session", db_path=db_path)
        assert result["resolved_auto"] == 1

    @patch("jobright_resolve_apply._session")
    def test_lever_url_sets_status_to_empty(self, mock_session, tmp_path):
        lever_url = "https://jobs.lever.co/acme/abc-123-def"
        mock_session.get.return_value = _mock_response(
            200, _success_body("6a2b1572d3ec8317fe146faa", original_url=lever_url)
        )
        db_path = _make_db(tmp_path)
        result = jr.run_batch("test-session", db_path=db_path)
        assert result["resolved_auto"] == 1


# ── _eligible_rows filtering ──────────────────────────────────────────────────

class TestEligibleRowsFilter:

    def test_only_eligible_rows_selected(self, tmp_path):
        db_path = tmp_path / "tracker.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY, source_key TEXT, company TEXT,
                role TEXT, status TEXT, app_url TEXT, flags TEXT,
                applied_by TEXT, applied_on TEXT, prep_status TEXT, agent_notes TEXT
            )
        """)
        rows = [
            # eligible
            (1, "jobright:aaa", "Co A", "Role A", "manual-apply", "https://jobright.ai/jobs/info/aaa"),
            # ineligible: already resolved
            (2, "jobright:bbb", "Co B", "Role B", "manual-apply", "https://boards.greenhouse.io/co/jobs/999"),
            # ineligible: wrong status
            (3, "jobright:ccc", "Co C", "Role C", "", "https://jobright.ai/jobs/info/ccc"),
            # ineligible: not jobright source
            (4, "linkedin:12345", "Co D", "Role D", "manual-apply", "https://jobright.ai/jobs/info/ddd"),
        ]
        conn.executemany(
            "INSERT INTO roles (id,source_key,company,role,status,app_url) VALUES (?,?,?,?,?,?)", rows
        )
        conn.commit()
        eligible = jr._eligible_rows(conn)
        conn.close()
        assert len(eligible) == 1
        assert eligible[0]["id"] == 1

    def test_limit_respected(self, tmp_path):
        db_path = tmp_path / "tracker.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY, source_key TEXT, company TEXT,
                role TEXT, status TEXT, app_url TEXT, flags TEXT,
                applied_by TEXT, applied_on TEXT, prep_status TEXT, agent_notes TEXT
            )
        """)
        for i in range(5):
            conn.execute(
                "INSERT INTO roles (id,source_key,company,role,status,app_url) VALUES (?,?,?,?,?,?)",
                (i+1, f"jobright:id{i}", f"Co{i}", f"Role{i}", "manual-apply",
                 f"https://jobright.ai/jobs/info/id{i}"),
            )
        conn.commit()
        eligible = jr._eligible_rows(conn, limit=3)
        conn.close()
        assert len(eligible) == 3

    def test_empty_db(self, tmp_path):
        db_path = tmp_path / "tracker.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY, source_key TEXT, company TEXT,
                role TEXT, status TEXT, app_url TEXT, flags TEXT,
                applied_by TEXT, applied_on TEXT, prep_status TEXT, agent_notes TEXT
            )
        """)
        conn.commit()
        eligible = jr._eligible_rows(conn)
        conn.close()
        assert eligible == []
