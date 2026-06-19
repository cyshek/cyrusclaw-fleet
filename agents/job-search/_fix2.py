import ast
p = "role-discovery/_adp_probe_addr.py"
s = open(p).read()
bad = chr(92) + "n"
s = s.replace("as e:" + bad + "    print(\"country fill exc:\", str(e)[:120])",
              "as e:\n    print(\"country fill exc:\", str(e)[:120])")
open(p, "w").write(s)
print("remaining literal backslash-n:", s.count(bad))
try:
    ast.parse(s); print("SYNTAX OK")
except SyntaxError as exc:
    print("ERR", exc.lineno, exc.text)
