import ast
p = "role-discovery/_adp_pi_next.py"
s = open(p).read()
bad = chr(92) + "n"
s = s.replace("if n:" + bad + "        line1.press", "if n:\n        line1.press")
open(p, "w").write(s)
print("remaining:", s.count(bad))
try:
    ast.parse(s); print("SYNTAX OK")
except SyntaxError as exc:
    print("ERR", exc.lineno, exc.text)
