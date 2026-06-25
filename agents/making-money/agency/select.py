import json, re, html as ihtml
data=json.load(open('enriched.json'))

def clean_name(n):
    n=ihtml.unescape(n or "")
    n=re.sub(r'\s+',' ',n).strip()
    return n

def fmt_phone(p):
    if not p: return ""
    d=re.sub(r'\D','',p)
    if len(d)==11 and d[0]=='1': d=d[1:]
    if len(d)==10: return f"({d[0:3]}) {d[3:6]}-{d[6:]}"
    return p.strip()

VLABEL={"med_spa":"Med spa / aesthetics","personal_injury_law":"Personal injury law",
        "family_law":"Family law","hvac":"HVAC","roofing":"Roofing"}

def hook(d):
    e=d.get('enrich',{})
    name=clean_name(d['name'])
    rev=d.get('reviews'); rat=d.get('rating'); vert=d['vertical']
    slow=e.get('slow'); book=e.get('booking'); chat=e.get('chat'); form=e.get('form')
    # 1) explicit slow language
    if slow:
        s=slow.strip().rstrip('.')
        return f"Site promises to '{s}' instead of an instant reply — every lead waits while competitors answer in seconds."
    # 2) review weakness (need both rating and count, count low)
    try:
        rc=int(rev) if rev is not None else None
    except: rc=None
    if rc is not None and rc < 35 and rat:
        if vert in ("med_spa",):
            return f"Only {rc} Google reviews ({rat}\u2605) for an aesthetics brand that lives on reputation — no automated post-visit review ask is firing."
        if vert in ("personal_injury_law","family_law"):
            return f"Just {rc} reviews ({rat}\u2605) despite years in practice — no automated review request after case resolution, leaving easy social proof on the table."
        return f"Thin online reputation at {rc} reviews ({rat}\u2605) — no automated review-request flow after completed jobs."
    # 3) med spa / aesthetics: no online booking
    if vert=="med_spa" and not book:
        return "No online booking widget on the site — prospects must call or fill a form, and there's no instant auto-reply to hold the appointment."
    # 4) no chat/auto-reply + form/phone only
    if not chat and not book:
        if form:
            return "Contact form with no live chat or instant auto-reply — inbound leads sit unanswered until someone manually checks the inbox."
        return "No live chat, online booking, or instant auto-responder — every inbound call/email depends on a human noticing it in time."
    # 5) has booking but no chat (still no speed-to-lead on calls/forms)
    if not chat:
        return "Online booking exists but there's no instant text-back/auto-reply for phone or form leads who don't self-book — those leads can go cold."
    # 6) fallback: chat present -> review angle if any
    if rc is not None and rat:
        return f"Has live chat but only {rc} reviews ({rat}\u2605) — review generation isn't automated, so reputation lags the service quality."
    return "No automated speed-to-lead follow-up evident — inbound leads rely on manual, business-hours response."

# attach hook + cleaned fields
rows=[]
for d in data:
    e=d.get('enrich',{})
    if not e.get('ok'): 
        continue
    name=clean_name(d['name'])
    site=d.get('website') or ""
    email=(e.get('emails') or [""])[0]
    phone=fmt_phone(d.get('phone') or e.get('phone'))
    city=clean_name(d.get('city') or ""); st=d.get('state') or ""
    citystate=f"{city}, {st}".strip().strip(',')
    h=hook(d)
    # quality score for selection
    score=0
    if e.get('slow'): score+=5
    try:
        rc=int(d['reviews']) if d.get('reviews') is not None else None
    except: rc=None
    if rc is not None and rc<35: score+=4
    if d['vertical']=="med_spa" and not e.get('booking'): score+=3
    if not e.get('chat') and not e.get('booking'): score+=2
    if email: score+=2          # contactable
    if email.startswith(("info@","office@","contact@","hello@","frontdesk@","reception@","appointments@","newpatients@","intake@")): score+=1
    if phone: score+=1
    if not site: score-=10
    rows.append({"name":name,"vertical":d['vertical'],"vlabel":VLABEL.get(d['vertical'],d['vertical']),
                 "city_state":citystate,"website":site,"email":email,"phone":phone,
                 "hook":h,"score":score,"reviews":d.get('reviews'),"rating":d.get('rating'),
                 "has_email":bool(email)})
json.dump(rows, open('scored.json','w'), ensure_ascii=False, indent=0)
from collections import Counter
print("scored rows:", len(rows))
for k,v in Counter(r['vertical'] for r in rows).most_common(): print(" ",k,v)
