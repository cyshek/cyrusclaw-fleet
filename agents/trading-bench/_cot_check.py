import json, os
from pathlib import Path

WS = Path("/home/azureuser/.openclaw/agents/trading-bench/workspace")
COT_DIR = WS / "data_cache" / "cot"

recs = []
for yr in range(2010, 2027):
    f = COT_DIR / "parsed_0.json" 