#!/usr/bin/env python3
"""Fix uber_robust.py - STATUS.md block and log/print newlines."""
import ast

NL = b'\x0a'
TARGET = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/uber_robust.py'
content = open(TARGET, 'rb').read()

# Fix 1: STATUS.md write_text block
# The original had f"...{title}\nstatus:..." but \n got corrupted
# Find the write_text call and replace with simpler form
old_block = (
    b'        (d / "STATUS.md").write_text(\n'
    b'            f"# Uber - {title}\x5c\x6estatus: submitted\x5c\x6erole_id: {role_id}\x5c\x6ejob_id: {job_id}\x5c\x6e"\n'
    b'            f"submitted_by: auto\nsubmitted_on: 2026-06-24\nconfirmation: {result}\nresume_attached: yes\n"\n'
    b'        )'
)
new_block = (
    b'        lines_out = [\n'
    b'            f"# Uber - {title}",\n'
    b'            f"status: submitted",\n'
    b'            f"role_id: {role_id}",\n'
    b'            f"job_id: {job_id}",\n'
    b'            "submitted_by: auto",\n'
    b'            "submitted_on: 2026-06-24",\n'
    b'            f"confirmation: {result}",\n'
    b'            "resume_attached: yes",\n'
    b'        ]\n'
    b'        (d / "STATUS.md").write_text("\\n".join(lines_out) + "\\n")'
)

if old_block in content:
    content = content.replace(old_block, new_block)
    print("Fixed STATUS.md block")
else:
    idx = content.find(b'(d / "STATUS.md").write_text(')
    if idx >= 0:
        print("STATUS.md block not matching, showing context:")
        print(repr(content[idx-10:idx+300]))

# Fix 2: log/print with \n+= formatting
replacements = [
    (b'    log("\\n" + "="*50)', b'    log("")'),
    (b'    print("\\n" + "="*50)', b'    print("")'),
    (b'    print("\\nSubmitted: " + str(len(submitted)) + "/" + str(len(JOBS)))', 
     b'    print("Submitted: " + str(len(submitted)) + "/" + str(len(JOBS)))'),
]
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"Fixed: {repr(old[:40])}")

open(TARGET, 'wb').write(content)

# Check remaining bad lines
bad = [(i+1, ln) for i, ln in enumerate(content.split(NL)) if b'\x5c\x6e' in ln]
print(f"Remaining bad lines: {len(bad)}")
for num, ln in bad[:10]:
    print(f"  {num}: {repr(ln[:100])}")

try:
    ast.parse(content.decode())
    print("Syntax OK")
except SyntaxError as se:
    print(f"SyntaxError: {se}")
