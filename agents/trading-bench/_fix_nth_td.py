
import re

path = '/home/azureuser/.openclaw/agents/trading-bench/workspace/strategies_candidates/pead_real/backtest_pead_v2.py'

with open(path, 'r') as f:\n    content = f.read()\n\n# Replace the broken single line that contains the literal escaped newlines\nold_line = r"            if count == n:\n                return d\n    return None\n\n\ndef adj_close(sym, date_str):"
new_lines = "            if count == n:\n                return d\n    return None\n\n\ndef adj_close(sym, date_str):"

content = content.replace(old_line, new_lines)

with open(path, 'w') as f:\n    f.write(content)\n\nprint("Done, checking syntax...")
import ast
try:
    ast.parse(content)
    print("Syntax OK!")
except SyntaxError as e:\n    print(f"SyntaxError at line {e.lineno}: {e.msg}")
    lines = content.split('\n')
    for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+3)):
        print(f"{i+1:4d}: {lines[i]!r}")
