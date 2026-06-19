#!/usr/bin/env python3
"""Re-login to Uber Careers (reuse saved acct) and land on the apply form for <job_id>.
Reuses _uber_apply.py's attach/open_form/sign_in/create_account. Returns exit 0 if the
form (input[name=firstName]) is visible, else nonzero.
Usage: _uber_login.py <job_id>
"""
import sys, json, time
from pathlib import Path
import _uber_apply as U

job_id=sys.argv[1]
creds=json.load(open(".uber-creds.json"))["account"]
email=creds["email"]; pw_=creds["password"]
print("[login] acct", email)

pw, br, ctx = U.attach()
# reuse an existing tab (prefer one already on this job's form, else newtab/blank)
page=None
for p in ctx.pages:
    if f"/careers/apply/form/{job_id}" in p.url:
        page=p; break
if not page:
    for p in ctx.pages:
        if "newtab" in p.url or p.url in ("about:blank",""):
            page=p; break
if not page:
    page=ctx.new_page()

# Already signed in? check current state on the form
def on_form():
    try: return page.locator("input[name=firstName]").count()>0
    except Exception: return False

state=U.open_form(page, job_id)
print("[login] open_form ->", state)
if state=="closed":
    print("RESULT: CLOSED"); sys.exit(3)
if state=="form":
    print("[login] already signed in, form visible"); print("RESULT: FORM"); sys.exit(0)
if state=="account":
    r=U.sign_in(page, email, pw_)
    print("[login] sign_in ->", r)
    if r=="captcha":
        print("RESULT: CAPTCHA"); sys.exit(2)
    if r=="form" or on_form():
        print("RESULT: FORM"); sys.exit(0)
    # maybe needs create (account got lost?) — try create
    print("[login] sign-in did not reach form; trying create_account fallback")
    r2=U.create_account(page, email, pw_, no_verify=False)
    print("[login] create ->", r2)
    if on_form():
        print("RESULT: FORM"); sys.exit(0)
print("RESULT: UNKNOWN url=", page.url)
sys.exit(4)
