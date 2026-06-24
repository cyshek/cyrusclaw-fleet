#!/usr/bin/env python3
"""
Debug BambooHR submit confirmation and discover field IDs for job 850.
Also attempt submission for 3377 with correct field IDs.
"""
import sys, time, json, sqlite3, os
from pathlib import Path
from playwright.sync_api import sync_playwright

CDP = "http://127.0.0.1:18800"
RDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery")
DB = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db")
RESUME = str(Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/resume/Cyrus_Shekari_Resume.pdf"))
APPDIR = Path("/home/azureuser/.openclaw/agents/job-search/workspace/applications/submitted")
CAPSOLVER_KEY = os.environ.get("CAPSOLVER_API_KEY", "")

PI = {
    "first_name": "Cyrus", "last_name": "Shekari",
    "email": "cyshekari@gmail.com", "phone": "3468040227",
    "street": "12420 NE 120th St #1437", "city": "Kirkland",
    "state": "Washington", "zip": "98034",
    "linkedin": "https://linkedin.com/in/cyshekari",
    "desired_pay": "150000",
}


def log(*a):
    print("[bh3377]", *a, flush=True)


def fill_field_by_name(page, field_name, value):
    """Fill by name attribute."""
    return page.evaluate("""([nm, val]) => {
        let el = document.querySelector('[name="' + nm + '"]');
        if (!el) return 'NOT_FOUND:' + nm;
        const proto = el.tagName === 'TEXTAREA'
            ? window.HTMLTextAreaElement.prototype
            : window.HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value');
        if (setter && setter.set) setter.set.call(el, val);
        else el.value = val;
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('blur', {bubbles:true}));
        return 'OK:' + (el.value||'').slice(0,10);
    }""", [field_name, value])


def fill_field_by_id(page, field_id, value):
    """Fill by id."""
    return page.evaluate("""([fid, val]) => {
        let el = document.getElementById(fid);
        if (!el) return 'NOT_FOUND:' + fid;
        const proto = el.tagName === 'TEXTAREA'
            ? window.HTMLTextAreaElement.prototype
            : window.HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value');
        if (setter && setter.set) setter.set.call(el, val);
        else el.value = val;
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
        el.dispatchEvent(new Event('blur', {bubbles:true}));
        return 'OK:' + (el.value||'').slice(0,10);
    }""", [field_id, value])


pw = sync_playwright().start()
br = pw.chromium.connect_over_cdp(CDP)
ctx = br.contexts[0]

# Close stale tabs
for p in list(ctx.pages):
    try:
        if "bamboohr" in p.url:
            p.close()
    except:
        pass
time.sleep(0.5)

page = ctx.new_page()
page.goto("https://uphold.bamboohr.com/careers/850", wait_until="domcontentloaded", timeout=30000)
time.sleep(2)

# Click Apply for This Job
page.locator('a:has-text("Apply for This Job"), button:has-text("Apply for This Job")').first.click(timeout=8000)
time.sleep(3)

# Discover all form fields
fields = page.evaluate("""() => {
    const inputs = [...document.querySelectorAll('input:not([type=hidden]):not([type=file]):not([type=radio]):not([type=checkbox])')].map(i => ({
        id: i.id, name: i.name, type: i.type, label: null
    }));
    // Get label text for each
    for (const inp of inputs) {
        if (inp.id) {
            const lbl = document.querySelector('label[for="' + inp.id + '"]');
            if (lbl) inp.label = (lbl.innerText||'').trim().replace(/[*\\s]+$/, '');
        }
    }
    return inputs;
}""")
log("Form fields:")
for f in fields:
    log(f"  id={f['id']!r:30s} name={f['name']!r:30s} label={f['label']!r}")

page.close()
