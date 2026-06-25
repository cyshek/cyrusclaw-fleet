import json, re, html as ihtml

sel=json.load(open('selected.json'))

PLACEHOLDER = {
 "user@domain.com","your@email.com","youremail@yourbusiness.com","example@mysite.com",
 "someone@example.com","name@example.com","email@example.com","jane.doe@email.com",
 "john.doe@email.com","yourname@email.com","test@test.com","info@example.com",
 "hello@example.com","emailhello@eumorphiamedspa.com","email@domain.com","you@example.com",
 "sample@email.com","firstname.lastname@example.com"
}
PLACEHOLDER_PAT = re.compile(r'(example\.com|mysite\.com|yourbusiness|yourdomain|domain\.com|email\.com$|@email\.|lastname|firstname|sentry|wixpress|@2x|placeholder|test@)', re.I)
# known third-party theme/agency domains that leak into scrapes
THIRDPARTY = re.compile(r'(indiantypefoundry|sansoxygen|townsquareinteract|themeforest|envato|godaddy|wix|squarespace|duda|weebly|elementor|wpengine|bluehost|hostgator|mailchimp|constantcontact)', re.I)

def base_domain(u):
    if not u: return ""
    d=re.sub(r'^https?://(www\.)?','',u).split('/')[0].lower()
    return d

def email_domain(e):
    return e.split('@')[-1].lower() if e and '@' in e else ""

def root(d):
    # crude eTLD+1
    parts=d.split('.')
    return ".".join(parts[-2:]) if len(parts)>=2 else d

def good_email(e, site):
    if not e: return False
    e=e.lower()
    if e in PLACEHOLDER: return False
    if PLACEHOLDER_PAT.search(e): return False
    if THIRDPARTY.search(email_domain(e)): return False
    # gmail/yahoo/outlook personal are acceptable (common for SMBs)
    free = email_domain(e) in {"gmail.com","yahoo.com","outlook.com","hotmail.com","aol.com","icloud.com","comcast.net","live.com"}
    if free:
        return True
    # else require domain root match site root
    sr=root(base_domain(site)); er=root(email_domain(e))
    if sr and er and (sr==er or er.endswith(sr) or sr.endswith(er)):
        return True
    # allow plausible same-brand parent (e.g. spokanederm for werschler) only if not third-party -> accept
    return True if not THIRDPARTY.search(er) and er not in {"email.com"} else False

# load full enriched to recover a contact URL / better email if needed
enr={ (d['name']): d for d in json.load(open('enriched.json')) }

def contact_url(site):
    return site.rstrip('/')+"/contact" if site else ""

cleaned=[]
for r in sel:
    e=r['email']
    if not good_email(e, r['website']):
        # try other emails from enrichment
        full=enr.get(r['name'],{})
        alts=(full.get('enrich',{}) or {}).get('emails',[]) or []
        picked=""
        for a in alts:
            if good_email(a, r['website']):
                picked=a; break
        if picked:
            r['email']=picked
        else:
            r['email']=""   # -> FORM ONLY
    cleaned.append(r)

# For rows with no email, set email field to "FORM ONLY: <contact url>"
for r in cleaned:
    if not r['email']:
        cu=contact_url(r['website'])
        r['email_out']=f"FORM ONLY: {cu}" if cu else "FORM ONLY"
    else:
        r['email_out']=r['email']

# report
noemail=sum(1 for r in cleaned if not r['email'])
print("rows:",len(cleaned)," real-email:",len(cleaned)-noemail," form-only:",noemail)
json.dump(cleaned, open('selected.json','w'), ensure_ascii=False, indent=0)
for r in cleaned:
    print(f"[{r['vertical'][:8]:8}] {r['name'][:28]:28} -> {r['email_out'][:50]}")
