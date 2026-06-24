#!/usr/bin/env python3
"""One-shot patch: replace REPLACE_THIS_BLOCK lines in _workday_runner.py"""

with open('_workday_runner.py', 'r') as f:\n+    content = f.read()\n+\n+old = ('REPLACE_THIS_BLOCK\n' * 8).rstrip('\n')

new = (
    '    try:\n'
    '        # FIX2 (workday-wd1-button-fix 2026-06-23): countryPhoneCode on wd1 is a\n'
    '        # <button> showing "United States (+1)" by default but React state is empty.\n'
    '        # Use wd_pick_listbox (real Playwright click) to commit the React state.\n'
    '        # Fall back to _commit_wd_dropdown for wd5 tenants.\n'
    '        cpc_committed = False\n'
    '        for cpc_sel in ("button#phoneNumber--countryPhoneCode",\n'
    '                        "[data-automation-id=countryPhoneCode]"):\n'
    '            if page.locator(cpc_sel).count():\n'
    '                picked = wd_pick_listbox(page, cpc_sel, "United States of America (+1)")\n'
    '                if not picked:\n'
    '                    for alt in ["United States of America", "United States (+1)", "+1"]:\n'
    '                        if wd_pick_listbox(page, cpc_sel, alt):\n'
    '                            picked = True; break\n'
    '                if picked:\n'
    '                    log("countryPhoneCode: committed via wd_pick_listbox")\n'
    '                    cpc_committed = True\n'
    '                break\n'
    '        if not cpc_committed:\n'
    '            if not _commit_wd_dropdown(\n'
    '                    page, "countryPhoneCode",\n'
    '                    "United States of America (+1)",\n'
    '                    want_alts=["United States of America", "United States",\n'
    '                               "(+1)", "+1"]):\n'
    '                _MYINFO_COMMIT_FAIL = (\n'
    '                    (_MYINFO_COMMIT_FAIL + "+countryPhoneCode")\n'
    '                    if _MYINFO_COMMIT_FAIL else "countryPhoneCode")\n'
    '    except Exception as e:\n'\n+    '        log("country phone code fail", str(e)[:60])'
)

count = content.count(old)
print(f"Found {count} occurrences of REPLACE_THIS_BLOCK block")
if count == 1:
    content = content.replace(old, new)
    with open('_workday_runner.py', 'w') as f:\n+        f.write(content)\n+    print("Patched OK")
else:
    # Try with explicit newlines
    marker = 'REPLACE_THIS_BLOCK'
    all_indices = [i for i in range(len(content)) if content[i:].startswith(marker)]
    print(f"Marker found at lines: {[content[:i].count(chr(10)) + 1 for i in all_indices]}")
