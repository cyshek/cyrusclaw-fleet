"""Tier 2 daily LLM regime classifier.

Per design doc reports/TIER2_REGIME_CLASSIFIER_DESIGN_20260530T170702Z.md
and GATE.md Bar C.

Public API
----------
- get_today_regime(now_utc=None) -> dict | None
      Cheap read-path used by the runner gate on EVERY tick. Looks up the
      canonical regime_decisions row for today's NY trading date, applies
      TTL (>5 calendar days = stale -> caller should fall back), and
      returns a dict (or None if no row). NEVER calls the LLM.

- classify_and_log(now_utc=None, *, force=False) -> dict
      Write-path used by the daily cron and the --run CLI. Builds the
      feature bundle, calls the LLM (with strict-JSON + schema validation),
      logs to llm_decisions, persists the canonical row to regime_decisions.
      ANY failure -> fall back to regime_uptrend(spy_closes, 50) and write
      a source='fallback' row instead. NEVER raises.

      If `force=False` (default) and a row already exists for today, the
      function returns the existing row WITHOUT calling the LLM. Idempotent.

- code_fallback_decision(spy_closes, *, trading_date, reason) -> dict
      Pure-Python regime computation from SPY closes using
      strategies._lib.indicators.regime_uptrend(_, 50). Used both as the
      fallback inside classify_and_log and as the runner's hot-path
      backup when no regime row exists / TTL exceeded. No DB writes.

CLI
---
    python3 -m runner.regime_classifier --run
        Run the classifier once. Exits 0 on success (LLM OR fallback path).
        Idempotent: if today's row exists, prints "already have decision"
        and exits 0 without calling the LLM.

    python3 -m runner.regime_classifier --run --force
        Re-classify even if today's row exists (UPSERT). Useful for testing.

    python3 -m runner.regime_classifier --show [--date YYYY-MM-DD]
        Print the canonical regime row for the given date (default today).

Design-doc open question resolutions (see implementation report for full):
- Live model: gpt-4o-mini (cheapest reasonable, strong JSON mode).
- VIX/breadth: SPY-derived vol proxy only (no external API in v1).
- Confidence floor: configurable via classifier_params.json (default off).
- CHOP mapping: block all (default-safe).
- Table naming: BOTH llm_decisions (Bar C.3 literal) AND regime_decisions
  (denormalized per-day verdict). Joined via llm_decision_id FK-ish.
- Whitelist source: hand-maintained in classifier_params.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from urllib import error, request

from . import db
from .market_hours import is_nyse_holiday, _ET  # type: ignore[attr-defined]

# Strategies that import this module must not crash if the indicators
# helper is missing; defer that import.

WORKSPACE = Path(__file__).resolve().parent.parent
PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_TXT_PATH = PROMPT_DIR / "regime_classifier_v1.txt"
PROMPT_SCHEMA_PATH = PROMPT_DIR / "regime_classifier_v1.schema.json"
CLASSIFIER_PARAMS_PATH = Path(__file__).resolve().parent / "classifier_params.json"

# Default classifier configuration. Overridden by classifier_params.json on disk.
DEFAULT_PARAMS: dict[str, Any] = {
    "strategy": "regime_classifier_v1",
    "purpose": "regime_classification",
    "model": "gpt-4o-mini",
    "temperature": 0.0,
    "seed": 42,
    "request_timeout_s": 30,
    "ttl_calendar_days": 5,
    "confidence_floor": 0.0,            # 0.0 = no floor; e.g. 0.5 = below-floor -> fallback
    "regime_fallback_period": 50,        # SPY SMA period for code fallback
    "whitelist_strategies": [
        "breakout_xlk",
        "breakout_xlk_regime",
        "sma_crossover_qqq",
        "sma_crossover_qqq_regime",
        "sma_crossover_qqq_rth",
        "momentum_arkk",
        "rsi_mean_revert_iwm",
        "buy_and_hold_spy",
    ],
    # Mapping from regime -> default-allowed strategies. The LLM's
    # allow_strategies is intersected with regime_defaults[regime] before
    # persistence, so the LLM can be MORE conservative but never expand.
    "regime_defaults": {
        # All long-only trend / breakout strategies allowed.
        "RISK_ON": [
            "breakout_xlk", "breakout_xlk_regime",
            "sma_crossover_qqq", "sma_crossover_qqq_regime",
            "sma_crossover_qqq_rth", "momentum_arkk",
            "rsi_mean_revert_iwm", "buy_and_hold_spy",
        ],
        # No mean-reverters yet; CHOP blocks all per design \u00a73.
        "CHOP": [],
        # Long-only book = no shorts to take advantage; block all.
        "RISK_OFF": [],
    },
    "model_pricing_per_mtok": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o":      {"input": 5.00, "output": 15.00},
    },
}


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_params() -> dict[str, Any]:
    """Load classifier_params.json on top of DEFAULT_PARAMS. Missing file
    is fine (returns defaults). This file is the single live-config knob;
    the prompt + schema are frozen separately."""
    params = json.loads(json.dumps(DEFAULT_PARAMS))  # deep copy
    if CLASSIFIER_PARAMS_PATH.exists():
        try:
            overrides = json.loads(CLASSIFIER_PARAMS_PATH.read_text())
            if isinstance(overrides, dict):
                params.update(overrides)
        except (ValueError, OSError):
            pass
    return params


def load_prompt() -> tuple[str, dict]:
    """Read frozen prompt + schema. Both files must exist or this raises;
    the runner gate degrades to fallback in that case."""
    prompt = PROMPT_TXT_PATH.read_text()
    schema = json.loads(PROMPT_SCHEMA_PATH.read_text())
    return prompt, schema


def prompt_hash(prompt_text: str, schema: dict) -> str:
    """SHA-256 of (prompt || canonicalized schema). Stable across runs.
    Bar C.4: frozen at deployment; any change = new strategy version."""
    canon = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    h = hashlib.sha256()
    h.update(prompt_text.encode("utf-8"))
    h.update(b"\x00")
    h.update(canon.encode("utf-8"))
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def today_trading_date(now_utc: Optional[datetime] = None) -> str:
    """Return YYYY-MM-DD in America/New_York for `now_utc`. Cron is wall-clock
    based on ET, so the runner's "today" must match."""
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    if _ET is not None:
        et = now_utc.astimezone(_ET)
    else:  # pragma: no cover
        et = now_utc
    return et.date().isoformat()


