import asyncio, os, sys
from datetime import datetime, timezone
sys.path.insert(0, '.')
from playwright.async_api import async_playwright

CDP = os.environ.get("JOBSEARCH_CDP", "http://127.0.0.1:18800")


async def probe():
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(CDP)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        graphql_responses = []

        async def on_response(resp):
            if 'graphql' in resp.url or 'careers/apply/api' in resp.url:
                try:
                    body = await resp.json()
                    graphql_responses.append({'url': resp.url, 'status': resp.status, 'body': body})
                except Exception as exc:
                    graphql_responses.append({'url': resp.url, 'status': resp.status, 'error': str(exc)})

        page.on("response", on_response)
        await page.goto("https://www.uber.com/careers/apply/form/159482", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        await page.locator("text=Create account").first.click()
        await page.wait_for_timeout(1500)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        EMAIL = f"cyshekari+uber-{ts}@gmail.com"
        PASSWORD = "K8mP2xQr5nWv9Lj"

        await page.locator('input[name="email"]').fill(EMAIL)
        await page.wait_for_timeout(300)
        await page.locator('input[type="password"]').fill(PASSWORD)
        await page.wait_for_timeout(500)
        graphql_responses.clear()

        await page.evaluate("""() => {
            const form = document.querySelector('form[data-testid="form-field-id"]');
            const submitBtn = form.querySelector('button[type="submit"]');
            submitBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
        }""")
        await page.wait_for_timeout(5000)

        print("GraphQL responses:")
        for r in graphql_responses:
            print(f"  {r['url']} status={r['status']}")
            body = r.get('body', r.get('error', ''))
            print(f"  body: {str(body)[:600]}")

        has_form = await page.locator("input[name=firstName]").count()
        print("has_form:", has_form)
        await ctx.close()


asyncio.run(probe())
