"""Thin Alpaca wrapper. Paper-only.

Refuses to operate against the live endpoint. Loads credentials from .env at
workspace root (key/secret + base URL). Exposes the minimum we need for Session 1:

    - account()            -> dict
    - get_position(symbol) -> dict | None
    - latest_price(symbol) -> float
    - submit_market_order(symbol, side, notional_usd) -> dict

Crypto symbols use Alpaca's slash form, e.g. 'BTC/USD'.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib import error, request


PAPER_HOST_FRAGMENT = "paper-api.alpaca.markets"
WORKSPACE = Path(__file__).resolve().parent.parent
ENV_PATH = WORKSPACE / ".env"


def _load_env(path: Path = ENV_PATH) -> None:
    """Load KEY=VALUE pairs from .env without overwriting real env vars."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


class AlpacaError(RuntimeError):
    pass


@dataclass
class AlpacaConfig:
    key_id: str
    secret: str
    trade_base: str
    data_base: str

    @classmethod
    def from_env(cls) -> "AlpacaConfig":
        _load_env()
        key_id = os.environ.get("APCA_API_KEY_ID", "").strip()
        secret = os.environ.get("APCA_API_SECRET_KEY", "").strip()
        trade_base = os.environ.get(
            "APCA_API_BASE_URL", "https://paper-api.alpaca.markets"
        ).rstrip("/")
        data_base = os.environ.get(
            "APCA_API_DATA_URL", "https://data.alpaca.markets"
        ).rstrip("/")
        if not key_id or not secret:
            raise AlpacaError(
                "Missing APCA_API_KEY_ID / APCA_API_SECRET_KEY in .env"
            )
        if PAPER_HOST_FRAGMENT not in trade_base:
            raise AlpacaError(
                f"Refusing to use non-paper trade base: {trade_base!r}. "
                "This bench is paper-only."
            )
        return cls(key_id=key_id, secret=secret,
                   trade_base=trade_base, data_base=data_base)


