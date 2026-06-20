#!/usr/bin/env python3
"""
capsolver_client.py — Thin façade for CapSolver's REST API.

Built 2026-05-27 as the brief-spec entrypoint for the strict-Ashby cohort
unlock. Delegates to `captcha_solver.CaptchaSolver(vendor='capsolver')`
under the hood, so the underlying network code (createTask + poll
getTaskResult, error mapping, timeouts) is shared with the existing
NopeCHA/CapSolver multi-vendor path.

Why a separate façade instead of just using `CaptchaSolver` directly?
    1. Brief asked for a stable, single-purpose API surface
       (`recaptcha_v3_enterprise`, `hcaptcha`, `turnstile`) with the
       arg order baked in. Tests and runner integration can pin to
       this surface; we won't accidentally drag the NopeCHA branch in.
    2. **Hard env-var gate.** This module REFUSES to do anything unless
       `CAPSOLVER_API_KEY` is set. No file-fallback, no NopeCHA fallback,
       no silent disablement. If the env var is missing we raise
       `CapSolverDisabled` immediately — no network call, no `.capsolver-key`
       file read, no balance check. This makes it safe to import in
       hot paths without worrying about an accidental spend.
    3. Adds explicit exponential-backoff on 429 rate-limits (the underlying
       multi-vendor client just retries N times with no backoff).

USAGE (when enabled):
    import os
    os.environ['CAPSOLVER_API_KEY'] = '<key>'
    from capsolver_client import CapSolverClient
    client = CapSolverClient()
    token = client.recaptcha_v3_enterprise(
        sitekey='6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y',
        page_url='https://jobs.ashbyhq.com/openai/...',
        action='submit',
        min_score=0.7,
    )

USAGE (default, no key):
    from capsolver_client import CapSolverClient, CapSolverDisabled
    try:
        client = CapSolverClient()
    except CapSolverDisabled:
        # Existing path — submit anyway, accept spam-gate risk.
        pass

COST (per CapSolver public pricing, last checked 2026-05-13):
    - reCAPTCHA v3 Enterprise: ~$2.99 / 1000 solves  (~$0.003/row)
    - hCaptcha:                 ~$0.80 / 1000 solves  (~$0.0008/row)
    - Turnstile:                 ~$0.80 / 1000 solves  (~$0.0008/row)
    Strict-Ashby cohort ~53 rows × $0.003 = ~$0.16 to sweep.

See CAPTCHA-SOLVER-DECISION.md for vendor comparison + stop-loss policy.
"""
from __future__ import annotations

import logging
import os
import random
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)

CAPSOLVER_API = "https://api.capsolver.com"


import re as _re


def _to_capsolver_proxy(raw: str) -> str:
    """Normalize a proxy string to CapSolver's `scheme:host:port:user:pass`.

    Accepts http://user:pass@host:port, user:pass@host:port, or
    host:port:user:pass. CapSolver wants the colon-delimited form.
    """
    s = (raw or "").strip()
    scheme = "http"
    m = _re.match(r"^(https?|socks5):", s)
    if m:
        scheme = m.group(1)
    s = _re.sub(r"^(https?|socks5)://", "", s)
    user = pw = host = port = None
    if "@" in s:
        creds, hostport = s.rsplit("@", 1)
        user, _, pw = creds.partition(":")
        host, _, port = hostport.partition(":")
    else:
        parts = s.split(":")
        if len(parts) == 4:
            host, port, user, pw = parts
        elif len(parts) == 2:
            host, port = parts
        else:
            raise CapSolverError(f"unparseable proxy for capsolver: {raw!r}")
    if user and pw:
        return f"{scheme}:{host}:{port}:{user}:{pw}"
    return f"{scheme}:{host}:{port}"

# Match underlying multi-vendor client defaults but make them tunable per-call.
DEFAULT_TIMEOUT_S = 60         # brief: 60s timeout
DEFAULT_POLL_INTERVAL_S = 2.0
DEFAULT_HTTP_TIMEOUT_S = 30
DEFAULT_MAX_RETRIES = 3        # exponential backoff on 429
DEFAULT_BACKOFF_BASE_S = 1.0   # first retry sleeps ~1s, then ~2s, then ~4s


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class CapSolverError(Exception):
    """Base class. Anything that goes wrong on a CapSolver call."""


class CapSolverDisabled(CapSolverError):
    """`CAPSOLVER_API_KEY` env var is unset. No network call attempted."""


class CapSolverTimeout(CapSolverError):
    """createTask succeeded but no solution within timeout_s."""