def _days_between_iso(a: str, b: str) -> int:
    """Calendar days between two YYYY-MM-DD strings (abs)."""
    da = date.fromisoformat(a)
    db_ = date.fromisoformat(b)
    return abs((db_ - da).days)


# ---------------------------------------------------------------------------
# Feature builder
# ---------------------------------------------------------------------------

def build_features(client, *, params: Optional[dict] = None) -> dict:
    """Assemble the feature bundle the LLM sees.

    Uses Alpaca SPY 1Day bars only (v1 per design \u00a72.2). Returns a dict
    of native-Python numbers (no numpy). Caller is responsible for trapping
    AlpacaError; we don't import the broker class here to keep this module
    testable in isolation (we accept any duck-typed object with stock_bars).
    """
    params = params or load_params()
    spy_bars = client.stock_bars("SPY", timeframe="1Day", limit=260)
    closes = [float(b["c"]) for b in (spy_bars or [])]
    if len(closes) < 20:
        raise ValueError(f"insufficient SPY bars for features: {len(closes)}")

    last = closes[-1]
    sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
    sma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
    ret_5d = (last - closes[-6]) / closes[-6] if len(closes) > 5 and closes[-6] else None
    ret_20d = (last - closes[-21]) / closes[-21] if len(closes) > 20 and closes[-21] else None
    high_52w = max(closes[-min(252, len(closes)):])
    dist_high = (last - high_52w) / high_52w if high_52w else None

    # SPY-derived vol proxy (no VIX): stdev of daily returns over 20d.
    if len(closes) >= 22:
        daily_rets = [
            (closes[i] - closes[i - 1]) / closes[i - 1]
            for i in range(-20, 0)
            if closes[i - 1]
        ]
        realized_vol_20d = statistics.pstdev(daily_rets) if len(daily_rets) > 1 else 0.0
    else:
        realized_vol_20d = None

    # Recent regime history for self-stability (last 5 days from db).
    recent_regime: list[dict] = []
    try:
        with db.connect() as c:
            rows = c.execute(
                "SELECT trading_date, regime, confidence, source FROM regime_decisions "
                "ORDER BY trading_date DESC LIMIT 5"
            ).fetchall()
        recent_regime = [dict(r) for r in rows]
    except Exception:
        recent_regime = []

    return {
        "spy_close": round(last, 4),
        "spy_sma_50": round(sma50, 4) if sma50 is not None else None,
        "spy_sma_200": round(sma200, 4) if sma200 is not None else None,
        "spy_return_5d": round(ret_5d, 6) if ret_5d is not None else None,
        "spy_return_20d": round(ret_20d, 6) if ret_20d is not None else None,
        "spy_dist_from_52w_high_pct": round(dist_high, 6) if dist_high is not None else None,
        "spy_realized_vol_20d": round(realized_vol_20d, 6) if realized_vol_20d is not None else None,
        "bars_available": len(closes),
        "recent_regime_history": recent_regime,
        "whitelist_strategies": params.get("whitelist_strategies", []),
        # Carry SPY closes through for the fallback path. Stripped from
        # the LLM payload below to keep the prompt cheap.
        "_spy_closes": closes,
    }


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class SchemaError(Exception):
    pass


