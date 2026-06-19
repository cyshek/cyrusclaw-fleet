"""Regression test: the Workday runner's WORK_HISTORY must be built from
personal-info.json (the single source of truth the rendered resume uses), so the
TYPED Workday experience section can't drift away from the uploaded PDF.

Background (Cyrus 2026-06-09): the old hardcoded WORK_HISTORY had only 3 of 5
roles (missing both Microsoft internships) + a wrong Amazon date, so the typed
fields conflicted with the 5-role resume PDF. _build_work_history() now reads
personal-info.json. These tests lock that wiring + the month/date conversion +
the safe fallback.
"""
import importlib
import _workday_runner as w


def test_work_history_built_from_personal_info_has_all_roles():
    importlib.reload(w)
    wh = w.WORK_HISTORY
    # Must include the full canonical history, not the legacy 3-role list.
    companies = [(j["company"], j["start"]) for j in wh]
    assert ("Microsoft", ("03", "2024")) in companies, "current Microsoft TPM missing"
    assert ("Microsoft", ("05", "2023")) in companies, "Microsoft 2023 internship missing"
    assert ("Microsoft", ("05", "2022")) in companies, "Microsoft 2022 internship missing"
    assert ("Amazon Robotics", ("08", "2023")) in companies, "Amazon Robotics missing/mis-dated"
    assert ("Pro Painters", ("05", "2021")) in companies, "Pro Painters missing"
    assert len(wh) >= 5, "expected the full 5-role canonical history"


def test_exactly_one_current_role():
    importlib.reload(w)
    current = [j for j in w.WORK_HISTORY if j.get("current")]
    assert len(current) == 1, "exactly one current role expected"
    assert current[0]["company"] == "Microsoft"
    assert current[0]["end"] is None, "current role must have end=None"


def test_every_role_has_dated_start_and_desc():
    importlib.reload(w)
    for j in w.WORK_HISTORY:
        sm, sy = j["start"]
        assert sm and len(sm) == 2 and sm.isdigit(), f"bad start month for {j['company']}: {sm!r}"
        assert sy and len(sy) == 4 and sy.isdigit(), f"bad start year for {j['company']}: {sy!r}"
        assert j.get("desc"), f"missing roleDescription desc for {j['company']}"


def test_non_current_roles_have_end_dates():
    importlib.reload(w)
    for j in w.WORK_HISTORY:
        if not j.get("current"):
            assert j["end"] is not None, f"{j['company']} should have an end date"
            em, ey = j["end"]
            assert em and ey, f"{j['company']} end date incomplete: {j['end']!r}"


def test_month_num_normalizes_names_abbrevs_and_numbers():
    assert w._month_num("March") == "03"
    assert w._month_num("mar") == "03"
    assert w._month_num("3") == "03"
    assert w._month_num("03") == "03"
    assert w._month_num("December") == "12"
    assert w._month_num("") == ""
    assert w._month_num("nonsense") == ""
    assert w._month_num("13") == ""


def test_fallback_returns_legacy_list_when_personal_info_unusable(monkeypatch):
    # If personal-info.json can't be read, must fall back to the legacy 3-role list,
    # never crash and never return empty.
    import builtins
    real_open = builtins.open

    def boom(path, *a, **k):
        if "personal-info.json" in str(path):
            raise FileNotFoundError("simulated missing personal-info")
        return real_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", boom)
    fb = w._build_work_history()
    assert fb == w._WORK_HISTORY_FALLBACK
    assert len(fb) >= 1 and any(j["current"] for j in fb)
