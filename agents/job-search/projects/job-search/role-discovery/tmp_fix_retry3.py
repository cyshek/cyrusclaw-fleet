#!/usr/bin/env python3
"""Fix uber_retry3.py bad lines."""
import ast

NL = b'\x0a'
f = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/uber_retry3.py'
content = open(f, 'rb').read()

lines = content.split(NL)
new_lines = []
for ln in lines:
    if b'\x5c\x6e' not in ln:
        new_lines.append(ln)
        continue
    # Code continuation: split on literal \n -> real lines
    parts = ln.split(b'\x5c\x6e')
    new_lines.extend(parts)

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