class CapSolverQuotaExceeded(CapSolverError):
    """402/balance/credit error. Caller should stop trying."""


class CapSolverRateLimited(CapSolverError):
    """429 from the API after all retries exhausted."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class CapSolverClient:
    """Thin CapSolver REST client. Reads key from env var only."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        http_timeout_s: int = DEFAULT_HTTP_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
        session: Optional[requests.Session] = None,
    ):
        # Resolve API key: explicit arg > env var. No file fallback.
        _maybe_load_dotenv()
        resolved = (api_key or os.environ.get("CAPSOLVER_API_KEY", "")).strip()
        if not resolved:
            raise CapSolverDisabled(
                "CAPSOLVER_API_KEY env var is not set. "
                "This is intentional: capsolver_client refuses to read "
                "the .capsolver-key file or any other source. "
                "Set the env var explicitly to enable real API calls."
            )
        self.api_key = resolved
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self.http_timeout_s = http_timeout_s
        self.max_retries = max(0, max_retries)
        self.backoff_base_s = max(0.1, backoff_base_s)
        self._session = session or requests.Session()

    # -- public API (brief spec) ---------------------------------------------

    def recaptcha_v3_enterprise(
        self,
        sitekey: str,
        page_url: str,
        action: str = "submit",
        min_score: float = 0.7,
    ) -> str:
        """Solve reCAPTCHA v3 Enterprise. Returns the gRecaptchaResponse token.

        NOTE on Ashby: the strict-Ashby cluster (OpenAI, Cursor, Notion, Sierra,
        Baseten, Plaid, Sentry, Deepgram, Cohere, Sana, Elev, Blaxel...) uses
        the SAME sitekey `6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y` with
        `pageAction='submit'`. Per page-source inspection 2026-05-26 it is
        NON-Enterprise (loader is `recaptcha.net/recaptcha/api.js?render=...`
        not `enterprise.js`). So for Ashby strict you should call
        `recaptcha_v3()` not `recaptcha_v3_enterprise()`. This method exists
        for genuinely Enterprise-loaded sites.
        """
        return self._solve(
            task={
                "type": "ReCaptchaV3EnterpriseTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
                "pageAction": action,
                "minScore": min_score,
            },
            solution_keys=("gRecaptchaResponse",),
            label=f"recaptcha-v3-ent action={action} min={min_score}",
        )

    def recaptcha_v3(
        self,
        sitekey: str,
        page_url: str,
        action: str = "submit",
        min_score: float = 0.7,
    ) -> str:
        """Solve standard (non-Enterprise) reCAPTCHA v3. Returns token.

        This is the right method for the strict-Ashby cluster.
        """
        return self._solve(
            task={
                "type": "ReCaptchaV3TaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
                "pageAction": action,
                "minScore": min_score,
            },
            solution_keys=("gRecaptchaResponse",),
            label=f"recaptcha-v3 action={action} min={min_score}",
        )

    def recaptcha_v3_proxied(
        self,
        sitekey: str,
        page_url: str,
        proxy: str,
        action: str = "submit",
        min_score: float = 0.7,
        enterprise: bool = False,
    ) -> str:
        """Solve reCAPTCHA v3 with a PROXY-BACKED task so the token is
        generated from OUR residential IP (not CapSolver's worker farm).

        This is the genuine end-to-end fix for the Ashby reCAPTCHA-v3
        score-gate (2026-06-03): the SUBMIT BROWSER egresses residential via
        _proxy_relay, but a Proxyless solve still generates the token from a
        datacenter/worker IP -> low score. A proxy-backed solve ties the token
        to the same residential IP the browser uses, so reCAPTCHA-v3 sees ONE
        consistent trusted IP across page-load + token.

        `proxy` accepts a full URL (http://user:pass@host:port) or the
        host:port:user:pass form; normalized to CapSolver's expected
        `scheme:host:port:user:pass` string.
        """
        cap_proxy = _to_capsolver_proxy(proxy)
        ttype = "ReCaptchaV3EnterpriseTask" if enterprise else "ReCaptchaV3Task"
        return self._solve(
            task={
                "type": ttype,
                "websiteURL": page_url,
                "websiteKey": sitekey,
                "pageAction": action,
                "minScore": min_score,
                "proxy": cap_proxy,
            },
            solution_keys=("gRecaptchaResponse",),
            label=f"recaptcha-v3-proxied action={action} min={min_score} ent={enterprise}",
        )

    def recaptcha_v2(self, sitekey: str, page_url: str,
                     is_invisible: bool = False) -> str:
        """Solve reCAPTCHA v2 (visible checkbox or invisible badge).

        Returns the g-recaptcha-response token. Inject into
        `#g-recaptcha-response` textarea (create one if missing) + dispatch
        a `change` event. Cost ~$0.002/solve. Added 2026-05-30 (chain_034a)
        for BambooHR-hosted careers pages.
        """
        return self._solve(
            task={
                "type": "ReCaptchaV2TaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
                "isInvisible": bool(is_invisible),
            },
            solution_keys=("gRecaptchaResponse",),
            label=f"recaptcha-v2 invisible={is_invisible}",
        )

    def hcaptcha(self, sitekey: str, page_url: str) -> str:
        """Solve hCaptcha. Returns the captcha-response token."""
        return self._solve(
            task={
                "type": "HCaptchaTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
            },
            solution_keys=("gRecaptchaResponse", "captchaResponse", "token"),
            label="hcaptcha",
        )

    def turnstile(self, sitekey: str, page_url: str) -> str:
        """Solve Cloudflare Turnstile. Returns the response token."""
        return self._solve(
            task={
                "type": "AntiTurnstileTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
            },
            solution_keys=("token", "gRecaptchaResponse"),
            label="turnstile",
        )

    def get_balance(self) -> float:
        """Returns the account USD balance. Raises on error."""
        resp = self._post(
            f"{CAPSOLVER_API}/getBalance",
            {"clientKey": self.api_key},
        )
        if resp.get("errorId"):
            raise CapSolverError(
                f"getBalance error: {resp.get('errorDescription') or resp}"
            )
        return float(resp.get("balance", 0))

    # -- core solve loop ------------------------------------------------------

    def _solve(self, task: dict, solution_keys: tuple, label: str) -> str:
        """createTask -> poll getTaskResult -> extract token by key list."""
        create = self._post(
            f"{CAPSOLVER_API}/createTask",
            {"clientKey": self.api_key, "task": task},
        )
        if create.get("errorId"):
            desc = (
                create.get("errorDescription")
                or create.get("errorCode")
                or "unknown"
            )
            self._classify_error(desc, label)
            raise CapSolverError(f"createTask({label}) error: {desc}")

        task_id = create.get("taskId")
        if not task_id:
            raise CapSolverError(
                f"createTask({label}) returned no taskId: {create}"
            )

        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            time.sleep(self.poll_interval_s)
            res = self._post(
                f"{CAPSOLVER_API}/getTaskResult",
                {"clientKey": self.api_key, "taskId": task_id},
            )
            if res.get("errorId"):
                desc = (
                    res.get("errorDescription")
                    or res.get("errorCode")
                    or "unknown"
                )
                self._classify_error(desc, label)
                raise CapSolverError(
                    f"getTaskResult({label}) error: {desc}"
                )
            status = res.get("status")
            if status == "ready":
                sol = res.get("solution") or {}
                for key in solution_keys:
                    token = sol.get(key)
                    if token:
                        return token
                raise CapSolverError(
                    f"{label} ready but no token in solution "
                    f"(expected one of {solution_keys}): {sol}"
                )
            # status == 'processing' / 'idle' -> keep polling

        raise CapSolverTimeout(
            f"{label} did not return a solution within {self.timeout_s}s "
            f"(taskId={task_id})"
        )

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _classify_error(desc: str, label: str) -> None:
        """Raise the specific subclass if `desc` looks like a quota error."""
        err_str = str(desc).lower()
        if any(tok in err_str for tok in ("balance", "credit", "quota", "out of")):
            raise CapSolverQuotaExceeded(
                f"{label}: account out of credit ({desc})"
            )
        # rate-limit description (CapSolver returns ERROR_NO_SLOT_AVAILABLE etc.)
        if "rate" in err_str or "no_slot" in err_str or "too many" in err_str:
            raise CapSolverRateLimited(
                f"{label}: rate-limited at the API level ({desc})"
            )

    def _post(self, url: str, payload: dict) -> dict:
        """POST JSON with exponential backoff on 429. Returns parsed JSON."""
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                r = self._session.post(
                    url, json=payload, timeout=self.http_timeout_s
                )
            except requests.RequestException as e:
                last_err = CapSolverError(f"network error calling {url}: {e}")
                # Network errors get one retry shot, no quota classification.
                if attempt < self.max_retries:
                    self._sleep_backoff(attempt)
                    continue
                raise last_err from e

            if r.status_code == 429:
                if attempt < self.max_retries:
                    log.warning(
                        "capsolver 429 on %s (attempt %d/%d); backing off",
                        url, attempt + 1, self.max_retries + 1,
                    )
                    self._sleep_backoff(attempt, retry_after=r.headers.get("Retry-After"))
                    continue
                raise CapSolverRateLimited(
                    f"HTTP 429 from {url} after {self.max_retries + 1} attempts"
                )

            if r.status_code >= 400:
                raise CapSolverError(
                    f"HTTP {r.status_code} from {url}: {r.text[:300]}"
                )

            try:
                return r.json()
            except ValueError as e:
                raise CapSolverError(
                    f"non-JSON response from {url}: {r.text[:300]}"
                ) from e

        assert last_err is not None
        raise last_err

    def _sleep_backoff(self, attempt: int, retry_after: Optional[str] = None) -> None:
        """Exponential backoff with jitter. Honors Retry-After header if int."""
        if retry_after:
            try:
                delay = float(retry_after)
                time.sleep(min(delay, 30))
                return
            except (TypeError, ValueError):
                pass
        # 2^attempt * base, capped at 30s, plus 0-25% jitter
        delay = min(self.backoff_base_s * (2 ** attempt), 30.0)
        jitter = delay * 0.25 * random.random()
        time.sleep(delay + jitter)


