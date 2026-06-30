import json, re
from collections import Counter

d = json.load(open("batch4_payload.json"))
issues = []
seen_to = {}
NL = chr(10)
BACKSLASH_N = chr(92) + "n"   # the two-char sequence backslash + n

for r in d:
    b = r["body"]; subj = r["subject"]; name = r["name"]; to = r["to"]
    line1 = b.split(NL)[0]
    mfn = re.match(r"Hi (.+),", line1)
    fn = mfn.group(1) if mfn else "??"
    for txt in (subj, b):
        for m in re.finditer(r"(\d+)\s+(reviews?)", txt):
            n, word = int(m.group(1)), m.group(2)
            if n == 1 and word != "review":
                issues.append((name, "PLURAL: '1 " + word + "' should be review"))
            if n != 1 and word == "review":
                issues.append((name, "PLURAL: '" + str(n) + " review' should be reviews"))
    badfn = ("law", "attorney", "office", "spa", "heating", "cooling", "roof", "firm",
             "skin", "crew", "team", "medi", "clinic", "injury", "divorce", "dental",
             "construction")
    if fn != "there" and any(w in fn.lower() for w in badfn):
        issues.append((name, "BAD FIRST NAME: Hi " + fn))
    if fn != "there" and re.search(r"\d", fn):
        issues.append((name, "FIRST NAME HAS DIGIT: Hi " + fn))
    msub = re.search(r"^(\d+) review", subj)
    if msub and int(msub.group(1)) > 12:
        issues.append((name, "REVIEW-GAP on high count: " + subj))
    if re.search(r"s's\b", b):
        issues.append((name, "POSSESSIVE oddity (s's)"))
    if b.count("https://cal.com/cyshek") != 1:
        issues.append((name, "BOOKING LINK count=" + str(b.count("https://cal.com/cyshek"))))
    if BACKSLASH_N in b:
        issues.append((name, "LITERAL backslash-n IN BODY"))
    wc = len(b.split())
    if wc > 170:
        issues.append((name, "LONG body wc=" + str(wc)))
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

fns = []
for r in d:
    m = re.match(r"Hi (.+),", r["body"].split(NL)[0])
    fns.append(m.group(1) if m else "??")
print()
print("first names -> named:", sum(1 for f in fns if f != "there"),
      "| 'there':", sum(1 for f in fns if f == "there"))
print("named values:", sorted(set(f for f in fns if f != "there")))
