import ast
p = "role-discovery/_adp_aiopen.py"
s = open(p).read()
bad = chr(92) + "n"
s = s.replace("except Exception as e:" + bad + '    print("focus exc", str(e)[:60])',
              'except Exception as e:\n    print("focus exc", str(e)[:60])')
s = s.replace('"USD" in o:' + bad + "            target = o; break" + bad + "    if not target:",
              '"USD" in o:\n            target = o; break\n    if not target:')
open(p, "w").write(s)
print("remaining:", s.count(bad))
try:
    ast.parse(s); print("SYNTAX OK")
except SyntaxError as exc:
    print("ERR", exc.lineno, ":", exc.text)