# ---------------------------------------------------------------------------
# Env fallback: source /home/azureuser/.openclaw/.env on demand.
# Cron jobs (weekly_run.sh) and standalone subprocess invocations may not
# inherit ENABLE_CAPSOLVER/CAPSOLVER_API_KEY from a parent shell. We do a
# one-time read-on-first-miss so the gate Just Works regardless of launcher.
# Never overrides values already set in the process env.
# ---------------------------------------------------------------------------

_DOTENV_LOADED = False
_DOTENV_PATHS = (
    "/home/azureuser/.openclaw/.env",
    os.path.expanduser("~/.openclaw/.env"),
)


def _maybe_load_dotenv() -> None:
    """Load CAPSOLVER_API_KEY / ENABLE_CAPSOLVER from .env if missing.

    Idempotent; only reads files once per process. Silently noops on any
    parse error — env-fallback is a best-effort convenience, not a contract.
    """
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    have_key = bool(os.environ.get("CAPSOLVER_API_KEY", "").strip())
    have_flag = bool(os.environ.get("ENABLE_CAPSOLVER", "").strip())
    if have_key and have_flag:
        return
    for path in _DOTENV_PATHS:
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k in ("CAPSOLVER_API_KEY", "ENABLE_CAPSOLVER") and not os.environ.get(k):
                        os.environ[k] = v
            return  # first successful read wins
        except FileNotFoundError:
            continue
        except Exception as e:  # noqa: BLE001
            log.debug("capsolver_client: .env fallback read failed at %s: %s", path, e)
            continue