def validate_decision(obj: Any, schema: dict, *,
                      whitelist: list[str]) -> dict:
    """Lightweight JSONSchema-ish validator. We don't pull in jsonschema for
    a 4-field object. Returns the normalized dict (with allow_strategies
    intersected against `whitelist`). Raises SchemaError on failure.

    Note: confidence range violations are CLAMPED + logged, not rejected
    (per design \u00a78 \"do NOT reject decision on this alone\"). Rationale
    over-length is TRUNCATED, not rejected.
    """
    if not isinstance(obj, dict):
        raise SchemaError(f"top-level must be object, got {type(obj).__name__}")

    regime = obj.get("regime")
    if regime not in ("RISK_ON", "RISK_OFF", "CHOP"):
        raise SchemaError(f"invalid regime: {regime!r}")

    conf = obj.get("confidence")
    if not isinstance(conf, (int, float)) or isinstance(conf, bool):
        raise SchemaError(f"confidence must be number, got {type(conf).__name__}")
    conf = float(conf)
    if conf < 0.0:
        conf = 0.0
    elif conf > 1.0:
        conf = 1.0

    rationale = obj.get("rationale", "")
    if not isinstance(rationale, str):
        raise SchemaError(f"rationale must be string, got {type(rationale).__name__}")
    if len(rationale) > 200:
        rationale = rationale[:200]
    rationale = rationale.replace("\n", " ").replace("\r", " ")

    allow = obj.get("allow_strategies")
    if not isinstance(allow, list):
        raise SchemaError(f"allow_strategies must be array, got {type(allow).__name__}")
    if not all(isinstance(s, str) for s in allow):
        raise SchemaError("allow_strategies items must be strings")
    # Drop names not on the whitelist (silent per design \u00a78).
    whitelist_set = set(whitelist)
    allow_filtered = [s for s in allow if s in whitelist_set]

    return {
        "regime": regime,
        "confidence": conf,
        "rationale": rationale,
        "allow_strategies": allow_filtered,
    }


# ---------------------------------------------------------------------------
# LLM call (OpenAI Chat Completions, urllib only - no SDK dependency)
# ---------------------------------------------------------------------------

class LLMError(Exception):
    pass


