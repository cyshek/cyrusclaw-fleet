"""2Captcha REST client (anti-captcha-compatible createTask/getTaskResult API).

WHY THIS EXISTS (2026-06-03):
CapSolver discontinued hCaptcha entirely — `HCaptchaTask` returns
`ERROR_INVALID_TASK_DATA / "We don't support this service"` even WITH a proxy
(live-probed 2026-06-03, see TOOLS.md). 2Captcha still solves hCaptcha AND
reCAPTCHA, and — critically — supports PROXY-BACKED tasks, which is required to
beat the strict-Ashby reCAPTCHA-v3 *score gate* (the score weights the
SERVER-SIDE request IP; a datacenter token always scores low). Feeding 2Captcha
a residential proxy makes its solve originate from a residential IP.

API shape is the anti-captcha standard (same family CapSolver mirrors):
  POST https://api.2captcha.com/createTask   -> {taskId}
  POST https://api.2captcha.com/getTaskResult-> poll until status=="ready"

PROXY: pass a residential proxy to the constructor (or PROXY_2CAPTCHA env) and
the reCAPTCHA/hCaptcha calls use the NON-proxyless task variants with
proxyType/proxyAddress/proxyPort/proxyLogin/proxyPassword fields. Omit the
proxy and they fall back to the *Proxyless variants (fine for hCaptcha, which
returns a binary token, NOT an IP-weighted score).

Key resolution: explicit arg > TWOCAPTCHA_API_KEY env. No file fallback
(same discipline as capsolver_client).
"""

from __future__ import annotations

import os
import re
import time
from typing import Optional, Tuple

import requests

TWOCAPTCHA_API = "https://api.2captcha.com"

DEFAULT_TIMEOUT_S = 180
DEFAULT_POLL_INTERVAL_S = 5.0
DEFAULT_HTTP_TIMEOUT_S = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE_S = 1.0


class TwoCaptchaError(Exception):
    pass


class TwoCaptchaDisabled(TwoCaptchaError):
    """No API key configured."""


class TwoCaptchaTimeout(TwoCaptchaError):
    """createTask succeeded but no solution within timeout."""


class TwoCaptchaQuotaExceeded(TwoCaptchaError):
    """Out of balance."""


# ---------------------------------------------------------------------------
# Proxy parsing
# ---------------------------------------------------------------------------

# Accepts: user:pass@host:port  |  host:port:user:pass  |  host:port
_PROXY_AT_RE = re.compile(
    r"^(?:(?P<scheme>https?|socks5)://)?"
    r"(?P<login>[^:@/]+):(?P<password>[^:@/]+)@(?P<host>[^:@/]+):(?P<port>\d+)/?$"
)
_PROXY_COLON_RE = re.compile(
    r"^(?P<host>[^:@/]+):(?P<port>\d+)(?::(?P<login>[^:@/]+):(?P<password>[^:@/]+))?/?$"
)


