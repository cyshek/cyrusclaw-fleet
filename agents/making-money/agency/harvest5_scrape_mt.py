#!/usr/bin/env python3
"""Threaded driver around sitescrape5's per-site logic. Same output
(harvest5_sitescrape.json) but ~12x faster via a thread pool. Pure stdlib.
"""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
import sitescrape5 as S

def scrape_one(r):
    url = r["website"]
    dom = r["domain"]
    parsed = urlparse(url)
    base = parsed.scheme + "://" + parsed.netloc
    pages = []
    home = S.fetch(url)
    if home:
        pages.append(home)
    tried = 0
    for path in S.CONTACT_PATHS:
        if tried >= 4:
            break
        c = S.fetch(urljoin(base, path), timeout=12)
        if c:
            pages.append(c)
            tried += 1
    blob = chr(10).join(pages)
    emails = []
    if blob:
        emails += S.EMAIL_RE.findall(blob)
    emails = [e for e in emails if S.good_email(e)]
    email, esource = S.pick_email(emails, dom)
    oname, osrc = (S.owner_name_from_html(blob) if blob else (None, None))
    if not oname:
        en = S.name_from_email(email)
        if en:
            oname, osrc = en, "email-local"
    hook = S.find_hook(blob.lower(), r.get("reviewCount")) if blob else \
           S.find_hook("", r.get("reviewCount"))
    rec = dict(r)
    rec["site_email"] = email
    rec["email_source"] = esource
    rec["owner_first"] = oname
    rec["owner_first_source"] = osrc
    rec["site_hook"] = hook
    rec["emails_found"] = sorted(set(emails))[:8]
    return rec

def main():
    rows = json.load(open("harvest5_deduped.json"))
    out = []
    done = 0
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(scrape_one, r): r for r in rows}
        for fut in as_completed(futs):
            r = futs[fut]
            try:
                rec = fut.result(timeout=120)
            except Exception as e:
                rec = dict(r); rec["site_email"] = None; rec["email_source"] = None
                rec["owner_first"] = None; rec["owner_first_source"] = None
                rec["site_hook"] = S.find_hook("", r.get("reviewCount"))
                rec["emails_found"] = []
            out.append(rec)
            done += 1
            print("[%3d/%d] %-26s mail=%-26s name=%-10s hook=%s" % (
                done, len(rows), rec["domain"][:26], (rec.get("site_email") or "-")[:26],
                (rec.get("owner_first") or "-")[:10], (rec.get("site_hook") or "-")[:24]),
                file=sys.stderr)
            if done % 20 == 0:
                json.dump(out, open("harvest5_sitescrape.partial.json", "w"),
                          ensure_ascii=False, indent=1)
    # keep deterministic order by original list
    order = {r["domain"]: i for i, r in enumerate(rows)}
    out.sort(key=lambda r: order.get(r["domain"], 1e9))
    json.dump(out, open("harvest5_sitescrape.json", "w"), ensure_ascii=False, indent=1)
    have = [r for r in out if r.get("site_email")]
    named = [r for r in out if r.get("owner_first")]
    personal = [r for r in out if (r.get("email_source") or "").startswith("site-personal")]
    hooks = [r for r in out if r.get("site_hook")]
    print("DONE. email=%d/%d  personal-inbox=%d  owner-name=%d  hooks=%d/%d" % (
        len(have), len(out), len(personal), len(named), len(hooks), len(out)),
        file=sys.stderr)

if __name__ == "__main__":
    main()
