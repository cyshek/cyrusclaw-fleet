#!/usr/bin/env python3
with open('/home/azureuser/.openclaw/agents/interview-prep/workspace/build_bundles.py') as f:\n    content = f.read()\nbad_lines = []\nfor i, line in enumerate(content.splitlines()):
    if '\\n' in line and not line.strip().startswith('#'):
        bad_lines.append((i+1, line))
if bad_lines:
    print(f'WARNING: literal backslash-n on lines:')
    for ln, text in bad_lines:
        print(f'  line {ln}: {text!r}')
else:
    print('No literal backslash-n found - file looks clean')
print(f'Total lines: {len(content.splitlines())}')
try:
    compile(content, 'build_bundles.py', 'exec')
    print('Syntax OK')
except SyntaxError as e:\n    print(f'Syntax ERROR: {e}')
