import json, re
from collections import Counter

d = json.load(open("batch5_payload.json"))
issues = []
seen_to = {}
NL = chr(10)
BACKSLASH_N = chr(92) + "n"   # literal backslash + n

CAL = "cal.com/cyshek"
DEMO_ASK = "Just reply and I'll fire it over."

for r in d:
    b = r["body"]; subj = r["subject"]; name = r["name"]; to = r["to"]
    line1 = b.split(NL)[0]
    mfn = re.match(r"Hi (.+),", line1)
    fn = mfn.group(1) if mfn else "??"
    # singular/plural reviews
    for txt in (subj, b):
        for m in re.finditer(r"(\d+)\s+(reviews?)", txt):
            n, word = int(m.group(1)), m.group(2)
            if n == 1 and word != "review":
                issues.append((name, "PLURAL: '1 " + word + "' should be review"))
            if n != 1 and word == "review":
                issues.append((name, "PLURAL: '" + str(n) + " review' should be reviews"))
    # bad first name words
    badfn = ("law", "attorney", "office", "spa", "heating", "cooling", "roof", "firm",
             "skin", "crew", "team", "medi", "clinic", "injury", "divorce", "dental",
             "construction", "plumb", "mechanic", "electric", "comfort", "who", "what",
             "your", "our", "the", "we", "us")
    if fn != "there" and any(w == fn.lower() or w in fn.lower() for w in badfn):
        issues.append((name, "BAD FIRST NAME: Hi " + fn))
    if fn != "there" and re.search(r"\d", fn):
        issues.append((name, "FIRST NAME HAS DIGIT: Hi " + fn))
    if fn != "there" and not fn.isalpha():
        issues.append((name, "FIRST NAME NON-ALPHA: Hi " + fn))
    # review-gap only on low counts
    msub = re.search(r"^(\d+) review", subj)
    if msub and int(msub.group(1)) > 12:
        issues.append((name, "REVIEW-GAP on high count: " + subj))
    if re.search(r"s's\b", b):
        issues.append((name, "POSSESSIVE oddity (s's)"))
    # CTA CHANGE: NO cal.com link on first touch; demo reply ask present
    if CAL in b:
        issues.append((name, "CAL LINK present on first touch (should be 0)"))
    if b.count("http://") + b.count("https://") > 0:
        issues.append((name, "LINK present on first touch count=" +
                       str(b.count("http://") + b.count("https://"))))
    if DEMO_ASK not in b:
        issues.append((name, "MISSING soft demo reply ask"))
    if BACKSLASH_N in b:
        issues.append((name, "LITERAL backslash-n IN BODY"))
    if not b.rstrip().endswith("— Cyrus"):
        issues.append((name, "MISSING/!= '— Cyrus' sign-off"))
    wc = len(b.split())
    if wc > 140:
        issues.append((name, "LONG body wc=" + str(wc)))
    if wc < 60:
        issues.append((name, "SHORT body wc=" + str(wc)))
    seen_to.setdefault(to, []).append(name)
    if not to or "@" not in to:
        issues.append((name, "BAD TO: " + repr(to)))
    if not subj.strip():
        issues.append((name, "EMPTY SUBJECT"))

for to, names in seen_to.items():
    if len(names) > 1:
        issues.append((names[0], "DUP RECIPIENT " + to + " -> " + str(names)))

print("TOTAL emails:", len(d))
print("ISSUES:", len(issues))
for n, msg in issues:
    print("  -", n[:34], "|", msg)

# personalization metrics
fns = []
for r in d:
    m = re.match(r"Hi (.+),", r["body"].split(NL)[0])
    fns.append(m.group(1) if m else "??")
named = sum(1 for f in fns if f != "there")
personal = sum(1 for r in d if (r.get("email_source") or "").startswith("site-personal"))
print()
print("first names -> named:", named, "(%.0f%%)" % (100*named/max(1,len(d))),
      "| 'there':", sum(1 for f in fns if f == "there"))
print("named values:", sorted(set(f for f in fns if f != "there")))
print("personal-inbox recipients:", personal, "(%.0f%%)" % (100*personal/max(1,len(d))))
print()
print("By vertical:", dict(Counter(r["vertical"] for r in d)))
print("By city:", dict(Counter(r["city_state"] for r in d)))
print("Email source:", dict(Counter((r.get("email_source") or "?").split("(")[0] for r in d)))
