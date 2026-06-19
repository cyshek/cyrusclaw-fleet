"""Test run.run_one per-company adapter timeout + note-exclusion (no network)."""
import time
import run


def test_run_one_excludes_note_from_opts(monkeypatch):
    captured = {}

    def fake_adapter(name, slug, **opts):
        captured.update(opts)
        return []

    monkeypatch.setitem(run.REGISTRY, "fake", fake_adapter)
    c = {"name": "X", "adapter": "fake", "slug": "x", "note": "should-not-pass", "region": "us"}
    cfg, roles, err = run.run_one(c)
    assert err is None
    assert "note" not in captured  # note must be stripped
    assert captured.get("region") == "us"  # other opts pass through


def test_run_one_times_out_on_hung_adapter(monkeypatch):
    def hung(name, slug, **opts):
        time.sleep(30)  # longer than the override timeout
        return []

    monkeypatch.setitem(run.REGISTRY, "hung", hung)
    monkeypatch.setattr(run, "ADAPTER_TIMEOUT_S", 1)
    c = {"name": "Slow", "adapter": "hung", "slug": "s"}
    t0 = time.time()
    cfg, roles, err = run.run_one(c)
    dt = time.time() - t0
    assert err == "timeout>1s"
    assert roles == []
    assert dt < 5  # returned promptly, did not wait the full 30s


def test_run_one_skip_and_unknown():
    assert run.run_one({"name": "S", "skip": True})[2] == "skip"
    assert run.run_one({"name": "N", "adapter": "nope", "slug": "x"})[2].startswith("unknown-adapter")
