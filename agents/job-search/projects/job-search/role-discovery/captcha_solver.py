#!/usr/bin/env python3
"""
captcha_solver.py — Vendor-agnostic CAPTCHA solver client.

Supports two vendors today:
  - **NopeCHA** (default) — flat-rate AI service. Free tier = 100 credits/day,
    but hCaptcha token costs 10 credits → ~10 hCaptcha solves/day on free.
    Free tier also REJECTS non-residential / datacenter IPs (per nopecha.com
    docs). For Azure VM use, expect free tier to fail and require a paid plan.
  - **CapSolver** (fallback) — pay-as-you-go (~$0.80 / 1k hCaptcha). Works from
    datacenter IPs. Use when NopeCHA fails (no balance, IP-blocked, etc.).

Vendor selection (first match wins):
    1. Explicit `vendor=` argument to the constructor
    2. `CAPTCHA_VENDOR` environment variable ("nopecha" | "capsolver")
    3. Default: "nopecha"

Key resolution per-vendor (first match wins):
    NopeCHA:
        1. Explicit `api_key=` argument
        2. `NOPECHA_API_KEY` env var
        3. `<project root>/.nopecha-key` file
    CapSolver:
        1. Explicit `api_key=` argument
        2. `CAPSOLVER_API_KEY` env var
        3. `<project root>/.capsolver-key` file

Network errors / vendor-side failures are wrapped in `SolverError`. The
`solve_*` methods stay vendor-agnostic; callers should NOT need to special-case
the vendor.

NO calls are made at import time. Constructing `CaptchaSolver()` only loads
the API key; the first real network call happens inside `solve_*`.

See `CAPTCHA-SOLVER-DECISION.md` for vendor selection rationale.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOPECHA_KEY_FILE = PROJECT_ROOT / ".nopecha-key"
CAPSOLVER_KEY_FILE = PROJECT_ROOT / ".capsolver-key"

NOPECHA_API = "https://api.nopecha.com"
CAPSOLVER_API = "https://api.capsolver.com"

DEFAULT_TIMEOUT_S = 90
DEFAULT_RETRIES = 2
POLL_INTERVAL_S = 2.0
HTTP_TIMEOUT_S = 30


class SolverError(Exception):
    """Generic solver failure (network, vendor error, timeout, no balance)."""


class SolverNotConfigured(SolverError):
    """No API key found anywhere. Caller should fail-the-role gracefully."""


class SolverTimeout(SolverError):
    """Vendor accepted the task but did not return a token within the budget."""


class SolverQuotaExceeded(SolverError):
    """Vendor returned out-of-credits / rate-limit / IP-blocked. Caller may
    fall back to a different vendor or fail-the-role."""


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class CaptchaSolver:
    """Vendor-agnostic captcha solver. Default vendor = nopecha."""

    SUPPORTED_VENDORS = ("nopecha", "capsolver", "twocaptcha")

    def __init__(
        self,
        vendor: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        retries: int = DEFAULT_RETRIES,
    ):
        # Resolve vendor: explicit > env > default
        resolved = (
            vendor
            or os.environ.get("CAPTCHA_VENDOR", "").strip().lower()
            or "nopecha"
        )
        if resolved not in self.SUPPORTED_VENDORS:
            raise SolverError(
                f"unsupported vendor {resolved!r}; supported: {self.SUPPORTED_VENDORS}"
            )
        self.vendor = resolved
        self.timeout_s = timeout_s
        self.retries = max(0, retries)
        self.api_key = (api_key or self._load_key(self.vendor)).strip()
        if not self.api_key:
            keyfile = NOPECHA_KEY_FILE if self.vendor == "nopecha" else CAPSOLVER_KEY_FILE
            envvar = {"nopecha": "NOPECHA_API_KEY", "capsolver": "CAPSOLVER_API_KEY",
                      "twocaptcha": "TWOCAPTCHA_API_KEY"}[self.vendor]
            raise SolverNotConfigured(
                f"no {self.vendor} API key found "
                f"(set {envvar} env var or write {keyfile}); "
                "see CAPTCHA-SOLVER-DECISION.md for vendor signup instructions"
            )

    # -- key loading ---------------------------------------------------------
    @staticmethod
    def _load_key(vendor: str) -> str:
        if vendor == "nopecha":
            env = os.environ.get("NOPECHA_API_KEY", "").strip()
            keyfile = NOPECHA_KEY_FILE
        else:  # capsolver / twocaptcha
            envvar_name = "TWOCAPTCHA_API_KEY" if vendor == "twocaptcha" else "CAPSOLVER_API_KEY"
            env = os.environ.get(envvar_name, "").strip()
            keyfile = CAPSOLVER_KEY_FILE
            if vendor == "twocaptcha" and not env:
                # ensure .env is loaded for the twocaptcha key
                try:
                    import twocaptcha_client as _tcmod
                    _tcmod._maybe_load_dotenv()
                    env = os.environ.get("TWOCAPTCHA_API_KEY", "").strip()
                except Exception:
                    pass
        if env:
            return env
        if keyfile.exists():
            try:
                return keyfile.read_text().strip().splitlines()[0].strip()
            except (OSError, IndexError):
                return ""
        return ""

    # -- public API ----------------------------------------------------------
    def _twocaptcha_client(self):
        """Lazily build a TwoCaptchaClient (reads TWOCAPTCHA_API_KEY +
        PROXY_2CAPTCHA from env/.env). Cached on the instance."""
        tc = getattr(self, "_tc", None)
        if tc is None:
            import twocaptcha_client as _tcmod
            try:
                tc = _tcmod.TwoCaptchaClient(
                    api_key=self.api_key or None,
                )
            except _tcmod.TwoCaptchaError as e:
                raise SolverError(f"twocaptcha init: {e}")
            self._tc = tc
        return tc

    def solve_hcaptcha(self, sitekey: str, page_url: str,
                       is_invisible: bool = False, user_agent: str = None,
                       rqdata: str = None) -> str:
        """Solve an hCaptcha challenge. Returns the response token (string).
        is_invisible/user_agent matter for PASSIVE hCaptcha (Lever) — see
        twocaptcha_client.hcaptcha docstring. `rqdata` (hCaptcha ENTERPRISE,
        2026-06-05) binds the token to the page's per-session challenge via
        enterprisePayload — REQUIRED for the Lever Enterprise cohort or the
        apply-POST 400s. Only 2Captcha implements the enterprise rqdata path
        (CapSolver discontinued hCaptcha; nopecha has no rqdata param), so a
        non-twocaptcha vendor with rqdata set raises rather than silently
        solving an unbound token."""
        if self.vendor == "twocaptcha":
            import twocaptcha_client as _tcmod
            try:
                return self._twocaptcha_client().hcaptcha(
                    sitekey, page_url, is_invisible=is_invisible,
                    user_agent=user_agent, rqdata=rqdata)
            except _tcmod.TwoCaptchaQuotaExceeded as e:
                raise SolverQuotaExceeded(str(e))
            except _tcmod.TwoCaptchaError as e:
                raise SolverError(f"twocaptcha hcaptcha: {e}")
        if rqdata:
            # Enterprise rqdata is only bindable via 2Captcha; refuse to solve an
            # unbound token on another vendor (would 400 at submit anyway).
            raise SolverError(
                f"hcaptcha enterprise rqdata requires the twocaptcha vendor, "
                f"not {self.vendor!r}")
        if self.vendor == "nopecha":
            return self._solve_with_retries(
                {"type": "hcaptcha", "sitekey": sitekey, "url": page_url},
                label="hcaptcha",
                solver=self._solve_nopecha,
            )
        return self._solve_with_retries(
            {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
            },
            label="hcaptcha",
            solver=self._solve_capsolver,
        )

    def solve_recaptcha_v2(self, sitekey: str, page_url: str) -> str:
        if self.vendor == "twocaptcha":
            import twocaptcha_client as _tcmod
            try:
                return self._twocaptcha_client().recaptcha_v2(sitekey, page_url)
            except _tcmod.TwoCaptchaQuotaExceeded as e:
                raise SolverQuotaExceeded(str(e))
            except _tcmod.TwoCaptchaError as e:
                raise SolverError(f"twocaptcha recaptcha-v2: {e}")
        if self.vendor == "nopecha":
            return self._solve_with_retries(
                {"type": "recaptcha2", "sitekey": sitekey, "url": page_url},
                label="recaptcha-v2",
                solver=self._solve_nopecha,
            )
        return self._solve_with_retries(
            {
                "type": "ReCaptchaV2TaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
            },
            label="recaptcha-v2",
            solver=self._solve_capsolver,
        )

    def solve_recaptcha_v3(
        self,
        sitekey: str,
        page_url: str,
        page_action: str = "submit",
        min_score: float = 0.7,
        enterprise: bool = False,
    ) -> str:
        """Solve reCAPTCHA v3 (score-based, invisible). Returns a token.

        Ashby strict tenants (OpenAI/Cursor/Notion/Sierra/Baseten/Plaid)
        all use the SAME sitekey `6LeFb_YUAAAAALUD5h-BiQEp8JaFChe0e0A6r49Y`
        with `pageAction='submit'` and an undisclosed min_score (treat 0.7
        as conservative default). Loader is
        `https://recaptcha.net/recaptcha/api.js?render=<sitekey>` (NOT
        Enterprise — verified 2026-05-26 from page source).

        Args:
            sitekey: data-sitekey / render param
            page_url: full page URL where the captcha runs
            page_action: pageAction param passed to grecaptcha.execute() —
                must match exactly what the site uses. Ashby = 'submit'.
            min_score: 0.0-1.0; CapSolver tries to deliver >= this.
            enterprise: True for reCAPTCHA Enterprise (different endpoint).
                Ashby strict tenants are NON-enterprise.

        NopeCHA support is best-effort (their docs are thin on v3) — prefer
        CapSolver for v3.

        2Captcha NOTE (2026-06-03): only RecaptchaV3TaskProxyless exists — the
        solve uses 2Captcha worker IPs (our residential proxy does NOT apply to
        v3). Whether the resulting score passes the Ashby gate is validated
        only on a live submit.
        """
        if self.vendor == "twocaptcha":
            import twocaptcha_client as _tcmod
            try:
                return self._twocaptcha_client().recaptcha_v3(
                    sitekey, page_url, action=page_action, min_score=min_score)
            except _tcmod.TwoCaptchaQuotaExceeded as e:
                raise SolverQuotaExceeded(str(e))
            except _tcmod.TwoCaptchaError as e:
                raise SolverError(f"twocaptcha recaptcha-v3: {e}")
        if self.vendor == "nopecha":
            # NopeCHA v3 task — uses 'recaptcha3' type per their token API.
            return self._solve_with_retries(
                {
                    "type": "recaptcha3",
                    "sitekey": sitekey,
                    "url": page_url,
                    "data": {"action": page_action},
                },
                label="recaptcha-v3",
                solver=self._solve_nopecha,
            )
        task_type = (
            "ReCaptchaV3EnterpriseTaskProxyless"
            if enterprise
            else "ReCaptchaV3TaskProxyless"
        )
        return self._solve_with_retries(
            {
                "type": task_type,
                "websiteURL": page_url,
                "websiteKey": sitekey,
                "pageAction": page_action,
                "minScore": min_score,
            },
            label="recaptcha-v3",
            solver=self._solve_capsolver,
        )

    def solve_turnstile(self, sitekey: str, page_url: str, action: str = None) -> str:
        if self.vendor == "twocaptcha":
            return self._twocaptcha_client().turnstile(
                sitekey, page_url, action=action
            )
        if self.vendor == "nopecha":
            return self._solve_with_retries(
                {"type": "turnstile", "sitekey": sitekey, "url": page_url},
                label="turnstile",
                solver=self._solve_nopecha,
            )
        return self._solve_with_retries(
            {
                "type": "AntiTurnstileTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
            },
            label="turnstile",
            solver=self._solve_capsolver,
        )

    def get_balance(self) -> float:
        """Returns USD balance (CapSolver) or remaining credits (NopeCHA).
        Raises SolverError on failure."""
        if self.vendor == "twocaptcha":
            return self._twocaptcha_client().get_balance()
        if self.vendor == "capsolver":
            r = self._post(
                f"{CAPSOLVER_API}/getBalance", {"clientKey": self.api_key}
            )
            if r.get("errorId"):
                raise SolverError(
                    f"capsolver balance error: {r.get('errorDescription') or r}"
                )
            return float(r.get("balance", 0))
        # NopeCHA: GET /status/?key=...
        try:
            r = requests.get(
                f"{NOPECHA_API}/status/",
                params={"key": self.api_key},
                timeout=HTTP_TIMEOUT_S,
            )
        except requests.RequestException as e:
            raise SolverError(f"nopecha status network error: {e}") from e
        if r.status_code >= 400:
            raise SolverError(
                f"nopecha status HTTP {r.status_code}: {r.text[:300]}"
            )
        try:
            data = r.json()
        except ValueError as e:
            raise SolverError(
                f"nopecha non-JSON status: {r.text[:300]}"
            ) from e
        # Response shape: {"plan":"free","credit":<int>,"quota":<int>,...}
        return float(data.get("credit", 0))

    # -- internals -----------------------------------------------------------
    def _solve_with_retries(self, task: dict, label: str, solver) -> str:
        last_err: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                return solver(task, label=label)
            except SolverNotConfigured:
                raise
            except SolverQuotaExceeded:
                # Don't retry quota errors — they won't recover in 2s
                raise
            except SolverError as e:
                last_err = e
                log.warning(
                    "captcha-solver(%s) %s attempt %d/%d failed: %s",
                    self.vendor, label, attempt + 1, self.retries + 1, e,
                )
        assert last_err is not None
        raise last_err

    # -- NopeCHA ---------------------------------------------------------
    def _solve_nopecha(self, task: dict, label: str) -> str:
        """NopeCHA Token API: POST /token/ → {data: <id>}; GET /token/?id=...
        until {data: <token>}. Errors come back as {error: ..., message: ...}."""
        # 1. POST /token/
        payload = {"key": self.api_key, **task}
        try:
            r = requests.post(
                f"{NOPECHA_API}/token/", json=payload, timeout=HTTP_TIMEOUT_S
            )
        except requests.RequestException as e:
            raise SolverError(f"nopecha network error (POST): {e}") from e
        if r.status_code in (402, 403, 429):
            raise SolverQuotaExceeded(
                f"nopecha {label} HTTP {r.status_code}: {r.text[:300]} "
                f"(out of credits, rate-limited, or non-residential IP)"
            )
        if r.status_code >= 400:
            raise SolverError(
                f"nopecha {label} POST HTTP {r.status_code}: {r.text[:300]}"
            )
        try:
            create = r.json()
        except ValueError as e:
            raise SolverError(
                f"nopecha {label} non-JSON POST response: {r.text[:300]}"
            ) from e
        if create.get("error"):
            err_msg = create.get("message") or create.get("error")
            err_str = str(err_msg).lower()
            if any(
                tok in err_str for tok in ("credit", "quota", "rate", "ip", "non-residential")
            ):
                raise SolverQuotaExceeded(
                    f"nopecha {label} create error: {err_msg}"
                )
            raise SolverError(f"nopecha {label} create error: {err_msg}")
        task_id = create.get("data")
        if not task_id:
            raise SolverError(
                f"nopecha {label} create returned no id: {create}"
            )

        # 2. GET /token/?key=...&id=...
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_S)
            try:
                rr = requests.get(
                    f"{NOPECHA_API}/token/",
                    params={"key": self.api_key, "id": task_id},
                    timeout=HTTP_TIMEOUT_S,
                )
            except requests.RequestException as e:
                raise SolverError(
                    f"nopecha {label} network error (GET): {e}"
                ) from e
            if rr.status_code >= 400:
                # NopeCHA returns 409 while result is not ready
                if rr.status_code == 409:
                    continue
                raise SolverError(
                    f"nopecha {label} GET HTTP {rr.status_code}: {rr.text[:300]}"
                )
            try:
                res = rr.json()
            except ValueError as e:
                raise SolverError(
                    f"nopecha {label} non-JSON GET response: {rr.text[:300]}"
                ) from e
            if res.get("error"):
                # "incomplete_job" => still solving, keep polling
                err = str(res.get("error", "")).lower()
                if "incomplete" in err or "pending" in err:
                    continue
                raise SolverError(
                    f"nopecha {label} GET error: {res.get('message') or res.get('error')}"
                )
            token = res.get("data")
            if token:
                return token
        raise SolverTimeout(
            f"nopecha {label} did not return a solution within {self.timeout_s}s"
        )

    # -- CapSolver -------------------------------------------------------
    def _solve_capsolver(self, task: dict, label: str) -> str:
        # 1. createTask
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
            err_str = str(desc).lower()
            if "balance" in err_str or "credit" in err_str:
                raise SolverQuotaExceeded(
                    f"capsolver createTask({label}) out of credits: {desc}"
                )
            raise SolverError(f"capsolver createTask({label}) error: {desc}")
        task_id = create.get("taskId")
        if not task_id:
            raise SolverError(
                f"capsolver createTask({label}) returned no taskId: {create}"
            )

        # 2. poll getTaskResult
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL_S)
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
                raise SolverError(
                    f"capsolver getTaskResult({label}) error: {desc}"
                )
            status = res.get("status")
            if status == "ready":
                sol = res.get("solution") or {}
                token = (
                    sol.get("gRecaptchaResponse")
                    or sol.get("token")
                    or sol.get("captchaResponse")
                    or sol.get("text")
                )
                if not token:
                    raise SolverError(
                        f"capsolver {label} ready but no token in solution: {sol}"
                    )
                return token
            # status == 'processing' → keep polling
        raise SolverTimeout(
            f"capsolver {label} did not return a solution within {self.timeout_s}s"
        )

    @staticmethod
    def _post(url: str, payload: dict) -> dict:
        try:
            r = requests.post(url, json=payload, timeout=HTTP_TIMEOUT_S)
        except requests.RequestException as e:
            raise SolverError(f"network error calling {url}: {e}") from e
        if r.status_code >= 400:
            raise SolverError(f"HTTP {r.status_code} from {url}: {r.text[:300]}")
        try:
            return r.json()
        except ValueError as e:
            raise SolverError(
                f"non-JSON response from {url}: {r.text[:300]}"
            ) from e


# ---------------------------------------------------------------------------
# CLI smoke entrypoint (no real solve)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse, json, sys

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--vendor", choices=CaptchaSolver.SUPPORTED_VENDORS, default=None
    )
    ap.add_argument(
        "--check", action="store_true",
        help="Try to construct + report balance/credits.",
    )
    args = ap.parse_args()
    try:
        s = CaptchaSolver(vendor=args.vendor)
    except SolverNotConfigured as e:
        print(json.dumps({"configured": False, "reason": str(e)}, indent=2))
        sys.exit(0)
    out = {"configured": True, "vendor": s.vendor}
    if args.check:
        try:
            balance = s.get_balance()
            key = "credits" if s.vendor == "nopecha" else "balance_usd"
            out[key] = balance
        except SolverError as e:
            out["balance_error"] = str(e)
    print(json.dumps(out, indent=2))