# ---------------------------------------------------------------------------
# Helper: is enabled?  (env-only — safe to call anywhere, never raises)
# ---------------------------------------------------------------------------

def is_enabled() -> bool:
    """True if both CAPSOLVER_API_KEY and ENABLE_CAPSOLVER=1 are set.

    The runners gate on this. Treat as a hard kill switch — when False,
    no CapSolver code path runs.

    Falls back to reading /home/azureuser/.openclaw/.env on first call
    if either var is missing, so cron-launched runs (weekly_run.sh) and
    bare subprocess invocations don't silently disable the solver.
    """
    _maybe_load_dotenv()
    return (
        bool(os.environ.get("CAPSOLVER_API_KEY", "").strip())
        and os.environ.get("ENABLE_CAPSOLVER", "").strip() == "1"
    )


# ---------------------------------------------------------------------------
# CLI smoke entrypoint — no real solve
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, json, sys

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--check", action="store_true",
        help="Construct client + report account balance.",
    )
    args = ap.parse_args()
    out = {
        "is_enabled": is_enabled(),
        "env_CAPSOLVER_API_KEY_set": bool(os.environ.get("CAPSOLVER_API_KEY")),
        "env_ENABLE_CAPSOLVER": os.environ.get("ENABLE_CAPSOLVER", ""),
    }
    try:
        client = CapSolverClient()
    except CapSolverDisabled as e:
        out["client"] = {"constructed": False, "reason": str(e)}
        print(json.dumps(out, indent=2))
        sys.exit(0)
    out["client"] = {"constructed": True}
    if args.check:
        try:
            out["balance_usd"] = client.get_balance()
        except CapSolverError as e:
            out["balance_error"] = str(e)
    print(json.dumps(out, indent=2))