def parse_proxy(raw: Optional[str]) -> Optional[dict]:
    """Parse a proxy string into 2Captcha task proxy fields, or None."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    m = _PROXY_AT_RE.match(raw)
    if not m:
        m = _PROXY_COLON_RE.match(raw)
    if not m:
        raise TwoCaptchaError(f"unparseable proxy string: {raw!r}")
    gd = m.groupdict()
    fields = {
        "proxyType": (gd.get("scheme") or "http").lower(),
        "proxyAddress": gd["host"],
        "proxyPort": int(gd["port"]),
    }
    if gd.get("login"):
        fields["proxyLogin"] = gd["login"]
        fields["proxyPassword"] = gd["password"]
    return fields


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class TwoCaptchaClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        proxy: Optional[str] = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
        http_timeout_s: int = DEFAULT_HTTP_TIMEOUT_S,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
        session: Optional[requests.Session] = None,
    ):
        _maybe_load_dotenv()
        resolved = (api_key or os.environ.get("TWOCAPTCHA_API_KEY", "")).strip()
        if not resolved:
            raise TwoCaptchaDisabled(
                "TWOCAPTCHA_API_KEY env var is not set. Set it explicitly "
                "to enable real 2Captcha API calls."
            )
        self.api_key = resolved
        self.proxy_fields = parse_proxy(
            proxy if proxy is not None else os.environ.get("PROXY_2CAPTCHA", "")
        )
        self.timeout_s = timeout_s
        self.poll_interval_s = poll_interval_s
        self.http_timeout_s = http_timeout_s
        self.max_retries = max(0, max_retries)
        self.backoff_base_s = max(0.1, backoff_base_s)
        self._session = session or requests.Session()

    @property
    def has_proxy(self) -> bool:
        return self.proxy_fields is not None

    # -- public API ----------------------------------------------------------

    def recaptcha_v3(
        self,
        sitekey: str,
        page_url: str,
        action: str = "submit",
        min_score: float = 0.7,
    ) -> str:
        """Solve reCAPTCHA v3.

        NOTE (2026-06-03): 2Captcha has NO proxy-backed reCAPTCHA-v3 task —
        only `RecaptchaV3TaskProxyless` exists. The solve always originates
        from 2Captcha's own worker IPs (not our proxy, not our datacenter IP).
        Whether that passes the Ashby score gate depends on THEIR IP rep.
        """
        task = {
            "type": "RecaptchaV3TaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
            "pageAction": action,
            "minScore": min_score,
        }
        return self._solve(task, ("gRecaptchaResponse", "token"),
                           f"recaptcha-v3 action={action} min={min_score}")

    def recaptcha_v2(self, sitekey: str, page_url: str,
                     is_invisible: bool = False) -> str:
        if self.proxy_fields:
            task = {
                "type": "RecaptchaV2Task",
                "websiteURL": page_url,
                "websiteKey": sitekey,
                "isInvisible": bool(is_invisible),
                **self.proxy_fields,
            }
        else:
            task = {
                "type": "RecaptchaV2TaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
                "isInvisible": bool(is_invisible),
            }
        return self._solve(task, ("gRecaptchaResponse", "token"),
                           f"recaptcha-v2 invisible={is_invisible} proxy={self.has_proxy}")

    def turnstile(self, sitekey: str, page_url: str, action: str = None,
                  cdata: str = None) -> str:
        """Solve a Cloudflare Turnstile challenge (Workable et al). 2Captcha's
        TurnstileTask returns a token accepted server-side. Proxy supported
        (and recommended so the token's IP matches the submitting browser)."""
        task = {
            "type": "TurnstileTask" if self.proxy_fields else "TurnstileTaskProxyless",
            "websiteURL": page_url,
            "websiteKey": sitekey,
        }
        if action:
            task["action"] = action
        if cdata:
            task["data"] = cdata
        if self.proxy_fields:
            task.update(self.proxy_fields)
        return self._solve(task, ("token", "gRecaptchaResponse"),
                           f"turnstile proxy={self.has_proxy}")

    def hcaptcha(self, sitekey: str, page_url: str,
                 is_invisible: bool = False, user_agent: str = None,
                 rqdata: str = None) -> str:
        """Solve hCaptcha (Lever cohort). For PASSIVE/invisible hCaptcha
        (Lever's `enclaves:2, visible_challenge:False` mode) the token is bound
        to the widget mode + the solving user-agent: pass `is_invisible=True`
        and the BROWSER's real navigator.userAgent, or the server rejects the
        token with a 400 even though the token itself is valid (diagnosed
        2026-06-04 on FloQast a11c182c — IP-matched residential submit still
        400'd until isInvisible+userAgent were threaded through).

        hCaptcha ENTERPRISE (2026-06-05): pass `rqdata` (the per-session
        challenge data extracted from the page). 2Captcha then binds the token
        to that session via `enterprisePayload.rqdata` + `isEnterprise:true`.
        Without it, an enterprise widget's token is valid-but-unbound and the
        apply-POST 400s (reproduced on FloQast + PointClickCare, shared sitekey
        e33f87f8-..., the exact Lever-cohort wall). rqdata REQUIRES a matching
        residential proxy + userAgent or the bind still fails."""
        if self.proxy_fields:
            task = {
                "type": "HCaptchaTask",
                "websiteURL": page_url,
                "websiteKey": sitekey,
                **self.proxy_fields,
            }
        else:
            task = {
                "type": "HCaptchaTaskProxyless",
                "websiteURL": page_url,
                "websiteKey": sitekey,
            }
        if is_invisible:
            task["isInvisible"] = True
        if user_agent:
            task["userAgent"] = user_agent
        if rqdata:
            # Enterprise bind: 2Captcha expects the rqdata under enterprisePayload.
            task["isEnterprise"] = True
            task["enterprisePayload"] = {"rqdata": rqdata}
        return self._solve(task, ("gRecaptchaResponse", "token", "captchaResponse"),
                           f"hcaptcha proxy={self.has_proxy} invisible={is_invisible} "
                           f"enterprise={bool(rqdata)}")

    def get_balance(self) -> float:
        resp = self._post(f"{TWOCAPTCHA_API}/getBalance",
                          {"clientKey": self.api_key})
        return float(resp.get("balance", 0.0))

    # -- internals -----------------------------------------------------------

    def _solve(self, task: dict, solution_keys: Tuple[str, ...], label: str) -> str:
        create = self._post(f"{TWOCAPTCHA_API}/createTask",
                            {"clientKey": self.api_key, "task": task})
        if create.get("errorId"):
            desc = create.get("errorDescription", "")
            code = create.get("errorCode", "")
            self._classify_error(code, desc, label)
            raise TwoCaptchaError(f"createTask({label}) error: {code} {desc}")
        task_id = create.get("taskId")
        if not task_id:
            raise TwoCaptchaError(f"createTask({label}) returned no taskId: {create}")

        deadline = time.time() + self.timeout_s
        while time.time() < deadline:
            time.sleep(self.poll_interval_s)
            res = self._post(f"{TWOCAPTCHA_API}/getTaskResult",
                            {"clientKey": self.api_key, "taskId": task_id})
            if res.get("errorId"):
                desc = res.get("errorDescription", "")
                code = res.get("errorCode", "")
                self._classify_error(code, desc, label)
                raise TwoCaptchaError(f"getTaskResult({label}) error: {code} {desc}")
            if res.get("status") == "ready":
                sol = res.get("solution", {}) or {}
                for k in solution_keys:
                    if sol.get(k):
                        return sol[k]
                raise TwoCaptchaError(
                    f"getTaskResult({label}) ready but no token in keys "
                    f"{solution_keys}: {list(sol.keys())}")
        raise TwoCaptchaTimeout(f"{label}: no solution within {self.timeout_s}s")

    @staticmethod
    def _classify_error(code: str, desc: str, label: str) -> None:
        blob = f"{code} {desc}".lower()
        if any(t in blob for t in ("zero_balance", "no_money", "out of",
                                    "insufficient", "balance")):
            raise TwoCaptchaQuotaExceeded(f"{label}: {code} {desc}")

    def _post(self, url: str, payload: dict) -> dict:
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                r = self._session.post(url, json=payload,
                                       timeout=self.http_timeout_s)
                r.raise_for_status()
                return r.json()
            except Exception as e:  # noqa: BLE001
                last_exc = e
                if attempt < self.max_retries:
                    time.sleep(self.backoff_base_s * (2 ** attempt))
        raise TwoCaptchaError(f"POST {url} failed after retries: {last_exc}")


# ---------------------------------------------------------------------------
# dotenv + enablement helpers (mirror capsolver_client)
# ---------------------------------------------------------------------------

_DOTENV_LOADED = False


def _maybe_load_dotenv() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    for cand in (
        os.path.expanduser("~/.openclaw/.env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
    ):
        try:
            if not os.path.isfile(cand):
                continue
            with open(cand, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k in ("TWOCAPTCHA_API_KEY", "PROXY_2CAPTCHA") and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


def is_enabled() -> bool:
    _maybe_load_dotenv()
    return bool(os.environ.get("TWOCAPTCHA_API_KEY", "").strip())


if __name__ == "__main__":
    import sys
    if not is_enabled():
        print("TWOCAPTCHA_API_KEY not set — adapter present but idle.")
        sys.exit(0)
    c = TwoCaptchaClient()
    print(f"2Captcha enabled. proxy={'yes' if c.has_proxy else 'no'}")
    try:
        print(f"balance: ${c.get_balance():.4f}")
    except Exception as e:  # noqa: BLE001
        print(f"balance check failed: {e}")
        sys.exit(1)
