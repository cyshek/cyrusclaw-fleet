"""Tests for himalayas_discover -- keyword KEEP gate, US filter, company
selection/dedup, board probe, run() dedup, and merge logic. No network: all
HTTP (fetch + probe) is monkeypatched.
"""
import json
import yaml
import himalayas_discover as hd


# --- keyword KEEP gate (reuses the live classifier) ------------------------

def test_keyword_match_keeps_target_roles():
    for title in [
        "Product Manager, Growth",
        "Technical Program Manager",
        "Solutions Engineer",
        "Sales Engineer, Enterprise",
        "Solutions Architect",
        "Customer Engineer",
        "APM, Platform",
    ]:
        assert hd.keyword_match({"title": title}) is True, title


def test_keyword_match_drops_senior_fde_swe_and_manager():
    for title in [
        "Senior Product Manager",          # senior -> skip
        "Staff Technical Program Manager", # staff -> skip
        "Principal Solutions Engineer",    # principal -> skip
        "Software Engineer",               # not a target role
        "Forward Deployed Engineer",       # FDE hard block
        "Engineering Manager",             # people-manager 'manager' w/o target
        "",                                # empty
    ]:
        assert hd.keyword_match({"title": title}) is False, title


# --- US eligibility ---------------------------------------------------------

def test_is_us_eligible():
    # empty restrictions => unrestricted => eligible
    assert hd.is_us_eligible({"locationRestrictions": []}) is True
    assert hd.is_us_eligible({}) is True
    # explicit US / remote / americas => eligible
    assert hd.is_us_eligible({"locationRestrictions": ["United States"]}) is True
    assert hd.is_us_eligible({"locationRestrictions": ["Remote"]}) is True
    assert hd.is_us_eligible({"locationRestrictions": ["North America", "Europe"]}) is True
    # purely non-US => not eligible
    assert hd.is_us_eligible({"locationRestrictions": ["Germany", "France"]}) is False


# --- company selection + dedup-to-unique ------------------------------------

def test_select_companies_filters_and_collapses():
    jobs = [
        {"title": "Product Manager", "companyName": "Acme", "companySlug": "acme",
         "locationRestrictions": ["United States"]},
        {"title": "Senior Product Manager", "companyName": "Acme", "companySlug": "acme",
         "locationRestrictions": ["United States"]},  # senior -> dropped
        {"title": "Solutions Engineer", "companyName": "Acme", "companySlug": "acme",
         "locationRestrictions": []},                  # 2nd target role, same co
        {"title": "Software Engineer", "companyName": "Beta", "companySlug": "beta",
         "locationRestrictions": ["United States"]},   # not target -> Beta absent
        {"title": "TPM", "companyName": "Gamma", "companySlug": "gamma",
         "locationRestrictions": ["Germany"]},         # non-US -> dropped under us_only
    ]
    # us_only: Gamma dropped (non-US), Beta dropped (no target role)
    comps = hd.select_companies(jobs, us_only=True)
    assert set(comps.keys()) == {"acme"}
    assert comps["acme"]["n_target_roles"] == 2  # PM + SE, not the senior dup
    assert comps["acme"]["name"] == "Acme"
    assert comps["acme"]["himalayas_slug"] == "acme"

    # without us_only: Gamma's TPM now survives the location filter
    comps2 = hd.select_companies(jobs, us_only=False)
    assert set(comps2.keys()) == {"acme", "gamma"}


def test_select_companies_skips_blank_company_name():
    jobs = [{"title": "Product Manager", "companyName": "", "companySlug": "x",
             "locationRestrictions": []}]
    assert hd.select_companies(jobs, us_only=False) == {}


def test_select_companies_drops_placeholder_and_staffing():
    jobs = [
        # Himalayas' literal "name" placeholder leakage -> must be dropped.
        {"title": "Program Manager", "companyName": "name", "companySlug": "abacus",
         "locationRestrictions": []},
        {"title": "Product Manager", "companyName": "Company Name", "companySlug": "x",
         "locationRestrictions": []},
        # Staffing/recruiter middlemen -> dropped via shared blocklist.
        {"title": "Solutions Architect", "companyName": "Bravo Global Staffing",
         "companySlug": "bgs", "locationRestrictions": []},
        {"title": "Project Manager", "companyName": "4 Staffing Corp",
         "companySlug": "4sc", "locationRestrictions": []},
        # A real product company survives.
        {"title": "Product Manager", "companyName": "GoodCo", "companySlug": "goodco",
         "locationRestrictions": []},
    ]
    comps = hd.select_companies(jobs, us_only=False)
    assert set(comps.keys()) == {"goodco"}, comps


# --- board probe (prefers the himalayas slug first) -------------------------

def test_discover_for_prefers_himalayas_slug(monkeypatch):
    calls = []

    def fake_probe(adapter, slug):
        calls.append((adapter, slug))
        if adapter == "greenhouse" and slug == "realslug":
            return ("greenhouse", "realslug", 5)
        return None

    monkeypatch.setattr(hd, "probe", fake_probe)
    r = hd.discover_for({"name": "Real Co", "himalayas_slug": "realslug",
                         "n_target_roles": 2, "sample_title": "PM"})
    assert r and r["adapter"] == "greenhouse" and r["slug"] == "realslug"
    assert r["jobs"] == 5 and r["n_target_roles"] == 2
    # the himalayas slug must be probed first
    assert calls[0] == ("greenhouse", "realslug")


