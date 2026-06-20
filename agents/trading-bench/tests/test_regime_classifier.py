"""Tests for runner/regime_classifier.py + runner gate integration.

Coverage targets (from subagent spec):
  - JSON parse success
  - Schema validation rejects invalid regime / wrong types
  - Fallback on LLM API error (HTTPError)
  - Fallback on LLM timeout (URLError)
  - Fallback on stale TTL (>5 days)
  - Fallback on missing API key
  - Fallback on invalid JSON in LLM response
  - Runner gate skip path (regime blocks strategy)
  - Runner gate pass path (regime allows strategy)
  - Runner gate skip_regime_unknown when no decision exists
  - llm_decisions logging on success + failure
  - regime_decisions persistence + idempotent UPSERT
  - get_today_regime TTL behavior
  - Prompt hash stability
  - allow_strategies whitelist intersection (drop unknown names)
  - allow_strategies regime-default intersection (LLM can only narrow)
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib import error

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMPDIR = tempfile.mkdtemp(prefix="tess_regime_")
_TEST_DB = Path(_TMPDIR) / "rc.db"

from runner import db, regime_classifier as rc, runner  # noqa: E402


class _FakeBroker:
    """Duck-types AlpacaClient.stock_bars for SPY only."""

    def __init__(self, closes=None):
        if closes is None:
            # 220 closes, mild uptrend.
            closes = [400.0 + i * 0.5 for i in range(220)]
        self.closes = closes

    def stock_bars(self, symbol, *, timeframe, limit):
        assert symbol == "SPY"
        n = min(limit, len(self.closes))
        return [{"t": f"day{i}", "o": c, "h": c, "l": c, "c": c}
                for i, c in enumerate(self.closes[-n:])]


def _patch_db_path(test_case: unittest.TestCase) -> None:
    """Swap db.DB_PATH AND all the captured default args. Same recipe as
    tests/test_runner.py."""
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    import types
    orig = db.DB_PATH
    patcher = mock.patch.object(db, "DB_PATH", _TEST_DB)
    patcher.start()
    test_case.addCleanup(patcher.stop)
    test_case._orig_defaults = {}
    for name in dir(db):
        fn = getattr(db, name)
        if not isinstance(fn, types.FunctionType):
            continue
        if fn.__defaults__:
            new = tuple(_TEST_DB if d == orig else d for d in fn.__defaults__)
            if new != fn.__defaults__:
                test_case._orig_defaults[(fn, "pos")] = fn.__defaults__
                fn.__defaults__ = new
        if fn.__kwdefaults__:
            new_kw = {k: (_TEST_DB if v == orig else v)
                      for k, v in fn.__kwdefaults__.items()}
            if new_kw != fn.__kwdefaults__:
                test_case._orig_defaults[(fn, "kw")] = dict(fn.__kwdefaults__)
                fn.__kwdefaults__ = new_kw

    def _restore():
        for (fn, kind), defs in test_case._orig_defaults.items():
            if kind == "pos":
                fn.__defaults__ = defs
            else:
                fn.__kwdefaults__ = defs
    test_case.addCleanup(_restore)
    db.init_db(_TEST_DB)


# ---------------------------------------------------------------------------
# Pure-unit tests (no broker, no LLM)
# ---------------------------------------------------------------------------

class TestPromptHashStability(unittest.TestCase):
    def test_same_inputs_same_hash(self):
        h1 = rc.prompt_hash("hello", {"a": 1, "b": 2})
        h2 = rc.prompt_hash("hello", {"b": 2, "a": 1})  # different key order
        self.assertEqual(h1, h2, "schema key order must not affect hash")

    def test_different_prompt_different_hash(self):
        h1 = rc.prompt_hash("hello", {"a": 1})
        h2 = rc.prompt_hash("hello2", {"a": 1})
        self.assertNotEqual(h1, h2)


class TestValidateDecision(unittest.TestCase):
    def setUp(self):
        self.schema = {}
        self.whitelist = ["s1", "s2", "s3"]

    def test_happy_path(self):
        d = rc.validate_decision(
            {"regime": "RISK_ON", "confidence": 0.8,
             "rationale": "trend strong", "allow_strategies": ["s1", "s2"]},
            self.schema, whitelist=self.whitelist,
        )
        self.assertEqual(d["regime"], "RISK_ON")
        self.assertEqual(d["allow_strategies"], ["s1", "s2"])

    def test_invalid_regime_rejected(self):
        with self.assertRaises(rc.SchemaError):
            rc.validate_decision(
                {"regime": "BULLISH", "confidence": 0.5,
                 "rationale": "x", "allow_strategies": []},
                self.schema, whitelist=self.whitelist,
            )

    def test_confidence_clamped_not_rejected(self):
        d = rc.validate_decision(
            {"regime": "CHOP", "confidence": 1.5,
             "rationale": "x", "allow_strategies": []},
            self.schema, whitelist=self.whitelist,
        )
        self.assertEqual(d["confidence"], 1.0)
        d2 = rc.validate_decision(
            {"regime": "CHOP", "confidence": -0.2,
             "rationale": "x", "allow_strategies": []},
            self.schema, whitelist=self.whitelist,
        )
        self.assertEqual(d2["confidence"], 0.0)

    def test_unknown_strategies_dropped(self):
        d = rc.validate_decision(
            {"regime": "RISK_ON", "confidence": 0.5,
             "rationale": "x",
             "allow_strategies": ["s1", "made_up_strategy", "s3"]},
            self.schema, whitelist=self.whitelist,
        )
        self.assertEqual(set(d["allow_strategies"]), {"s1", "s3"})

    def test_rationale_truncated(self):
        d = rc.validate_decision(
            {"regime": "RISK_ON", "confidence": 0.5,
             "rationale": "x" * 500, "allow_strategies": []},
            self.schema, whitelist=self.whitelist,
        )
        self.assertEqual(len(d["rationale"]), 200)

    def test_missing_field_rejected(self):
        with self.assertRaises(rc.SchemaError):
            rc.validate_decision(
                {"regime": "RISK_ON"},
                self.schema, whitelist=self.whitelist,
            )

    def test_non_object_rejected(self):
        with self.assertRaises(rc.SchemaError):
            rc.validate_decision("not an object", self.schema,
                                 whitelist=self.whitelist)


class TestCodeFallback(unittest.TestCase):
    def test_uptrend_fallback_risk_on(self):
        closes = [100.0 + i for i in range(60)]  # strong uptrend
        d = rc.code_fallback_decision(closes, trading_date="2026-05-30",
                                       reason="test")
        self.assertEqual(d["regime"], "RISK_ON")
        self.assertEqual(d["source"], "fallback")

    def test_downtrend_fallback_risk_off(self):
        closes = [200.0 - i for i in range(60)]  # downtrend
        d = rc.code_fallback_decision(closes, trading_date="2026-05-30",
                                       reason="test")
        self.assertEqual(d["regime"], "RISK_OFF")

    def test_empty_closes_defaults_risk_on(self):
        # regime_uptrend([]) returns True per its contract.
        d = rc.code_fallback_decision([], trading_date="2026-05-30",
                                       reason="empty")
        self.assertEqual(d["regime"], "RISK_ON")


# ---------------------------------------------------------------------------
# classify_and_log integration (DB-backed, broker faked, LLM mocked)
# ---------------------------------------------------------------------------

class TestClassifyAndLog(unittest.TestCase):
    def setUp(self):
        _patch_db_path(self)
        self.broker = _FakeBroker()
        self.params = rc.load_params()

    def test_llm_success_persists_both_tables(self):
        content_json = json.dumps({
            "regime": "RISK_ON", "confidence": 0.75,
            "rationale": "spy above 50sma",
            "allow_strategies": self.params["whitelist_strategies"][:2],
        })
        good_resp = (content_json,
                     {"usage": {"prompt_tokens": 800, "completion_tokens": 50},
                      "system_fingerprint": "fp_test",
                      "model": "gpt-4o-mini"},
                     123)
        with mock.patch.object(rc, "call_llm", return_value=good_resp):
            decision = rc.classify_and_log(client=self.broker, params=self.params)
        self.assertEqual(decision["source"], "llm")
        self.assertEqual(decision["regime"], "RISK_ON")
        self.assertIsNotNone(decision.get("llm_decision_id"))
        # llm_decisions row exists + ok=1
        with db.connect(_TEST_DB) as c:
            llm_rows = [dict(r) for r in c.execute(
                "SELECT * FROM llm_decisions").fetchall()]
            rd_rows = [dict(r) for r in c.execute(
                "SELECT * FROM regime_decisions").fetchall()]
        self.assertEqual(len(llm_rows), 1)
        self.assertEqual(llm_rows[0]["ok"], 1)
        self.assertEqual(llm_rows[0]["model"], "gpt-4o-mini")
        self.assertIsNotNone(llm_rows[0]["cost_usd"])
        self.assertEqual(len(rd_rows), 1)

    def test_llm_api_error_falls_back(self):
        with mock.patch.object(rc, "call_llm",
                               side_effect=rc.LLMError("http_500: server down")):
            decision = rc.classify_and_log(client=self.broker, params=self.params)
        self.assertEqual(decision["source"], "fallback")
        self.assertIn("http_500", decision["fallback_reason"])
        # llm_decisions still has the failure row.
        with db.connect(_TEST_DB) as c:
            llm = c.execute("SELECT * FROM llm_decisions").fetchone()
        self.assertEqual(llm["ok"], 0)
        self.assertIn("http_500", llm["error"])

    def test_llm_timeout_falls_back(self):
        with mock.patch.object(rc, "call_llm",
                               side_effect=rc.LLMError("url_error: timed out")):
            decision = rc.classify_and_log(client=self.broker, params=self.params)
        self.assertEqual(decision["source"], "fallback")
        self.assertIn("url_error", decision["fallback_reason"])

    def test_missing_api_key_falls_back(self):
        with mock.patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            decision = rc.classify_and_log(client=self.broker, params=self.params)
        self.assertEqual(decision["source"], "fallback")
        self.assertIn("missing_api_key", decision["fallback_reason"])

    def test_invalid_json_response_falls_back(self):
        bad_resp = ("not json at all",
                    {"usage": {"prompt_tokens": 10, "completion_tokens": 5}},
                    99)
        with mock.patch.object(rc, "call_llm", return_value=bad_resp):
            decision = rc.classify_and_log(client=self.broker, params=self.params)
        self.assertEqual(decision["source"], "fallback")
        self.assertIn("json_parse_failed", decision["fallback_reason"])

    def test_schema_failure_falls_back(self):
        bad_resp = (json.dumps({
                        "regime": "BULLISH",  # not in enum
                        "confidence": 0.5, "rationale": "x",
                        "allow_strategies": []}),
                    {"usage": {"prompt_tokens": 10, "completion_tokens": 5}},
                    99)
        with mock.patch.object(rc, "call_llm", return_value=bad_resp):
            decision = rc.classify_and_log(client=self.broker, params=self.params)
        self.assertEqual(decision["source"], "fallback")
        self.assertIn("schema_failed", decision["fallback_reason"])

    def test_idempotent_already_exists(self):
        good_resp = (json.dumps({
                         "regime": "RISK_ON", "confidence": 0.8,
                         "rationale": "x", "allow_strategies": []}),
                     {"usage": {"prompt_tokens": 5, "completion_tokens": 5}},
                     1)
        with mock.patch.object(rc, "call_llm", return_value=good_resp) as m:
            d1 = rc.classify_and_log(client=self.broker, params=self.params)
            d2 = rc.classify_and_log(client=self.broker, params=self.params)
        self.assertEqual(m.call_count, 1, "second call must NOT hit LLM")
        self.assertTrue(d2.get("already_existed"))
        self.assertEqual(d1["trading_date"], d2["trading_date"])

    def test_llm_can_only_narrow_allow_list(self):
        # LLM tries to allow strategies that aren't in the regime's defaults
        # for CHOP (which is empty). Result: allow=[].
        good_resp = (json.dumps({
                         "regime": "CHOP", "confidence": 0.6,
                         "rationale": "directionless",
                         "allow_strategies": self.params["whitelist_strategies"],
                     }),
                     {"usage": {"prompt_tokens": 5, "completion_tokens": 5}},
                     1)
        with mock.patch.object(rc, "call_llm", return_value=good_resp):
            d = rc.classify_and_log(client=self.broker, params=self.params)
        self.assertEqual(d["regime"], "CHOP")
        self.assertEqual(d["allow_strategies"], [],
                         "CHOP default-allow=[] must intersect to []")


class TestGetTodayRegimeAndTTL(unittest.TestCase):
    def setUp(self):
        _patch_db_path(self)
        self.params = rc.load_params()

    def test_no_decision_returns_none(self):
        self.assertIsNone(rc.get_today_regime(params=self.params))

    def test_fresh_decision_returned(self):
        today = rc.today_trading_date()
        db.save_regime_decision(
            trading_date=today, source="llm", regime="RISK_ON",
            allow_strategies=["s1"], confidence=0.9, rationale="x",
        )
        d = rc.get_today_regime(params=self.params)
        self.assertIsNotNone(d)
        self.assertEqual(d["regime"], "RISK_ON")
        self.assertFalse(d["is_stale"])

    def test_within_ttl_returned_stale(self):
        # Two days ago — within 5d TTL.
        d2 = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        db.save_regime_decision(
            trading_date=d2, source="llm", regime="RISK_OFF",
            allow_strategies=[], confidence=0.5, rationale="x",
        )
        d = rc.get_today_regime(params=self.params)
        self.assertIsNotNone(d)
        self.assertEqual(d["regime"], "RISK_OFF")
        self.assertTrue(d["is_stale"])

    def test_beyond_ttl_returns_none(self):
        # 10 days ago — past 5d TTL.
        d10 = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
        db.save_regime_decision(
            trading_date=d10, source="llm", regime="RISK_ON",
            allow_strategies=["s1"], confidence=0.9, rationale="x",
        )
        self.assertIsNone(rc.get_today_regime(params=self.params))


# ---------------------------------------------------------------------------
# Runner gate integration tests
# ---------------------------------------------------------------------------

def _action(action="hold", symbol="SYM", notional_usd=0.0, reason=""):
    class _A:
        pass
    a = _A()
    a.action = action
    a.symbol = symbol
    a.notional_usd = notional_usd
    a.reason = reason
    return a


class _FakeAlpacaClient:
    def __init__(self):
        self.submitted_orders = []
        self.price = 100.0
        self.fill_status = "filled"
        self.fill_price = 100.0
        self.bars_data = [{"t": "x", "o": 100, "h": 101, "l": 99, "c": 100}]

    @staticmethod
    def is_crypto_symbol(symbol):
        return "/" in symbol

    def latest_stock_price(self, symbol):
        return self.price

    def latest_crypto_price(self, symbol):
        return self.price

    def stock_bars(self, symbol, *, timeframe, limit):
        if symbol == "SPY":
            return [{"t": "x", "o": 500, "h": 500, "l": 500, "c": 500}]
        return list(self.bars_data)

    def crypto_bars(self, symbol, *, timeframe, limit):
        return list(self.bars_data)

    def submit_market_order(self, symbol, side, *, qty=None, notional_usd=None):
        o = {"id": f"o-{len(self.submitted_orders)+1}",
             "status": self.fill_status,
             "filled_avg_price": self.fill_price,
             "qty": str(qty) if qty is not None else ""}
        self.submitted_orders.append({"symbol": symbol, "side": side,
                                      "qty": qty, "notional_usd": notional_usd})
        return o


class _RunnerGateBase(unittest.TestCase):
    def setUp(self):
        _patch_db_path(self)
        self.fake = _FakeAlpacaClient()
        cls = mock.MagicMock(return_value=self.fake)
        cls.is_crypto_symbol = _FakeAlpacaClient.is_crypto_symbol
        p1 = mock.patch.object(runner, "AlpacaClient", cls)
        p1.start(); self.addCleanup(p1.stop)
        p2 = mock.patch.object(runner, "is_us_equity_market_open", return_value=True)
        p2.start(); self.addCleanup(p2.stop)
        p3 = mock.patch.object(runner, "killswitch_active", return_value=False)
        p3.start(); self.addCleanup(p3.stop)

    def _patch_strategy(self, decide_fn, params):
        stub = mock.MagicMock()
        stub.decide = decide_fn
        p = mock.patch.object(runner, "load_strategy", return_value=(stub, params))
        p.start(); self.addCleanup(p.stop)

    def _decisions(self):
        with db.connect(_TEST_DB) as c:
            return [dict(r) for r in c.execute(
                "SELECT action, reason FROM decisions ORDER BY id ASC"
            ).fetchall()]

    def _runs(self):
        with db.connect(_TEST_DB) as c:
            return [dict(r) for r in c.execute(
                "SELECT outcome, detail FROM runs ORDER BY id ASC"
            ).fetchall()]


class TestRunnerGate(_RunnerGateBase):
    def test_gate_disabled_falls_through(self):
        """regime_gate=false (default) -> existing behavior unchanged."""
        decide_called = {"n": 0}

        def decide(*a, **k):
            decide_called["n"] += 1
            return _action("hold", "SYM", 0, "ok")

        self._patch_strategy(decide,
                             {"symbol": "SYM", "timeframe": "1Hour",
                              "bar_limit": 10, "notional_usd": 50.0})
        rc_code = runner.run("any")
        self.assertEqual(rc_code, 0)
        self.assertEqual(decide_called["n"], 1)

    def test_gate_pass_calls_decide(self):
        """regime_gate=true + strategy in allow_strategies -> decide() runs."""
        today = rc.today_trading_date()
        db.save_regime_decision(
            trading_date=today, source="llm", regime="RISK_ON",
            allow_strategies=["my_strat"], confidence=0.9,
            rationale="strong trend",
        )
        decide_called = {"n": 0}

        def decide(*a, **k):
            decide_called["n"] += 1
            return _action("hold", "SYM", 0, "ok")

        self._patch_strategy(decide,
                             {"symbol": "SYM", "timeframe": "1Hour",
                              "bar_limit": 10, "notional_usd": 50.0,
                              "regime_gate": True})
        rc_code = runner.run("my_strat")
        self.assertEqual(rc_code, 0)
        self.assertEqual(decide_called["n"], 1)

    def test_gate_skip_when_strategy_not_in_allow(self):
        """regime_gate=true + strategy NOT in allow_strategies -> skip_regime_block."""
        today = rc.today_trading_date()
        db.save_regime_decision(
            trading_date=today, source="llm", regime="RISK_OFF",
            allow_strategies=[], confidence=0.6,
            rationale="bear trend", fallback_reason=None,
        )
        decide_called = {"n": 0}

        def decide(*a, **k):
            decide_called["n"] += 1
            return _action("buy", "SYM", 50, "yolo")

        self._patch_strategy(decide,
                             {"symbol": "SYM", "timeframe": "1Hour",
                              "bar_limit": 10, "notional_usd": 50.0,
                              "regime_gate": True})
        rc_code = runner.run("my_strat")
        self.assertEqual(rc_code, 0)
        self.assertEqual(decide_called["n"], 0, "decide() must be skipped")
        self.assertEqual(self.fake.submitted_orders, [],
                         "no broker call when gate blocks")
        run_detail = self._runs()[0]["detail"]
        self.assertEqual(run_detail, "skip_regime_block")
        decision_actions = [d["action"] for d in self._decisions()]
        self.assertIn("skip_regime_block", decision_actions)

    def test_gate_no_decision_skips_regime_unknown(self):
        """regime_gate=true + no decision in db -> skip_regime_unknown.

        Default-safe: rather than trade blind, we skip the tick.
        """
        decide_called = {"n": 0}

        def decide(*a, **k):
            decide_called["n"] += 1
            return _action("buy", "SYM", 50, "yolo")

        self._patch_strategy(decide,
                             {"symbol": "SYM", "timeframe": "1Hour",
                              "bar_limit": 10, "notional_usd": 50.0,
                              "regime_gate": True})
        rc_code = runner.run("my_strat")
        self.assertEqual(rc_code, 0)
        self.assertEqual(decide_called["n"], 0)
        self.assertEqual(self._runs()[0]["detail"], "skip_regime_unknown")

    def test_gate_crypto_bypasses(self):
        """Crypto strategies skip the gate entirely (no SPY regime applies)."""
        decide_called = {"n": 0}

        def decide(*a, **k):
            decide_called["n"] += 1
            return _action("hold", "BTC/USD", 0, "ok")

        self._patch_strategy(decide,
                             {"symbol": "BTC/USD", "timeframe": "1Hour",
                              "bar_limit": 10, "notional_usd": 50.0,
                              "regime_gate": True})
        rc_code = runner.run("crypto_strat")
        self.assertEqual(rc_code, 0)
        self.assertEqual(decide_called["n"], 1, "crypto must bypass regime gate")


if __name__ == "__main__":
    unittest.main()
