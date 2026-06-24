#!/usr/bin/env python3
"""Fix uber_robust.py corruption - run with python3."""
import sys

NL = b'\x0a'
TARGET = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/uber_robust.py'

content = open(TARGET, 'rb').read()
original = content

# Fix 1: Line 78 - the if/close/closed block collapsed onto one line
# Split at literal \n (0x5c 0x6e)
lines = content.split(NL)
new_lines = []
for ln in lines:
    if b'\x5c\x6e' not in ln:
        new_lines.append(ln)
        continue
    # Check if this is an f-string with intentional \n (like STATUS.md content)
    # Those start with f" and contain things like \nstatus:
    stripped = ln.strip()
    is_string_content = (stripped.startswith(b'f"') or stripped.startswith(b'f\'')) and b'status:' in ln
    is_log_newline = b'log(f"' in ln and b'=\'*50' in ln
    is_print_newline = b'print(f"' in ln and (b'=\'*50' in ln or b'Submitted:' in ln)
    is_code_continuation = not is_string_content

    if is_log_newline:
        new_lines.append(ln.replace(b'log(f"\\n{\'=\'*50}")', b'log("\\n" + "="*50)'))
    elif is_print_newline and b'=\'*50' in ln:
        new_lines.append(ln.replace(b'print(f"\\n{\'=\'*50}")', b'print("\\n" + "="*50)'))
    elif is_print_newline and b'Submitted:' in ln:
        new_lines.append(ln.replace(b'print(f"\\nSubmitted: {len(submitted)}/{len(JOBS)}")', b'print("\\nSubmitted: " + str(len(submitted)) + "/" + str(len(JOBS)))'))
    elif is_code_continuation:
        # Split on literal \n -> real newlines
        sub_parts = ln.split(b'\x5c\x6e')
        new_lines.extend(sub_parts)
    else:
        new_lines.append(ln)

content = NL.join(new_lines)
open(TARGET, 'wb').write(content)

import ast
try:
    ast.parse(content.decode())
    changed = len(content) - len(original)
    print(f"Syntax OK. Changed {len(original)} -> {len(content)} bytes ({changed:+d})")
except SyntaxError as se:
    print(f"SyntaxError at line {se.lineno}: {se.text}")
    for i, ln in enumerate(content.split(NL)):
        if b'\x5c\x6e' in ln:
            print(f"  Bad line {i+1}: {repr(ln[:120])}")