class AlpacaClient:
    def __init__(self, cfg: Optional[AlpacaConfig] = None):
        self.cfg = cfg or AlpacaConfig.from_env()

    # -- low-level ---------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "APCA-API-KEY-ID": self.cfg.key_id,
            "APCA-API-SECRET-KEY": self.cfg.secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, url: str,
                 body: Optional[dict[str, Any]] = None,
                 timeout: float = 15.0) -> Any:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = request.Request(url, data=data, method=method, headers=self._headers())
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                payload = resp.read().decode("utf-8")
                return json.loads(payload) if payload else {}
        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise AlpacaError(f"HTTP {e.code} {method} {url}: {detail}") from e
        except error.URLError as e:
            raise AlpacaError(f"URLError {method} {url}: {e}") from e

    # -- trade API ---------------------------------------------------------
    def account(self) -> dict[str, Any]:
        return self._request("GET", f"{self.cfg.trade_base}/v2/account")

    def get_position(self, symbol: str) -> Optional[dict[str, Any]]:
        # Alpaca expects URL-safe symbol; BTC/USD -> BTCUSD on the positions endpoint.
        sym = symbol.replace("/", "")
        try:
            return self._request("GET", f"{self.cfg.trade_base}/v2/positions/{sym}")
        except AlpacaError as e:
            if "HTTP 404" in str(e):
                return None
            raise

    @staticmethod
    def is_crypto_symbol(symbol: str) -> bool:
        """Crypto symbols use Alpaca slash form, e.g. 'BTC/USD'. Stocks don't."""
        return "/" in symbol

    @classmethod
    def default_tif(cls, symbol: str) -> str:
        # Crypto supports 'gtc'; stocks must use 'day' (gtc is rejected for equities
        # on market orders in paper unless extended_hours+limit).
        return "gtc" if cls.is_crypto_symbol(symbol) else "day"

    def submit_market_order(self, symbol: str, side: str,
                            notional_usd: Optional[float] = None,
                            qty: Optional[float] = None,
                            time_in_force: Optional[str] = None) -> dict[str, Any]:
        if (notional_usd is None) == (qty is None):
            raise ValueError("Provide exactly one of notional_usd or qty")
        if side not in ("buy", "sell"):
            raise ValueError(f"bad side {side!r}")
        if time_in_force is None:
            time_in_force = self.default_tif(symbol)
        body: dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": "market",
            "time_in_force": time_in_force,
        }
        if notional_usd is not None:
            body["notional"] = f"{notional_usd:.2f}"
        else:
            body["qty"] = f"{qty}"
        return self._request("POST", f"{self.cfg.trade_base}/v2/orders", body=body)

    # -- data API ----------------------------------------------------------
    def latest_crypto_price(self, symbol: str) -> float:
        """symbol like 'BTC/USD'."""
        sym = symbol.upper()
        url = f"{self.cfg.data_base}/v1beta3/crypto/us/latest/trades?symbols={sym}"
        payload = self._request("GET", url)
        trades = payload.get("trades", {})
        rec = trades.get(sym) or next(iter(trades.values()), None)
        if not rec or "p" not in rec:
            raise AlpacaError(f"No latest trade for {symbol}: {payload!r}")
        return float(rec["p"])

    def crypto_bars(self, symbol: str, timeframe: str = "1Hour",
                    limit: int = 200) -> list[dict[str, Any]]:
        """Return list of OHLCV bars, oldest first.

        Each bar: {t, o, h, l, c, v}. timeframe e.g. '15Min','1Hour','4Hour','1Day'.
        Alpaca defaults `start` to today; we backfill enough history to honor `limit`.
        """
        from urllib.parse import quote
        from datetime import datetime, timedelta, timezone
        sym = symbol.upper()
        # Pick a start far enough back that `limit` bars exist; tf-aware.
        tf_minutes = {"1Min": 1, "5Min": 5, "15Min": 15, "30Min": 30,
                      "1Hour": 60, "2Hour": 120, "4Hour": 240,
                      "6Hour": 360, "12Hour": 720, "1Day": 1440}.get(timeframe, 60)
        # 1.5x cushion for missing/aggregated bars
        start_dt = datetime.now(timezone.utc) - timedelta(minutes=int(limit * tf_minutes * 1.5) + tf_minutes)
        start = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = (f"{self.cfg.data_base}/v1beta3/crypto/us/bars"
               f"?symbols={quote(sym)}&timeframe={timeframe}&limit={limit}"
               f"&start={start}&sort=desc")
        payload = self._request("GET", url)
        bars_by_sym = payload.get("bars", {})
        rows = bars_by_sym.get(sym) or next(iter(bars_by_sym.values()), [])
        rows = list(rows or [])
        rows.reverse()  # oldest first for indicator math
        return rows

    # -- stocks data API ---------------------------------------------------
    def latest_stock_price(self, symbol: str) -> float:
        """symbol like 'SPY'. Uses /v2/stocks/{symbol}/trades/latest.

        Free-tier (IEX) feed is selected via ?feed=iex. SIP is paid.
        """
        sym = symbol.upper()
        url = f"{self.cfg.data_base}/v2/stocks/{sym}/trades/latest?feed=iex"
        payload = self._request("GET", url)
        trade = payload.get("trade") or {}
        if "p" not in trade:
            raise AlpacaError(f"No latest trade for {symbol}: {payload!r}")
        return float(trade["p"])

    def stock_bars(self, symbol: str, timeframe: str = "1Hour",
                   limit: int = 200) -> list[dict[str, Any]]:
        """Return OHLCV stock bars, oldest first. Mirrors crypto_bars() shape.

        Uses /v2/stocks/{symbol}/bars with feed=iex (free tier; SIP is paid).
        """
        from urllib.parse import quote
        from datetime import datetime, timedelta, timezone
        sym = symbol.upper()
        tf_minutes = {"1Min": 1, "5Min": 5, "15Min": 15, "30Min": 30,
                      "1Hour": 60, "2Hour": 120, "4Hour": 240,
                      "6Hour": 360, "12Hour": 720, "1Day": 1440}.get(timeframe, 60)
        # Stocks trade ~6.5h/day, 5d/wk = ~32.5h/wk = ~19% of clock time.
        # Need ~5x cushion minimum, plus a hard minimum so tiny `limit` calls
        # still span at least one trading day. For 1Day timeframe, cushion 7x
        # (weekends + holidays).
        if timeframe == "1Day":
            cushion_min = int(limit * tf_minutes * 1.7) + tf_minutes * 7
        else:
            cushion_min = max(int(limit * tf_minutes * 6) + tf_minutes,
                              60 * 24 * 4)  # ≥ 4 calendar days
        start_dt = datetime.now(timezone.utc) - timedelta(minutes=cushion_min)
        start = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = (f"{self.cfg.data_base}/v2/stocks/{quote(sym)}/bars"
               f"?timeframe={timeframe}&limit={limit}&feed=iex"
               f"&start={start}&sort=desc&adjustment=raw")
        payload = self._request("GET", url)
        rows = payload.get("bars") or []
        rows = list(rows)
        rows.reverse()  # oldest first
        return rows

    def get_order(self, order_id: str) -> dict[str, Any]:
        """GET /v2/orders/{id} — fetch current order status from Alpaca.

        Used by the runner's reconcile step after submit to capture the
        post-submit settled state (filled / canceled / rejected / etc.)
        instead of recording the transient `pending_new` / `accepted`
        status returned by POST /v2/orders.
        """
        return self._request("GET",
                             f"{self.cfg.trade_base}/v2/orders/{order_id}")

    def close_position(self, symbol: str) -> dict[str, Any]:
        """Close the full position in `symbol` at market."""
        sym = symbol.replace("/", "")
        return self._request("DELETE",
                             f"{self.cfg.trade_base}/v2/positions/{sym}")


def smoke_test() -> None:
    """Quick auth check. Prints account status; never logs secrets."""
    c = AlpacaClient()
    acct = c.account()
    print(f"Alpaca paper auth OK. "
          f"status={acct.get('status')} "
          f"cash=${acct.get('cash')} "
          f"buying_power=${acct.get('buying_power')} "
          f"crypto_tier={acct.get('crypto_tier')}")


if __name__ == "__main__":
    smoke_test()
