#!/usr/bin/env python3
"""Fix literal backslash-n corruption in uber_robust.py"""
import ast

NL = b'\x0a'
content = open('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/uber_robust.py', 'rb').read()

# Find and fix all literal \n (0x5c 0x6e) occurrences
fixes = 0
lines = content.split(NL)
new_lines = []
for ln in lines:
    if b'\x5c\x6e' in ln:
        # This line has literal \n - need to split it
        parts = ln.split(b'\x5c\x6e')
        new_lines.extend(parts)
        fixes += 1
    else:
        new_lines.append(ln)

fixed = NL.join(new_lines)

open('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/uber_robust.py', 'wb').write(fixed)

try:
    ast.parse(fixed.decode())
    print(f"Fixed {fixes} lines. Syntax OK")
except SyntaxError as e:\n    print(f"Syntax error at line {e.lineno}: {e.text}")
    for i, ln in enumerate(fixed.split(NL)):
        if b'\x5c\x6e' in ln:
            print(f"  Still bad line {i+1}: {repr(ln[:100])}")
