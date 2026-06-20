"""Tests for regate_google_llm_yoe_knockouts: target selection + flag idempotency."""
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import regate_google_llm_yoe_knockouts as R  # noqa: E402


def _mkdb():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE roles (id INTEGER PRIMARY KEY, company TEXT, role TEXT, "
        "status TEXT, exp_req TEXT, llm_yoe_required INT, llm_fit_score INT, "
        "flags TEXT, agent_notes TEXT, last_seen TEXT)"
    )
    return c


def _ins(c, **kw):
    cols = ",".join(kw); ph = ",".join("?" * len(kw))
    c.execute(f"INSERT INTO roles ({cols}) VALUES ({ph})", tuple(kw.values()))


def test_selects_only_open_google_yoe_ge_4():
    c = _mkdb()
    _ins(c, id=1, company="Google", role="PM II", status="", llm_yoe_required=5)   # drop
    _ins(c, id=2, company="Google", role="PM I", status="", llm_yoe_required=3)    # keep (fit)
    _ins(c, id=3, company="Google", role="PM", status="", llm_yoe_required=4)      # drop (==4)
    _ins(c, id=4, company="Google", role="PM", status="skip", llm_yoe_required=8)  # already skip
    _ins(c, id=5, company="Netflix", role="PM", status="", llm_yoe_required=9)     # not google
    _ins(c, id=6, company="Google", role="PM", status="", llm_yoe_required=None)   # no llm yoe
    ids = sorted(r["id"] for r in R.select_targets(c))
    assert ids == [1, 3], ids


def test_add_flag_idempotent():
    assert R._add_flag(None, "x") == "x"
    assert R._add_flag("a b", "x") == "a b x"
    assert R._add_flag("a x b", "x") == "a x b"  # no dup
    assert R._add_flag("manual-apply discovery-only", R.KNOCKOUT_FLAG) == \
        "manual-apply discovery-only " + R.KNOCKOUT_FLAG


def test_threshold_constant_matches_doctrine():
    # canonical gate: min stated >= 4 -> DROP
    assert R.MIN_DROP_YOE == 4


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn(); passed += 1; print(f"PASS {fn.__name__}")
        except Exception:
            print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
