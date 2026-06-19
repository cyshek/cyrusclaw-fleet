import json

TEMPLATES = {
    "viewport": (
        "DOMAIN \u2014 quick fix for site not configured as mobile-friendly",
        "your site isn\u2019t configured as mobile-friendly \u2014 Google now ranks mobile experience first, so this directly tanks your position."
    ),
    "share": (
        "DOMAIN \u2014 quick fix for blank preview when shared on social",
        "when someone shares your site on social media or iMessage, it shows up blank with no preview image or description."
    ),
    "meta_desc": (
        "DOMAIN \u2014 quick fix for missing meta description",
        "your meta description is missing \u2014 the snippet Google shows under your site name in search results is blank, so people skip past you."
    ),
    "h1": (
        "DOMAIN \u2014 quick fix for missing main heading",
        "your main heading (H1) is missing \u2014 that\u2019s one of the first things Google reads to understand what your page is about."
    ),
}

data = json.load(open('/home/azureuser/.openclaw/agents/making-money/workspace/outreach/batch2_chunk3.json'))

fixed = 0
output = []
for e in data:
    domain = e['domain']
    fail = e.get('top_fail', 'viewport')
    if fail not in TEMPLATES:
        fail = 'viewport'

    if 'subject' not in e or 'body' not in e:
        subj_tmpl, body_intro = TEMPLATES[fail]
        subj = subj_tmpl.replace("DOMAIN", domain)
        body = ("Hi \u2014 I ran a free audit on " + domain +
                " and the main thing that stood out: " + body_intro +
                " This is likely costing you rankings and new customers finding you online."
                " Full report (no signup needed): https://sitelume.app/audit/?url=" + domain +
                "\n\n\u2014 Cyrus")
        e['subject'] = subj
        e['body'] = body
        fixed += 1

    clean = {k: v for k, v in e.items() if k in ('domain', 'to', 'source', 'top_fail', 'subject', 'body')}
    output.append(clean)

print(f"Fixed {fixed} entries, total {len(output)}")
json.dump(output, open('/home/azureuser/.openclaw/agents/making-money/workspace/outreach/batch2_chunk3.json', 'w'), indent=2, ensure_ascii=False)
print("Saved.")
