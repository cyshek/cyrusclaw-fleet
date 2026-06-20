"""Compare selfid screenshots and dump page state mid-flow."""
import sys, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright
import json

URL = "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/San-Jose/AEP-Data-Solutions-Engineer_R166534"

# Re-run from selfid via persistent context? Easier: just open the screenshot diffs.
# Actually let's just dump DOM of the stuck page by re-running and pausing.
import subprocess, time

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir="/tmp/wd-probe-adobe",
        headless=True,
        viewport={"width": 1400, "height": 900},
    )
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    print("URL:", page.url)
    print(page.locator("body").text_content()[:500])
    ctx.close()
