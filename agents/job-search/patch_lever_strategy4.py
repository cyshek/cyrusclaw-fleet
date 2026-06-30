#!/usr/bin/env python3
import sys

path = "projects/job-search/role-discovery/_lever_runner.py"
with open(path, 'r') as f:\n    content = f.read()\n\nold = (\n    "                # STRATEGY 4 (last resort): external 2Captcha/capsolver solver\n"
    "                # Note: Lever rejects these (IP mismatch) but keep for other ATS\n"
    "                if not token:\n"
    "                    try:\n"
    "                        errs = {}\n"
    "                        try:\n"
    "                            _ua = page.evaluate(\"() => navigator.userAgent\")\n"
    "                        except Exception:\n"
    "                            _ua = None\n"
    "                        _vendors = ('twocaptcha',) if _rqdata else ('twocaptcha', 'capsolver', 'nopecha')\n"
    "                        for vend in _vendors:\n"
    "                            try:\n"
    "                                token = CaptchaSolver(vendor=vend).solve_hcaptcha(\n"
    "                                    sitekey, page_url, is_invisible=_invis,\n"
    "                                    user_agent=_ua, rqdata=_rqdata)\n"
    "                                log(f\"hcaptcha solved via {vend} token_len={len(token)} [FALLBACK]\")\n"
    "                                break\n"
    "                            except Exception as ev:\n"
    "                                errs[vend] = str(ev)\n"
    "                                log(f\"hcaptcha {vend} failed: {ev}\")\n"
    "                        if not token:\n"
    "                            result['error'] = 'hcaptcha-solve-fail: ' + '; '.join(f'{k}={v}' for k,v in errs.items())\n"
    "                            result['steps'].append({'i':i,'tool':tool,'err':result['error']})\n"
    "                            log(f\"hcaptcha solve fail (all): {result['error']}\"); continue\n"
    "                    except Exception as e:\n"
    "                        result['error'] = f'hcaptcha-solve-exc: {e}'\n"
    "                        result['steps'].append({'i':i,'tool':tool,'err':result['error']})\n"
    "                        log(result['error']); continue\n"
)

new = (
    "                # STRATEGY 4 (last resort): external solver.\n"
    "                # NopeCHA + residential proxy: when CAPTCHA_VENDOR=nopecha and\n"
    "                # Webshare proxy creds are available, pass proxy= so NopeCHA\n"
    "                # solves from the same residential IP as our submit POST --\n"
    "                # Lever's IP-matching check requires token IP == submit IP.\n"
    "                if not token:\n"
    "                    try:\n"
    "                        errs = {}\n"
    "                        try:\n"
    "                            _ua = page.evaluate(\"() => navigator.userAgent\")\n"
    "                        except Exception:\n"
    "                            _ua = None\n"
    "                        _vendors = ('twocaptcha',) if _rqdata else ('twocaptcha', 'capsolver', 'nopecha')\n"
    "                        # Load Webshare proxy for NopeCHA IP-match (Lever requirement)\n"
    "                        _nopecha_proxy = _load_webshare_proxy()\n"
    "                        if _nopecha_proxy:\n"
    "                            log(f\"NopeCHA proxy loaded: {_nopecha_proxy['host']}:{_nopecha_proxy['port']}\")\n"
    "                        for vend in _vendors:\n"
    "                            try:\n"
    "                                _proxy_arg = _nopecha_proxy if (vend == 'nopecha' and _nopecha_proxy) else None\n"
    "                                token = CaptchaSolver(vendor=vend).solve_hcaptcha(\n"
    "                                    sitekey, page_url, is_invisible=_invis,\n"
    "                                    user_agent=_ua, rqdata=_rqdata,\n"
    "                                    proxy=_proxy_arg)\n"
    "                                log(f\"hcaptcha solved via {vend} (proxy={'yes' if _proxy_arg else 'no'}) token_len={len(token)} [FALLBACK]\")\n"
    "                                break\n"
    "                            except Exception as ev:\n"
    "                                errs[vend] = str(ev)\n"
    "                                log(f\"hcaptcha {vend} failed: {ev}\")\n"
    "                        if not token:\n"
    "                            result['error'] = 'hcaptcha-solve-fail: ' + '; '.join(f'{k}={v}' for k,v in errs.items())\n"
    "                            result['steps'].append({'i':i,'tool':tool,'err':result['error']})\n"
    "                            log(f\"hcaptcha solve fail (all): {result['error']}\"); continue\n"
    "                    except Exception as e:\n"
    "                        result['error'] = f'hcaptcha-solve-exc: {e}'\n"
    "                        result['steps'].append({'i':i,'tool':tool,'err':result['error']})\n"
    "                        log(result['error']); continue\n"
)

if old in content:
    content2 = content.replace(old, new, 1)
    with open(path, 'w') as f:\n        f.write(content2)\n    print("SUCCESS: replaced Strategy 4 block")
else:
    print("FAIL: old text not found")
    lines = content.splitlines()
    for i, line in enumerate(lines[370:405], start=371):
        print(f"{i}: {repr(line)}")
    sys.exit(1)
