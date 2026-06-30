import json, time, urllib.request, urllib.parse, urllib.error, sys

KEY = "2d85793600304bdb30cf721a9668a43871218ee9"
ENDPOINT = "https://api.hunter.io/v2/domain-search"

rows = json.load(open("harvest4_deduped.json"))

# role/generic locals we prefer (in order) when no good owner email
GENERIC_PREF = ["info", "contact", "office", "admin", "hello", "frontdesk",
                "reception", "booking", "appointments", "intake", "team"]

def pick_email(data):
    """Return (email, first_name, confidence, type) best choice or (None,...)."""
    emails = data.get("emails") or []
    if not emails:
        return None, None, None, None
    # 1) personal email with a first name + decent confidence
    personal = [e for e in emails if e.get("type") == "personal" and e.get("first_name")]
    personal.sort(key=lambda e: (e.get("confidence") or 0), reverse=True)
    for e in personal:
        if (e.get("confidence") or 0) >= 50:
            return e["value"], e.get("first_name"), e.get("confidence"), "personal"
    # 2) generic/role by preference order then confidence
    generic = [e for e in emails if e.get("type") == "generic" or not e.get("first_name")]
    def gkey(e):
        local = (e.get("value") or "").split("@")[0].lower()
        pref = GENERIC_PREF.index(local) if local in GENERIC_PREF else 99
        return (pref, -(e.get("confidence") or 0))
    generic.sort(key=gkey)
    if generic:
        e = generic[0]
        return e["value"], e.get("first_name"), e.get("confidence"), "generic"
    # 3) fallback: highest-confidence anything
    emails.sort(key=lambda e: (e.get("confidence") or 0), reverse=True)
    e = emails[0]
    return e["value"], e.get("first_name"), e.get("confidence"), e.get("type")

out = []
for i, r in enumerate(rows, 1):
    dom = r["domain"]
    url = ENDPOINT + "?" + urllib.parse.urlencode({"domain": dom, "api_key": KEY})
    email = fname = conf = etype = None
    err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            data = payload.get("data") or {}
            email, fname, conf, etype = pick_email(data)
            # hunter sometimes returns org name / pattern even with no emails
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = int(e.headers.get("Retry-After", "20"))
                print("  429 rate-limited, sleeping %ds" % wait, file=sys.stderr)
                time.sleep(wait)
                continue
            err = "HTTP %s" % e.code
            try:
                err += " " + e.read().decode("utf-8")[:120]
            except Exception:
                pass
            break
        except Exception as e:
            err = str(e)[:120]
            time.sleep(5)
            continue
    rec = dict(r)
    rec["email"] = email
    rec["hunter_first"] = fname
    rec["hunter_conf"] = conf
    rec["hunter_type"] = etype
    rec["hunter_err"] = err
    out.append(rec)
    tag = email if email else ("ERR:" + str(err) if err else "no-email")
    print("[%2d/%d] %-30s %-22s -> %s (conf=%s)" % (i, len(rows), dom[:30], r["vertical"], tag, conf), file=sys.stderr)
    time.sleep(1.2)

json.dump(out, open("harvest4_hunter.json", "w"), ensure_ascii=False, indent=1)
emailable = [r for r in out if r.get("email")]
print("DONE. emailable: %d / %d" % (len(emailable), len(out)), file=sys.stderr)
