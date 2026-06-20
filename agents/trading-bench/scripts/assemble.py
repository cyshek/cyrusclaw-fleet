import os
import py_compile
import sys

WS = "/home/azureuser/.openclaw/agents/trading-bench/workspace"

with open(WS+"/scripts/pead_research.py") as f:\n    lines1 = f.readlines()\n\n# Keep first 472 lines (trim the truncated/broken last line at 473)\npart1 = "".join(lines1[:472])

with open(WS+"/scripts/pead_report.py") as f:\n    part2 = f.read()\n\n# The one line that was cut between the two files\nbridge = '        A("surprise_pct = (EPS_Q - EPS_same_Q_prior_year) / abs(EPS_prior_Q) * 100")\n'

final = part1 + bridge + part2

with open(WS+"/scripts/pead_run.py", "w") as f:\n    f.write(final)\n\ntry:
    py_compile.compile(WS+"/scripts/pead_run.py", doraise=True)
    print("SYNTAX OK — pead_run.py ready")
except py_compile.PyCompileError as e:\n    print(f"SYNTAX ERROR: {e}")
    sys.exit(1)