def call_llm(features: dict, *, params: dict, prompt_text: str) -> tuple[str, dict, int]:
    """POST to OpenAI Chat Completions. Returns (raw_content, response_meta,
    latency_ms). Raises LLMError on any failure (caller catches and falls back).

    Strips the underscore-prefixed `_spy_closes` from the user payload to
    keep the prompt cheap; that key is for the local fallback path only.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise LLMError("missing_api_key")

    user_payload = {k: v for k, v in features.items() if not k.startswith("_")}
    user_msg = json.dumps(user_payload, separators=(",", ":"))

    body = {
        "model": params["model"],
        "temperature": float(params.get("temperature", 0.0)),
        "messages": [
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": user_msg},
        ],
        # Strict JSON mode (supported by gpt-4o family + gpt-4o-mini).
        "response_format": {"type": "json_object"},
    }
    seed = params.get("seed")
    if seed is not None:
        body["seed"] = int(seed)

    data = json.dumps(body).encode("utf-8")
    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    t0 = time.monotonic()
    try:
        with request.urlopen(req, timeout=float(params.get("request_timeout_s", 30))) as resp:
            payload = resp.read().decode("utf-8")
    except error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise LLMError(f"http_{e.code}: {detail}") from e
    except error.URLError as e:
        raise LLMError(f"url_error: {e.reason}") from e
    except Exception as e:  # noqa: BLE001
        raise LLMError(f"network_error: {e}") from e
    latency_ms = int((time.monotonic() - t0) * 1000)

    try:
        resp_obj = json.loads(payload)
    except ValueError as e:
        raise LLMError(f"response_not_json: {e}") from e

    try:
        content = resp_obj["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"response_missing_content: {e}") from e

    if not isinstance(content, str) or not content.strip():
        raise LLMError("empty_content")

    return content, resp_obj, latency_ms


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int,
                      pricing: dict) -> float:
    """Per-MTok pricing -> USD. Returns 0.0 if model not in pricing table."""
    p = pricing.get(model)
    if not p:
        return 0.0
    return (prompt_tokens * p["input"] + completion_tokens * p["output"]) / 1_000_000.0


# ---------------------------------------------------------------------------
# Fallback path
# ---------------------------------------------------------------------------

def code_fallback_decision(spy_closes: list[float], *,
                            trading_date: str,
                            reason: str,
                            params: Optional[dict] = None) -> dict:
    """Compute a regime verdict from SPY closes alone using regime_uptrend(_, 50).

    Returns a dict shaped like a regime_decisions row (source='fallback',
    NO llm_decision_id). Caller may persist via save_regime_decision or
    consume directly (the runner gate does the latter when DB has no row).
    """
    params = params or load_params()
    period = int(params.get("regime_fallback_period", 50))
    # Deferred import; avoids hard dep when this module is imported by tests
    # that monkeypatch the indicators module.
    from strategies._lib.indicators import regime_uptrend  # noqa: WPS433
    uptrend = regime_uptrend(spy_closes, period) if spy_closes else True
    regime = "RISK_ON" if uptrend else "RISK_OFF"
    defaults = params.get("regime_defaults", {})
    allow = list(defaults.get(regime, []))
    return {
        "trading_date": trading_date,
        "source": "fallback",
        "regime": regime,
        "confidence": None,
        "rationale": f"code fallback regime_uptrend(SPY, {period}): uptrend={uptrend}",
        "allow_strategies": allow,
        "llm_decision_id": None,
        "fallback_reason": reason,
    }


# ---------------------------------------------------------------------------
# Read path: what the runner gate uses every tick.
# ---------------------------------------------------------------------------

def get_today_regime(now_utc: Optional[datetime] = None,
                     *, params: Optional[dict] = None) -> Optional[dict]:
    """Return the regime decision for today's NY trading date.

    Behavior:
      1. Look up regime_decisions WHERE trading_date == today_ny.
      2. If found, return it.
      3. If not found, return the most recent decision IFF it's within
         ttl_calendar_days. Beyond the TTL -> None (caller falls back).
      4. If no decision ever existed -> None.

    Returns dict with keys: trading_date, source, regime, confidence,
    rationale, allow_strategies, llm_decision_id, fallback_reason, plus
    a synthetic 'is_stale' bool (True if returned row's trading_date != today).
    """
    params = params or load_params()
    today_iso = today_trading_date(now_utc)
    row = db.get_regime_decision_for_date(today_iso)
    if row:
        row["is_stale"] = False
        return row
    latest = db.latest_regime_decision()
    if not latest:
        return None
    ttl_days = int(params.get("ttl_calendar_days", 5))
    age = _days_between_iso(latest["trading_date"], today_iso)
    if age > ttl_days:
        return None
    latest["is_stale"] = True
    return latest


# ---------------------------------------------------------------------------
# Write path: cron / CLI entry point.
# ---------------------------------------------------------------------------

def classify_and_log(now_utc: Optional[datetime] = None,
                     *,
                     force: bool = False,
                     client=None,
                     params: Optional[dict] = None) -> dict:
    """Run one classification pass for today's NY trading date.

    Idempotent: if a row already exists for today and force=False, returns
    that row WITHOUT calling the LLM.

    Failure mode contract: NEVER raises. On any error path (no params, no
    prompt file, broker fetch fail, LLM fail, parse fail, schema fail) we
    write a source='fallback' row and return it.
    """
    params = params or load_params()
    today_iso = today_trading_date(now_utc)

    if not force:
        existing = db.get_regime_decision_for_date(today_iso)
        if existing:
            existing["already_existed"] = True
            return existing

    # Lazy-import the real broker; tests inject `client=`.
    if client is None:
        try:
            from .broker_alpaca import AlpacaClient  # noqa: WPS433
            client = AlpacaClient()
        except Exception as e:  # noqa: BLE001
            # Can't even build a client -> write fallback with no SPY data.
            decision = code_fallback_decision(
                [], trading_date=today_iso,
                reason=f"alpaca_client_init_failed: {e}",
                params=params,
            )
            rid = db.save_regime_decision(**decision)
            decision["id"] = rid
            return decision

    # Build features. Failure here -> fallback with zero SPY data; the
    # downstream regime_uptrend returns True by convention, but we still
    # mark the row as fallback with reason.
    try:
        features = build_features(client, params=params)
    except Exception as e:  # noqa: BLE001
        decision = code_fallback_decision(
            [], trading_date=today_iso,
            reason=f"feature_build_failed: {e}",
            params=params,
        )
        rid = db.save_regime_decision(**decision)
        decision["id"] = rid
        return decision

    spy_closes = features.get("_spy_closes", []) or []

    try:
        prompt_text, schema = load_prompt()
    except Exception as e:  # noqa: BLE001
        decision = code_fallback_decision(
            spy_closes, trading_date=today_iso,
            reason=f"prompt_load_failed: {e}", params=params,
        )
        rid = db.save_regime_decision(**decision)
        decision["id"] = rid
        return decision

    phash = prompt_hash(prompt_text, schema)
    model = params["model"]
    temperature = float(params.get("temperature", 0.0))
    seed = params.get("seed")
    purpose = params.get("purpose", "regime_classification")
    strategy_name = params.get("strategy", "regime_classifier_v1")

    inputs_for_log = {k: v for k, v in features.items() if not k.startswith("_")}
    inputs_json = json.dumps(inputs_for_log, separators=(",", ":"))

    # Try the LLM. Catch ANY exception. Each failure mode maps to a
    # specific `error` string for ops triage.
    raw_content: Optional[str] = None
    resp_meta: dict = {}
    latency_ms: Optional[int] = None
    error_reason: Optional[str] = None
    parsed: Optional[dict] = None
    try:
        raw_content, resp_meta, latency_ms = call_llm(
            features, params=params, prompt_text=prompt_text,
        )
    except LLMError as e:
        error_reason = str(e)

    if error_reason is None and raw_content is not None:
        # Parse JSON
        try:
            obj = json.loads(raw_content)
        except ValueError as e:
            error_reason = f"json_parse_failed: {e}"
        else:
            try:
                parsed = validate_decision(
                    obj, schema, whitelist=params.get("whitelist_strategies", []),
                )
            except SchemaError as e:
                error_reason = f"schema_failed: {e}"

    # Token usage + cost estimate
    cost_usd = None
    model_version = None
    if resp_meta:
        usage = resp_meta.get("usage") or {}
        pt = int(usage.get("prompt_tokens", 0))
        ct = int(usage.get("completion_tokens", 0))
        cost_usd = round(
            estimate_cost_usd(model, pt, ct, params.get("model_pricing_per_mtok", {})),
            8,
        )
        model_version = resp_meta.get("system_fingerprint") or resp_meta.get("model")

    # Log the LLM call attempt (success or failure both audit-logged).
    llm_id = db.log_llm_decision(
        strategy=strategy_name,
        purpose=purpose,
        model=model,
        model_version=model_version,
        temperature=temperature,
        seed=int(seed) if seed is not None else None,
        prompt_hash=phash,
        prompt_version="regime_classifier_v1",
        inputs_json=inputs_json,
        response_raw=raw_content,
        response_parsed=json.dumps(parsed) if parsed else None,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        ok=(parsed is not None),
        error=error_reason,
    )

    # Confidence-floor check: a parsed-but-low-confidence decision can
    # optionally be demoted to the code fallback path. Off by default.
    if parsed is not None:
        floor = float(params.get("confidence_floor", 0.0))
        if floor > 0 and parsed["confidence"] < floor:
            error_reason = f"confidence_below_floor: {parsed['confidence']} < {floor}"
            parsed = None

    if parsed is None:
        decision = code_fallback_decision(
            spy_closes, trading_date=today_iso,
            reason=error_reason or "unknown_failure",
            params=params,
        )
        # Cross-ref to the failed LLM call so audit-trail joins work.
        decision["llm_decision_id"] = llm_id
        rid = db.save_regime_decision(**decision)
        decision["id"] = rid
        return decision

    # Intersect LLM-allowed with regime-default-allowed (LLM may only narrow).
    defaults = params.get("regime_defaults", {})
    default_allow = set(defaults.get(parsed["regime"], []))
    llm_allow = set(parsed["allow_strategies"])
    final_allow = sorted(llm_allow & default_allow)

    decision = {
        "trading_date": today_iso,
        "source": "llm",
        "regime": parsed["regime"],
        "confidence": parsed["confidence"],
        "rationale": parsed["rationale"],
        "allow_strategies": final_allow,
        "llm_decision_id": llm_id,
        "fallback_reason": None,
    }
    rid = db.save_regime_decision(**decision)
    decision["id"] = rid
    return decision


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_run(args: argparse.Namespace) -> int:
    db.init_db()
    decision = classify_and_log(force=args.force)
    if decision.get("already_existed"):
        print(f"already have decision for {decision['trading_date']}: "
              f"{decision['regime']} (source={decision['source']})")
        return 0
    src = decision["source"]
    extras = []
    if src == "llm":
        extras.append(f"conf={decision.get('confidence')}")
    else:
        extras.append(f"reason={decision.get('fallback_reason')!r}")
    extras.append(f"allow={decision.get('allow_strategies')}")
    print(f"[regime_classifier] {decision['trading_date']} "
          f"regime={decision['regime']} source={src} "
          + " ".join(extras))
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    target = args.date or today_trading_date()
    row = db.get_regime_decision_for_date(target)
    if not row:
        print(f"no regime decision for {target}")
        return 1
    print(json.dumps(row, indent=2, default=str))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="runner.regime_classifier")
    sub = ap.add_subparsers(dest="cmd")
    # Accept --run / --show at TOP level for the task-spec'd invocation
    # form `python3 -m runner.regime_classifier --run`.
    ap.add_argument("--run", action="store_true",
                    help="run classifier once for today")
    ap.add_argument("--show", action="store_true",
                    help="print today's regime decision row")
    ap.add_argument("--date", help="YYYY-MM-DD (with --show)")
    ap.add_argument("--force", action="store_true",
                    help="re-classify even if today's row exists")
    args = ap.parse_args(argv)
    if args.show:
        return _cmd_show(args)
    if args.run:
        return _cmd_run(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
