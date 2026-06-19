import ast, sys
p = "role-discovery/_adp_wfn_runner.py"
s = open(p).read()
n_before = s.count(chr(92) + "n")  # literal backslash-n
# Replace literal backslash-n sequences with real newline where they corrupt except blocks
bad = chr(92) + "n"
s = s.replace("last = e" + bad + "    raise", "last = e\n    raise")
s = s.replace("as e:" + bad + "            last = e", "as e:\n            last = e")
s = s.replace("as e:" + bad + "            log(", "as e:\n            log(")
s = s.replace("as e:" + bad + "        log(", "as e:\n        log(")
open(p, "w").write(s)
n_after = s.count(bad)
print("literal backslash-n before=%d after=%d" % (n_before, n_after))
try:
    ast.parse(s)
    print("SYNTAX OK")
except SyntaxError as exc:
    print("SYNTAX ERR line", exc.lineno, ":", exc.text)
