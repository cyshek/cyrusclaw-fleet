#!/usr/bin/env python3
"""Trigger a submit attempt on a Lever form to see if hCaptcha escalates to a
visible challenge. Fills minimal junk data, clicks submit, watches for a
checkbox-iframe / challenge-iframe to appear.

DOES NOT actually submit successfully (we use junk data — server may reject
on validation, but that's after captcha runs).
"""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path
from playwright.async_api import async_playwright

try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except Exception:
    HAS_STEALTH = False
    stealth_async = None  # type: ignore

URLS = [
    ("Outreach", "https://jobs.lever.co/outreach/810b13b3-8338-44fd-99dd-94d24cfe078c/apply"),
    ("Spotify",  "https://jobs.lever.co/spotify/a4a933ce-ab44-4a13-b8ca-8575c97ea40a/apply"),
    ("Palantir", "https://jobs.lever.co/palantir/96a0ce26-cf84-4fa8-934b-acc4363620b2/apply"),
]

PROBE_JS = r"""
() => {
  const out = { challenge_iframes: [], checkbox_iframes: [], enclave_iframes: [], any_visible_hc: false };
  for (const f of document.querySelectorAll("iframe")) {
    const src = f.getAttribute("src") || "";
    const r = f.getBoundingClientRect();
    const cs = getComputedStyle(f);
    const vis = r.width > 5 && r.height > 5 && cs.visibility !== "hidden" && cs.display !== "none";
    if (src.includes("hcaptcha-challenge") || src.includes("hcaptcha.com/captcha/v1") && src.includes("frame=challenge")) {
      out.challenge_iframes.push({ src, w: r.width, h: r.height, visible: vis });
      if (vis) out.any_visible_hc = true;
    }
    if (src.includes("hcaptcha.com/captcha/v1") && (src.includes("frame=checkbox") || src.includes("hcaptcha-checkbox"))) {
      out.checkbox_iframes.push({ src, w: r.width, h: r.height, visible: vis });
      if (vis) out.any_visible_hc = true;
    }
    if (src.includes("hcaptcha-enclave")) {
      out.enclave_iframes.push({ w: r.width, h: r.height, visible: vis });
    }
    if (src.includes("hcaptcha.com") && vis && r.height > 50) {
      out.any_visible_hc = true;
    }
  }
  return out;
}
"""


async def attempt_submit(p, name, url, use_stealth):
    browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = await browser.new_context(
        viewport={"width": 1366, "height": 900},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    page = await ctx.new_page()
    if use_stealth and HAS_STEALTH:
        await stealth_async(page)

    result = {"site": name, "stealth": use_stealth, "steps": []}
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)

        # Fill minimum required fields if we can find them.
        async def maybe_fill(selector, value):
            try:
                el = page.locator(selector).first
                if await el.count() > 0:
                    await el.fill(value, timeout=3000)
                    result["steps"].append(f"filled {selector}")
            except Exception as e:
                result["steps"].append(f"skip {selector}: {type(e).__name__}")

        await maybe_fill("input[name='name']", "Test User")
        await maybe_fill("input[name='email']", "test@example.com")
        await maybe_fill("input[name='phone']", "555-555-5555")
        await maybe_fill("input[name='org']", "Test Co")
        await maybe_fill("input[name='urls[LinkedIn]']", "https://linkedin.com/in/test")

        # Find the REAL visible submit button (skip the hidden hcaptchaSubmitBtn helper).
        clicked = False
        for sel in [
            "button:has-text('Submit application'):visible",
            "button:has-text('Submit Application'):visible",
            "button:has-text('Submit'):visible",
            "button[type='submit']:not(.hidden):visible",
            "input[type='submit']:visible",
        ]:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    await loc.scroll_into_view_if_needed(timeout=2000)
                    await loc.click(timeout=5000)
                    result["steps"].append(f"clicked submit via {sel}")
                    clicked = True
                    break
            except Exception as e:
                result["steps"].append(f"sel {sel} failed: {type(e).__name__}: {str(e)[:80]}")
        if not clicked:
            result["steps"].append("NO visible submit button clicked")

        # Wait and observe what appears
        for wait_s in (1, 3, 6):
            await page.wait_for_timeout(wait_s * 1000)
            probe = await page.evaluate(PROBE_JS)
            result.setdefault("probes", []).append({"after_s": wait_s, **probe})
            if probe.get("any_visible_hc"):
                break

        # Final screenshot for evidence
        shot = Path(__file__).parent / f"submit_probe_{name.lower()}_stealth{int(use_stealth)}.png"
        try:
            await page.screenshot(path=str(shot), full_page=False)
            result["screenshot"] = str(shot)
        except Exception:
            pass

    except Exception as e:
        result["error"] = str(e)

    await ctx.close()
    await browser.close()
    return result


async def main():
    results = []
    async with async_playwright() as p:
        for name, url in URLS:
            for use_stealth in (False, True):
                print(f"-> {name} stealth={use_stealth}", flush=True)
                r = await attempt_submit(p, name, url, use_stealth)
                # summary line
                last = (r.get("probes") or [{}])[-1]
                print(f"   any_visible_hc={last.get('any_visible_hc')} challenge={len(last.get('challenge_iframes', []))} checkbox={len(last.get('checkbox_iframes', []))}")
                results.append(r)

    out = Path(__file__).parent / "test_lever_submit_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out}")

    print("\n=== SUBMIT-TIME SUMMARY ===")
    for r in results:
        last = (r.get("probes") or [{}])[-1]
        print(f"{r['site']:10s} stealth={r['stealth']!s:5s}  visible_hc_challenge={last.get('any_visible_hc')}  challenge_iframes={len(last.get('challenge_iframes', []))}  checkbox_iframes={len(last.get('checkbox_iframes', []))}")

if __name__ == "__main__":
    asyncio.run(main())
