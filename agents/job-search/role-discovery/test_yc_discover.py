"""Tests for yc_discover — dedup, selection, and merge logic (no network)."""
import json
import types
import yaml
import yc_discover as yd


def test_norm_name():
    assert yd._norm_name("Work-At.A Startup!") == "workatastartup"
    assert yd._norm_name("") == ""


def test_select_hiring_filters_status_and_region():
    data = [
        {"name": "A", "status": "Active", "isHiring": True, "regions": ["America / Canada"]},
        {"name": "B", "status": "Active", "isHiring": False, "regions": ["America"]},
        {"name": "C", "status": "Inactive", "isHiring": True, "regions": ["America"]},
        {"name": "D", "status": "Active", "isHiring": True, "regions": ["Europe"]},
    ]
    allh = yd.select_hiring(data, us_only=False)
    assert {c["name"] for c in allh} == {"A", "D"}
    us = yd.select_hiring(data, us_only=True)
    assert {c["name"] for c in us} == {"A"}


def test_load_existing(tmp_path):
    p = tmp_path / "companies.yaml"
    p.write_text(yaml.safe_dump([
        {"name": "Acme Corp", "adapter": "greenhouse", "slug": "acme"},
        {"name": "Beta", "adapter": "ashby", "slug": "beta"},
        {"name": "NoSlug"},
    ]), encoding="utf-8")
    names, slugs = yd.load_existing(p)
    assert "acmecorp" in names and "beta" in names and "noslug" in names
    assert "greenhouse/acme" in slugs and "ashby/beta" in slugs


def test_discover_for_prefers_yc_slug(monkeypatch):
    calls = []

    def fake_probe(adapter, slug):
        calls.append((adapter, slug))
        if adapter == "greenhouse" and slug == "realslug":
            return ("greenhouse", "realslug", 7)
        return None

    monkeypatch.setattr(yd, "probe", fake_probe)
    r = yd.discover_for({"name": "Real Co", "slug": "realslug"})
    assert r and r["adapter"] == "greenhouse" and r["slug"] == "realslug" and r["jobs"] == 7
    # the authoritative yc slug must be probed first
    assert calls[0] == ("greenhouse", "realslug")


def test_discover_for_returns_none_when_no_board(monkeypatch):
    monkeypatch.setattr(yd, "probe", lambda a, s: None)
    assert yd.discover_for({"name": "Ghost", "slug": "ghost"}) is None


def test_run_dedups_existing_name_and_slug(monkeypatch, tmp_path):
    # existing yaml has Acme(name) and ashby/dup(slug)
    p = tmp_path / "companies.yaml"
    p.write_text(yaml.safe_dump([
        {"name": "Acme", "adapter": "greenhouse", "slug": "acme"},
        {"name": "HasDupSlug", "adapter": "ashby", "slug": "dup"},
    ]), encoding="utf-8")
    monkeypatch.setattr(yd, "YAML_PATH", p)

    data = [
        {"name": "Acme", "status": "Active", "isHiring": True, "regions": ["America"], "slug": "acme"},
        {"name": "NewCo", "status": "Active", "isHiring": True, "regions": ["America"], "slug": "newco"},
        {"name": "SlugClash", "status": "Active", "isHiring": True, "regions": ["America"], "slug": "dup"},
    ]
    monkeypatch.setattr(yd, "fetch_yc", lambda force=False: data)

    def fake_probe(adapter, slug):
        if slug == "newco" and adapter == "greenhouse":
            return ("greenhouse", "newco", 3)
        if slug == "dup" and adapter == "ashby":
            return ("ashby", "dup", 9)
        return None

    monkeypatch.setattr(yd, "probe", fake_probe)
    # isolate the report write so the test can't clobber the real output dir
    (tmp_path / "output").mkdir(exist_ok=True)
    monkeypatch.setattr(yd, "ROOT", tmp_path)
    hits = yd.run(limit=0, us_only=True, apply=False, workers=2, force_fetch=False)
    names = {h["name"] for h in hits}
    # Acme skipped by name; SlugClash skipped by slug; only NewCo survives
    assert names == {"NewCo"}


def test_append_to_yaml_handles_companies_wrapper(monkeypatch, tmp_path):
    p = tmp_path / "companies.yaml"
    p.write_text(yaml.safe_dump({"companies": [
        {"name": "Existing", "adapter": "greenhouse", "slug": "existing"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(yd, "YAML_PATH", p)
    yd._append_to_yaml([{"name": "NewCo", "adapter": "ashby", "slug": "newco", "batch": "S25"}])
    out = yaml.safe_load(p.read_text())
    assert isinstance(out, dict) and "companies" in out
    names = [c["name"] for c in out["companies"]]
    assert names == ["Existing", "NewCo"]
    # backup written
    assert (tmp_path / "companies.yaml.bak.yc").exists()
