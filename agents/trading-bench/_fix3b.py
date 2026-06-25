p = "_probe_task3b_resolve.py"
s = open(p).read()
a2 = 'with urllib.request.urlopen(req, timeout=30) as r:\\n        return json.load(r)\\n\\n\\ndef main():'
b2 = 'with urllib.request.urlopen(req, timeout=30) as r:\n        return json.load(r)\n\n\ndef main():'
found = a2 in s
if found:
    s = s.replace(a2, b2)
open(p, "w").write(s)
import py_compile
py_compile.compile(p, doraise=True)
print("OK compiled clean; fragment_found=%s" % found)
