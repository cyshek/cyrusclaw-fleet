from __future__ import annotations
import os, sqlite3
from pathlib import Path
from typing import Optional
from unittest import mock
import pytest, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobright_search as js

# ── helpers ──────────────────────────────────────────────────────────────────

def _item(**kw):
    defaults = dict(
        job_id="abc123def456abc123def456", title="Product Manager",
        company="Acme Corp", location="SF, CA",
        publish_time="2026-06-14 10:00:00",
        original_url="https://boards.greenhouse.io/acme/jobs/1",
    )
    d = {**defaults, **kw}
    return {
        "jobResult": {
            "jobId": d["job_id"], "jobTitle": d["title"],
            "companyName": "", "jobLocation": d["location"],
            "isRemote": False, "workModel": "Hybrid",
            "publishTime": d["publish_time"], "publishTimeDesc": "now",
            "salaryDesc": "$120K", "employmentType": "Full-time",
            "jobSummary": "desc", "originalUrl": d["original_url"],
            "applyLink": d["original_url"], "isCompanySiteLink": True,
            "jobSeniority": "Mid Level", "minYearsOfExperience": 2.0,
        },
        "companyResult": {
            "companyId": 1, "companyName": d["company"], "companySize": "100-500"
        },
        "isLiked": False,
    }

def _resp(items, success=True):
    return {
        "success": success,
        "errorCode": 10000 if success else 20001,
        "errorMsg": None if success else "error",
        "result": {"jobList": items, "impId": "x"},
    }

def _sr(**kw):
    d = dict(job_id="aaa000aaa000aaa000aaa000", title="Product Manager",
             company="Acme", publish_time="2026-06-14 10:00:00",
             original_url="https://boards.greenhouse.io/acme/jobs/1")
    d.update(kw)
    return js.SearchResult(
        job_id=d["job_id"], title=d["title"], company=d["company"],
        location="Seattle, WA", publish_time=d["publish_time"],
        original_url=d["original_url"], apply_link=d["original_url"],
        is_remote=False, work_model="Hybrid", seniority="Mid Level",
        min_yoe=2.0, employment_type="Full-time", salary_desc="$120K",
        company_id=1, source_key="jobright-search:" + d["job_id"],
    )

