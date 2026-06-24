#!/usr/bin/env python3
"""Fix rok_discover.py bad lines."""
import ast

NL = b'\x0a'
f = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/rok_discover.py'
content = open(f, 'rb').read()

lines = content.split(NL)
new_lines = []
for ln in lines:
    if b'\x5c\x6e' not in ln:
        new_lines.append(ln)
        continue
    # f-string with \n prefix for formatting - remove the \n
    if b'print(f"\\n' in ln or b'print("\\n' in ln:
        new_lines.append(ln.replace(b'\x5c\x6e', b''))
        continue
    # except ... as e: continuation - split on literal \n
    if b'except' in ln and b'as e:' in ln:
        parts = ln.split(b'\x5c\x6e')
        new_lines.extend(parts)
        continue
    new_lines.append(ln)

content = NL.join(new_lines)
open(f, 'wb').write(content)
try:
    ast.parse(content.decode())
    print("Syntax OK")
except SyntaxError as se:
    print(f"Error: {se}")
    for i, ln in enumerate(content.split(NL)):
        if b'\x5c\x6e' in ln:
            print(f"  {i+1}: {repr(ln[:80])}")
