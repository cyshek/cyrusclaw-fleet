import ast
p = "role-discovery/_adp_bothsalary.py"
s = open(p).read()
bad = chr(92) + "n"
s = s.replace("'USD' in o:" + bad + "            target=o; break" + bad + "    if not target",
              "'USD' in o:\n            target=o; break\n    if not target")
open(p, "w").write(s)
print("remaining:", s.count(bad))
try:
    ast.parse(s); print("SYNTAX OK")
except SyntaxError as exc:
    print("ERR", exc.lineno, ":", exc.text)
