p = "_probe3_wd_date.py"
s = open(p).read()
NL = chr(10)
BS_N = chr(92) + "n"
# Replace every literal 'as f:\n            f.write(' and 'as e:\n        return ...' / 'as e:\n                        ret = ...'\n# and the sync_playwright launch. Generic: any 'as X:' + BS_N + spaces is broken.
import re
# Generic regex: a line ending in ':' immediately followed by literal backslash-n then spaces then code.
# But we must avoid the f-string '... + chr(10))' and JS heredocs (those have real newlines already).
# Safe targeted replacements:
pairs = [
    ('with open(STATUS, "a") as f:' + BS_N + '            f.write(',
     'with open(STATUS, "a") as f:' + NL + '            f.write('),
    ('    with sync_playwright() as p:' + BS_N + '        ctx = p.chromium.launch_persistent_context(' + BS_N + '            user_data_dir',
     '    with sync_playwright() as p:' + NL + '        ctx = p.chromium.launch_persistent_context(' + NL + '            user_data_dir'),
]
for bad, good in pairs:
    c = s.count(bad); s = s.replace(bad, good); print("repl", c, repr(bad[:38]))

# Now handle the many 'except Exception as e:\n<spaces>...' one-liners generically.
# Match: 'except Exception as e:' + literal backslash-n + run of spaces + non-space
patt = re.compile(r'except Exception as e:' + re.escape(BS_N) + r'( +)')
n = len(patt.findall(s))
s = patt.sub(lambda m: 'except Exception as e:' + NL + m.group(1), s)
print("except-oneliner repl:", n)
open(p, "w").write(s)
print("WROTE_OK")
