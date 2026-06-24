#!/usr/bin/env python3
NL = b'\x0a'
content = open('/tmp/uber_diag2.py', 'rb').read()

old_except = b'    except Exception as e:\x5c\x6e        print("No popup:", str(e)[:100])'
new_except = b'    except Exception as e:' + NL + b'        print("No popup:", str(e)[:100])'

if old_except in content:
    content = content.replace(old_except, new_except)
    print("Fixed except line")
else:
    print("Pattern not found - checking lines...")
    for i, ln in enumerate(content.split(NL)):
        if b'except' in ln or b'\x5c\x6e' in ln:
            print(f"  Line {i+1}: {repr(ln[:100])}")

open('/tmp/uber_diag2.py', 'wb').write(content)
import ast
result = ast.parse(content.decode()) if True else None
print("Syntax OK")
