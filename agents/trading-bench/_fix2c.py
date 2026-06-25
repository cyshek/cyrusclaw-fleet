p = "_probe_task2c_recycle.py"
s = open(p).read()
a = 'with urllib.request.urlopen(req, timeout=30) as r:\\n                d = json.load(r)\\n            res = d.get("chart", {}).get("result")'
b = 'with urllib.request.urlopen(req, timeout=30) as r:\n                d = json.load(r)\n            res = d.get("chart", {}).get("result")'
found = a in s
if found:
    s = s.replace(a, b)
open(p, "w").write(s)
import py_compile
py_compile.compile(p, doraise=True)
print("OK compiled clean; fragment_found=%s" % found)
