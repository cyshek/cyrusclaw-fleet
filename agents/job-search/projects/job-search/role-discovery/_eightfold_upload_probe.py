#!/usr/bin/env python3
# Eightfold resume upload network probe
import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

CDP_URL = "http://127.0.0.1:18800"
JOB_URL = "https://explore.jobs.netflix.net/careers/job/790316069889"
PDF_PATH = str(Path(__file__).parent.parent / "applications/submitted/orca-security-5823501004/Cyrus_Shekari_Resume_orcasecurity_5823501004_v2.pdf")
OUT_JSON = "/tmp/eightfold-upload-probe.json"

SKIP_EXT = [".js",".css",".woff",".png",".svg",".ico",".jpg",".ttf",".woff2",".map"]
captured = []

def skip(url):
    return any(url.endswith(x) or ("chunk" in url and x == ".js") for x in SKIP_EXT)

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(CDP_URL)
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await ctx.new_page()

        def on_request(req):
            if skip(req.url): return
            entry = {"type":"request","url":req.url,"method":req.method,
                     "headers":dict(req.headers),"post":(req.post_data or "")[:500]}
            captured.append(entry)
            print(f"REQ {req.method} {req.url[:120]}")

        async def on_response(resp):
            if skip(resp.url): return
            try:
                body = (await resp.body())[:500].decode("utf-8","replace")
            except Exception:
                body = "<err>"
            captured.append({"type":"response","url":resp.url,"status":resp.status,"body":body})
            print(f"RES {resp.status} {resp.url[:100]} | {body[:80]}")

        page.on("request", on_request)
        page.on("response", on_response)

        print("[*] Navigating to job page...")
        await page.goto(JOB_URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        # Click Apply
        for sel in ["text=Apply", "button:has-text('Apply')", "a:has-text('Apply')"]:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    print(f"[*] Clicking: {sel}")
                    await el.click()
                    await page.wait_for_timeout(4000)
                    break
            except Exception:
                pass

        print(f"[*] URL: {page.url}")
        await page.wait_for_timeout(2000)

        # Find file input
        file_inp = await page.query_selector("input[type='file']")
        print(f"[*] File input: {file_inp is not None}")

        if file_inp:
            try:
                await file_inp.set_input_files(PDF_PATH)
                print("[*] set_input_files called, waiting for network...")
                await page.wait_for_timeout(7000)
            except Exception as e:
                print(f"[!] set_input_files error: {e}")

        # Try dropzone click
        for sel in [".dropzone","[class*='dropzone']","[class*='upload']"]:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    async def handle_chooser(fc):
                        print("[*] FileChooser!")
                        await fc.set_files(PDF_PATH)
                    page.once("filechooser", handle_chooser)
                    await el.click()
                    await page.wait_for_timeout(4000)
            except Exception:
                pass

        # JS probe
        try:
            info = await page.evaluate("""() => {
                const scripts = Array.from(document.scripts).map(s=>s.src)
                    .filter(s=>s && (s.includes('filestack')||s.includes('uploader')));
                const state = window.__INITIAL_STATE__ || window.__APP_STATE__ || null;
                return {scripts, state_keys: state ? Object.keys(state) : []};
            }""")
            print(f"[*] FS scripts: {info['scripts']}")
            print(f"[*] State keys: {info['state_keys'][:10]}")
            captured.append({"type":"js_probe","info":info})
        except Exception as e:
            print(f"[!] JS probe: {e}")

        await page.wait_for_timeout(3000)
        await page.close()

    Path(OUT_JSON).write_text(json.dumps(captured, indent=2))
    print(f"[*] {len(captured)} events -> {OUT_JSON}")

    upload_events = [e for e in captured if
        any(k in e.get("url","").lower() for k in ["upload","filestack","s3","blob","resume","multipart"])
        or (e.get("method") in ("POST","PUT") and e.get("type")=="request")]

    print(f"\n=== UPLOAD-RELEVANT ({len(upload_events)}) ===")
    for e in upload_events:
        print(json.dumps(e, indent=2)[:700])

    return upload_events

if __name__ == "__main__":
    asyncio.run(main())
