import re
p = "_probe5_wd_date.py"
s = open(p).read()
NL = chr(10); BS_N = chr(92) + "n"
pairs = [
    ('with open(STATUS, "a") as f:' + BS_N + '            f.write(',
     'with open(STATUS, "a") as f:' + NL + '            f.write('),
    ('    with sync_playwright() as p:' + BS_N + '        ctx = p.chromium.launch_persistent_context(' + BS_N + '            user_data_dir',
     '    with sync_playwright() as p:' + NL + '        ctx = p.chromium.launch_persistent_context(' + NL + '            user_data_dir'),
]
for bad, good in pairs:
    c = s.count(bad); s = s.replace(bad, good); print("repl", c, repr(bad[:34]))
patt = re.compile(r'except Exception as e:' + re.escape(BS_N) + r'( +)')
n = len(patt.findall(s)); s = patt.sub(lambda m: 'except Exception as e:' + NL + m.group(1), s)
print("except repl:", n)
open(p, "w").write(s); print("OK")
