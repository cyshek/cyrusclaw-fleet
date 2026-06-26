#!/bin/bash
set -e
cd /home/azureuser/.openclaw/agents/trading-bench/workspace
python3 - <<'PYEOF'
import io
p = "_regime_allocator.py"
src = open(p, "r").read()
# Replace literal two-char backslash-n with real newline ONLY where it was injected
# at statement boundaries. Build the literal sequence safely as chr(92)+'n'.
lit = chr(92) + "n"
src = src.replace(lit, chr(10))
open(p, "w").write(src)
print("replaced literal backslash-n with newline")
PYEOF
echo "=== remaining literal backslash-n? ==="
grep -n -F '\n' _regime_allocator.py || echo "NONE"
python3 -m py_compile _regime_allocator.py && echo "COMPILE OK"