def test_discover_for_returns_none_when_no_board(monkeypatch):
    monkeypatch.setattr(hd, "probe", lambda a, s: None)
    assert hd.discover_for({"name": "Ghost", "himalayas_slug": "ghost"}) is None


# --- full run(): dedup by existing name AND existing slug -------------------

def test_run_dedups_existing_name_and_slug(monkeypatch, tmp_path):
    p = tmp_path / "companies.yaml"
    p.write_text(yaml.safe_dump([
        {"name": "Acme", "adapter": "greenhouse", "slug": "acme"},
        {"name": "HasDupSlug", "adapter": "ashby", "slug": "dup"},
    ]), encoding="utf-8")
    monkeypatch.setattr(hd, "YAML_PATH", p)

    jobs = [
        {"title": "Product Manager", "companyName": "Acme", "companySlug": "acme",
         "locationRestrictions": ["United States"]},          # dup by name
        {"title": "Solutions Engineer", "companyName": "NewCo", "companySlug": "newco",
         "locationRestrictions": ["United States"]},          # net-new
        {"title": "TPM", "companyName": "SlugClash", "companySlug": "dup",
         "locationRestrictions": ["United States"]},          # dup by resolved slug
    ]
    monkeypatch.setattr(hd, "fetch_jobs",
                        lambda max_jobs, force=False: jobs)

    def fake_probe(adapter, slug):
        if slug == "newco" and adapter == "greenhouse":
            return ("greenhouse", "newco", 3)
        if slug == "dup" and adapter == "ashby":
            return ("ashby", "dup", 9)
        return None

    monkeypatch.setattr(hd, "probe", fake_probe)
    monkeypatch.setattr(hd, "HITS_OUT", tmp_path / "hits.json")
    hits = hd.run(max_jobs=100, us_only=True, apply=False, workers=2,
                  force_fetch=False)
    names = {h["name"] for h in hits}
    # Acme skipped by name; SlugClash skipped by resolved slug; only NewCo survives
    assert names == {"NewCo"}


def test_append_to_yaml_handles_companies_wrapper(monkeypatch, tmp_path):
    p = tmp_path / "companies.yaml"
    p.write_text(yaml.safe_dump({"companies": [
        {"name": "Existing", "adapter": "greenhouse", "slug": "existing"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(hd, "YAML_PATH", p)
    hd._append_to_yaml([{"name": "NewCo", "adapter": "ashby", "slug": "newco"}])
    out = yaml.safe_load(p.read_text())
    assert isinstance(out, dict) and "companies" in out
    names = [c["name"] for c in out["companies"]]
    assert names == ["Existing", "NewCo"]
    assert out["companies"][-1]["note"] == "himalayas-auto-discovered"
    assert (tmp_path / "companies.yaml.bak.himalayas").exists()


def test_fetch_jobs_uses_cache_when_large_enough(monkeypatch, tmp_path):
    cache = tmp_path / "himalayas_jobs.json"
    cache.write_text(json.dumps([{"title": "PM", "companyName": "C"}] * 50),
                     encoding="utf-8")
    monkeypatch.setattr(hd, "CACHE", cache)

    def boom(*a, **k):  # network must NOT be touched when cache suffices
        raise AssertionError("network called despite sufficient cache")

    monkeypatch.setattr(hd.requests, "get", boom)
    got = hd.fetch_jobs(10, force=False)
    assert len(got) == 10


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_fetch_jobs_backs_off_then_succeeds_on_429(monkeypatch, tmp_path):
    monkeypatch.setattr(hd, "CACHE", tmp_path / "nocache.json")
    monkeypatch.setattr(hd.time, "sleep", lambda *_: None)  # no real waiting
    seq = [
        _Resp(200, {"jobs": [{"title": "PM", "companyName": "A"}], "totalCount": 100}),
        _Resp(429),
        _Resp(429),
        _Resp(200, {"jobs": [{"title": "TPM", "companyName": "B"}], "totalCount": 100}),
    ]
    calls = {"i": 0}

    def fake_get(*a, **k):
        r = seq[calls["i"]]
        calls["i"] += 1
        return r

    monkeypatch.setattr(hd.requests, "get", fake_get)
    got = hd.fetch_jobs(2, force=True)
    # the two 429s were retried (not fatal); both 200 pages collected
    assert len(got) == 2
    assert {j["companyName"] for j in got} == {"A", "B"}


def test_fetch_jobs_gives_up_after_persistent_429(monkeypatch, tmp_path):
    monkeypatch.setattr(hd, "CACHE", tmp_path / "nocache.json")
    monkeypatch.setattr(hd.time, "sleep", lambda *_: None)
    monkeypatch.setattr(hd.requests, "get", lambda *a, **k: _Resp(429))
    # never raises, just returns whatever it had (nothing) after 5 retries
    got = hd.fetch_jobs(100, force=True)
    assert got == []
