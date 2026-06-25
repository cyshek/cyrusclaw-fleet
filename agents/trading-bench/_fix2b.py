p = "_probe_task2b_yahoo.py"
s = open(p).read()
pairs = [
    ('with urllib.request.urlopen(req, timeout=30) as r:\\n                d = json.load(r)\\n            res = d.get("chart", {}).get("result")',
     'with urllib.request.urlopen(req, timeout=30) as r:\n                d = json.load(r)\n            res = d.get("chart", {}).get("result")'),
    ('except urllib.error.HTTPError as e:\\n            last = "HTTP %s" % e.code',
     'except urllib.error.HTTPError as e:\n            last = "HTTP %s" % e.code'),
    ('except Exception as e:\\n            last = str(e)[:60]',
     'except Exception as e:\n            last = str(e)[:60]'),
]
missing = []
for a, b in pairs:
    present = a in s
    if present:
        s = s.replace(a, b)
    else:
        missing.append(a[:60])
open(p, "w").write(s)
import py_compile
py_compile.compile(p, doraise=True)
print("OK compiled clean")
for m in missing:
    print("WARN missing:", m)