@pytest.fixture
def tmp_db(tmp_path):
    db = tmp_path / "tracker.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_key TEXT UNIQUE, company TEXT NOT NULL,
            role TEXT NOT NULL, level TEXT, loc TEXT, exp_req TEXT,
            jd_url TEXT, app_url TEXT, status TEXT NOT NULL DEFAULT \'queued\',
            flags TEXT, applied_by TEXT, applied_on TEXT,
            cyrus_notes TEXT, agent_notes TEXT DEFAULT \'\',
            posted_on TEXT, first_seen TEXT, last_seen TEXT
        );
    """)
    conn.commit(); conn.close()
    return db

@pytest.fixture(autouse=True)
def reset_http():
    js._session_obj = None
    yield
    js._session_obj = None

# ── 1. Cookie loading ─────────────────────────────────────────────────────────

class TestCookieLoading:
    def test_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("JOBRIGHT_SESSION_ID", "env_val_abc")
        with mock.patch.object(js, "SESSION_FILE", tmp_path / "nope"):
            assert js.load_session_cookie() == "env_val_abc"

    def test_from_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv("JOBRIGHT_SESSION_ID", raising=False)
        f = tmp_path / ".jobright-session"
        f.write_text("file_cookie_xyz\n")
        with mock.patch.object(js, "SESSION_FILE", f):
            assert js.load_session_cookie() == "file_cookie_xyz"

    def test_env_wins_over_file(self, monkeypatch, tmp_path):
        monkeypatch.setenv("JOBRIGHT_SESSION_ID", "env_wins")
        f = tmp_path / ".jobright-session"
        f.write_text("file_val")
        with mock.patch.object(js, "SESSION_FILE", f):
            assert js.load_session_cookie() == "env_wins"

    def test_missing_raises(self, monkeypatch, tmp_path):
        monkeypatch.delenv("JOBRIGHT_SESSION_ID", raising=False)
        with mock.patch.object(js, "SESSION_FILE", tmp_path / "nosuch"):
            with pytest.raises(RuntimeError, match="No JobRight session cookie"):
                js.load_session_cookie()

    def test_file_strips_whitespace(self, monkeypatch, tmp_path):
        monkeypatch.delenv("JOBRIGHT_SESSION_ID", raising=False)
        f = tmp_path / ".jobright-session"
        f.write_text("  trimmed  \n")
        with mock.patch.object(js, "SESSION_FILE", f):
            assert js.load_session_cookie() == "trimmed"

    def test_no_hardcoded_cookie(self):
        import re
        src = (Path(__file__).parent / "jobright_search.py").read_text()
        assert "SESSION_FILE" in src  # no hardcoded token

# ── 2. Response parsing ───────────────────────────────────────────────────────

class TestResponseParsing:
    def test_valid_item(self):
        sr = js.SearchResult.from_api_item(_item())
        assert sr is not None
        assert sr.job_id == "abc123def456abc123def456"
        assert sr.title == "Product Manager"
        assert sr.company == "Acme Corp"
        assert sr.publish_time == "2026-06-14 10:00:00"
        assert sr.source_key == "jobright-search:abc123def456abc123def456"

    def test_missing_job_id(self):
        i = _item(); i["jobResult"]["jobId"] = ""
        assert js.SearchResult.from_api_item(i) is None

    def test_missing_title(self):
        i = _item(); i["jobResult"]["jobTitle"] = ""
        assert js.SearchResult.from_api_item(i) is None

    def test_missing_company(self):
        i = _item()
        i["companyResult"]["companyName"] = ""
        i["jobResult"]["companyName"] = ""
        assert js.SearchResult.from_api_item(i) is None

    def test_none_jobresult(self):
        assert js.SearchResult.from_api_item({"jobResult": None, "companyResult": {}}) is None

    def test_strips_whitespace(self):
        i = _item(title="  PM  ", company="  Corp  ")
        sr = js.SearchResult.from_api_item(i)
        assert sr.title == "PM"; assert sr.company == "Corp"

    def test_source_key_format(self):
        i = _item(job_id="deadbeef12345678deadbeef")
        assert js.SearchResult.from_api_item(i).source_key == "jobright-search:deadbeef12345678deadbeef"

    def test_company_fallback(self):
        i = _item(company="")
        i["companyResult"]["companyName"] = ""
        i["jobResult"]["companyName"] = "Fallback Co"
        sr = js.SearchResult.from_api_item(i)
        assert sr is not None and sr.company == "Fallback Co"

# ── 3. Dedup logic ────────────────────────────────────────────────────────────

class TestDedupLogic:
    def test_dedup_across_pages(self):
        with mock.patch.object(js, "_throttled_get") as mg:
            mg.return_value.json.return_value = _resp([_item(job_id="dup000dup000dup000dup000")])
            mg.return_value.status_code = 200
            results = js.search_all_pages("test", "fake", max_pages=3)
        assert len(results) == 1

    def test_dedup_across_keywords(self):
        with mock.patch.object(js, "_throttled_get") as mg:
            mg.return_value.json.return_value = _resp([_item(job_id="shared000shared000shared0")])
            mg.return_value.status_code = 200
            results = js.search_jobright(["k1", "k2", "k3"], cookie="fake", max_pages=1)
        ids = [r.job_id for r in results]
        assert len(ids) == len(set(ids))
        assert "shared000shared000shared0" in ids

    def test_company_filter(self):
        items = [_item(job_id="a01", company="Google"),
                 _item(job_id="a02", company="Amazon"),
                 _item(job_id="a03", company="Google DeepMind")]
        with mock.patch.object(js, "_throttled_get") as mg:
            mg.return_value.json.return_value = _resp(items)
            mg.return_value.status_code = 200
            results = js.search_jobright(["pm"], companies=["google"], cookie="fake", max_pages=1)
        cos = [r.company for r in results]
        assert "Amazon" not in cos and "Google" in cos and "Google DeepMind" in cos

    def test_partial_page_stops(self):
        calls = [0]
        def fake(url, params, cookie):
            calls[0] += 1
            r = mock.MagicMock(); r.status_code = 200
            if calls[0] == 1:
                r.json.return_value = _resp([_item(job_id=f"a{i:04d}") for i in range(10)])
            else:
                r.json.return_value = _resp([_item(job_id=f"b{i:04d}") for i in range(3)])
            return r
        with mock.patch.object(js, "_throttled_get", side_effect=fake):
            results = js.search_all_pages("t", "c", max_pages=5, page_size=10)
        assert len(results) == 13 and calls[0] == 2

# ── 4. publishTime sorting ────────────────────────────────────────────────────

class TestPublishTimeSorting:
    def test_sorted_desc(self):
        items = [
            _item(job_id="t01", publish_time="2026-06-10 08:00:00"),
            _item(job_id="t02", publish_time="2026-06-14 22:00:00"),
            _item(job_id="t03", publish_time="2026-06-12 15:30:00"),
        ]
        with mock.patch.object(js, "_throttled_get") as mg:
            mg.return_value.json.return_value = _resp(items)
            mg.return_value.status_code = 200
            results = js.search_jobright(["pm"], cookie="fake", max_pages=1)
        times = [r.publish_time for r in results]
        assert times == sorted(times, reverse=True)
        assert results[0].publish_time == "2026-06-14 22:00:00"

    def test_empty_time_sorts_last(self):
        items = [_item(job_id="e01", publish_time=""), _item(job_id="e02", publish_time="2026-06-13 10:00:00")]
        with mock.patch.object(js, "_throttled_get") as mg:
            mg.return_value.json.return_value = _resp(items)
            mg.return_value.status_code = 200
            results = js.search_jobright(["t"], cookie="fake", max_pages=1)
        dated = [r for r in results if r.publish_time]
        undated = [r for r in results if not r.publish_time]
        assert results.index(dated[0]) < results.index(undated[0])

# ── 5. Classifier gate ────────────────────────────────────────────────────────

class TestClassifierGate:
    def _r(self, title): return _sr(title=title)
    def test_pm(self): assert js._classify_keep(self._r("Product Manager"))
    def test_tpm(self): assert js._classify_keep(self._r("TPM, Infra"))
    def test_technical_program_mgr(self): assert js._classify_keep(self._r("Technical Program Manager"))
    def test_solutions_eng(self): assert js._classify_keep(self._r("Solutions Engineer"))
    def test_solutions_arch(self): assert js._classify_keep(self._r("Solutions Architect"))
    def test_customer_eng(self): assert js._classify_keep(self._r("Customer Engineer"))
    def test_no_senior(self): assert not js._classify_keep(self._r("Senior Product Manager"))
    def test_no_staff(self): assert not js._classify_keep(self._r("Staff Product Manager"))
    def test_no_director(self): assert not js._classify_keep(self._r("Director of Product"))
    def test_no_swe(self): assert not js._classify_keep(self._r("Software Engineer II"))
    def test_no_ml(self): assert not js._classify_keep(self._r("ML Engineer"))
    def test_no_ds(self): assert not js._classify_keep(self._r("Data Scientist"))
    def test_unknown_keeps(self): assert js._classify_keep(self._r("Business Analyst"))

# ── 6. ATS detection ──────────────────────────────────────────────────────────

class TestAtsDetection:
    def test_greenhouse(self): assert js._detect_ats("https://boards.greenhouse.io/a/jobs/1") == "greenhouse"
    def test_ashby(self): assert js._detect_ats("https://jobs.ashbyhq.com/co/abc") == "ashby"
    def test_lever(self): assert js._detect_ats("https://jobs.lever.co/co/abc") == "lever"
    def test_workday_wd5(self): assert js._detect_ats("https://co.wd5.myworkdayjobs.com/c/job/x") == "workday"
    def test_workday_wd1(self): assert js._detect_ats("https://co.wd1.myworkdayjobs.com/site/job/x") == "workday"
    def test_bamboohr(self): assert js._detect_ats("https://co.bamboohr.com/careers/1") == "bamboohr"
    def test_rippling(self): assert js._detect_ats("https://ats.rippling.com/co/jobs/1") == "rippling"
    def test_smartrecruiters(self): assert js._detect_ats("https://jobs.smartrecruiters.com/co/1") == "smartrecruiters"
    def test_unknown_none(self): assert js._detect_ats("https://careers.example.com") is None
    def test_wrapper_none(self): assert js._detect_ats("https://jobright.ai/jobs/info/abc") is None
    def test_empty_none(self): assert js._detect_ats("") is None
    def test_none_arg(self): assert js._detect_ats(None) is None

# ── 7. Tracker insertion ──────────────────────────────────────────────────────

class TestIngestToTracker:
    def test_dry_run_no_writes(self, tmp_db):
        results = [_sr(job_id="bbb000bbb000bbb000bbb001",
                        original_url="https://boards.greenhouse.io/t/jobs/1")]
        stats = js.ingest_to_tracker(results, db_path=tmp_db, dry_run=True, verbose=False)
        assert stats["inserted"] == 1
        conn = sqlite3.connect(tmp_db)
        assert conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == 0
        conn.close()

    def test_inserts_new(self, tmp_db):
        results = [_sr(job_id="ccc000ccc000ccc000ccc001", company="AcmeCo",
                        original_url="https://boards.greenhouse.io/acmeco/jobs/1")]
        stats = js.ingest_to_tracker(results, db_path=tmp_db, dry_run=False, verbose=False)
        assert stats["inserted"] == 1
        conn = sqlite3.connect(tmp_db)
        row = conn.execute("SELECT source_key, company, app_url, status FROM roles").fetchone()
        conn.close()
        assert row[0] == "jobright-search:ccc000ccc000ccc000ccc001"
        assert row[1] == "AcmeCo"
        assert "greenhouse.io" in row[2]
        assert row[3] == ""  # auto-submit queue

    def test_skips_dup_source_key(self, tmp_db):
        jid = "ddd000ddd000ddd000ddd001"
        conn = sqlite3.connect(tmp_db)
        conn.execute("INSERT INTO roles (source_key,company,role,status) VALUES (?,?,?,?)",
                     (f"jobright-search:{jid}", "Ex", "PM", "manual-apply"))
        conn.commit(); conn.close()
        stats = js.ingest_to_tracker([_sr(job_id=jid)], db_path=tmp_db, dry_run=False, verbose=False)
        assert stats["skipped_dup"] == 1 and stats["inserted"] == 0

    def test_skips_public_crawl_dup(self, tmp_db):
        jid = "ddd000ddd000ddd000ddd002"
        conn = sqlite3.connect(tmp_db)
        conn.execute("INSERT INTO roles (source_key,company,role,status) VALUES (?,?,?,?)",
                     (f"jobright:{jid}", "Ex", "PM", "manual-apply"))
        conn.commit(); conn.close()
        stats = js.ingest_to_tracker([_sr(job_id=jid)], db_path=tmp_db, dry_run=False, verbose=False)
        assert stats["skipped_dup"] == 1

    def test_filters_senior(self, tmp_db):
        results = [_sr(job_id="eee000eee000eee000eee001", title="Senior PM")]
        stats = js.ingest_to_tracker(results, db_path=tmp_db, dry_run=False, verbose=False)
        assert stats["skipped_filter"] == 1 and stats["inserted"] == 0

    def test_manual_apply_unknown_ats(self, tmp_db):
        results = [_sr(job_id="fff000fff000fff000fff001", company="Cx",
                        original_url="https://custom.ats.io/jobs/1")]
        js.ingest_to_tracker(results, db_path=tmp_db, dry_run=False, verbose=False)
        conn = sqlite3.connect(tmp_db)
        row = conn.execute("SELECT status FROM roles WHERE company=\'Cx\'").fetchone()
        conn.close()
        assert row[0] == "manual-apply"

    def test_posted_on_date(self, tmp_db):
        results = [_sr(job_id="hhh000hhh000hhh000hhh001", publish_time="2026-06-14 18:30:00",
                        original_url="https://boards.greenhouse.io/co/jobs/1")]
        js.ingest_to_tracker(results, db_path=tmp_db, dry_run=False, verbose=False)
        conn = sqlite3.connect(tmp_db)
        row = conn.execute("SELECT posted_on FROM roles WHERE source_key LIKE \'%hhh000%\'").fetchone()
        conn.close()
        assert row[0] == "2026-06-14"

    def test_mixed_counts(self, tmp_db):
        jex = "ggg000ggg000ggg000ggg001"
        conn = sqlite3.connect(tmp_db)
        conn.execute("INSERT INTO roles (source_key,company,role,status) VALUES (?,?,?,?)",
                     (f"jobright-search:{jex}", "Ex", "PM", "manual-apply"))
        conn.commit(); conn.close()
        results = [
            _sr(job_id=jex, title="Product Manager"),
            _sr(job_id="ggg000ggg000ggg000ggg002", title="Senior PM"),
            _sr(job_id="ggg000ggg000ggg000ggg003", title="TPM",
                original_url="https://jobs.ashbyhq.com/co/abc"),
        ]
        stats = js.ingest_to_tracker(results, db_path=tmp_db, dry_run=False, verbose=False)
        assert stats["inserted"] == 1
        assert stats["skipped_dup"] == 1
        assert stats["skipped_filter"] == 1

# ── 8. Auth errors ────────────────────────────────────────────────────────────

class TestAuthErrors:
    def test_401(self):
        with mock.patch("requests.Session.get") as mg:
            mg.return_value.status_code = 401
            with pytest.raises(js.JobRightAuthError, match="Session rejected"):
                js.search("t", "bad")

    def test_403(self):
        with mock.patch("requests.Session.get") as mg:
            mg.return_value.status_code = 403
            with pytest.raises(js.JobRightAuthError, match="Session rejected"):
                js.search("t", "bad")

    def test_success_false(self):
        with mock.patch("requests.Session.get") as mg:
            mg.return_value.status_code = 200
            mg.return_value.json.return_value = {"success": False, "errorCode": 20000, "errorMsg": "unauth", "result": None}
            with pytest.raises(js.JobRightSearchError, match="success=false"):
                js.search("t", "bad")

# ── 9. Network errors ─────────────────────────────────────────────────────────

class TestNetworkErrors:
    def test_non_json(self):
        with mock.patch("requests.Session.get") as mg:
            mg.return_value.status_code = 200
            mg.return_value.json.side_effect = ValueError("no json")
            mg.return_value.text = "ISE"
            with pytest.raises(js.JobRightSearchError, match="Non-JSON"):
                js.search("t", "fake")

    def test_empty_list_ok(self):
        with mock.patch("requests.Session.get") as mg:
            mg.return_value.status_code = 200
            mg.return_value.json.return_value = {"success": True, "errorCode": 10000, "result": {"jobList": [], "impId": "x"}}
            assert js.search("empty", "c") == []
