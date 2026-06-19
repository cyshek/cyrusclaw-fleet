import json

# Load batch 1 (17 entries from raw_results.json)
batch1 = json.load(open('/tmp/raw_results.json'))

# Load batch 2 (10 entries from biz2.py)
batch2 = json.load(open('/tmp/biz2_results.json'))

# Vertical mapping for batch1 entries
vertical_map = {
    'dilippatelcpa.com': 'cpa',
    'cpapatelandparikh.com': 'cpa',
    'gullacpa.com': 'cpa',
    'jdjcpa.com': 'cpa',
    'mjacsi.com': 'construction',
    'peakconstruction.com': 'construction',
    'garysautorepair.com': 'auto_repair',
    'gastleysautorepair.com': 'auto_repair',
    'cutclean.com': 'landscaping',
    'yandllandscaping.com': 'landscaping',
    'aalawns.com': 'landscaping',
    'premierlawn.com': 'landscaping',
    'pestshieldinc.com': 'pest_control',
    'anchorpestcontrol.net': 'pest_control',
    'bugbusters.com': 'pest_control',
    'firemanpestcontrol.com': 'pest_control',
    'wittpm.com': 'pest_control',
}

vertical_map2 = {
    'aceautoshop.com': 'auto_repair',
    'greatbearautoshop.com': 'auto_repair',
    'smalltownbuilders.com': 'construction',
    'sbasgroup.com': 'cpa',
    'jpacpa.com': 'cpa',
    'gillespie-cpas.com': 'cpa',
    'ckconstruction.net': 'construction',
    'harrisonconstruction.com': 'construction',
    'sunriselandscaping.com': 'landscaping',
    'greenleaflandscaping.com': 'landscaping',
}

# Tag verticals
for e in batch1:
    e['_vertical'] = vertical_map.get(e['domain'], 'unknown')

for e in batch2:
    e['_vertical'] = vertical_map2.get(e['domain'], 'unknown')

all_entries = batch1 + batch2

# Deduplicate by domain
seen = set()
unique = []
for e in all_entries:
    if e['domain'] not in seen:
        seen.add(e['domain'])
        unique.append(e)

print(f"Total unique: {len(unique)}")

# Count per vertical
from collections import Counter
vc = Counter(e['_vertical'] for e in unique)
print("Vertical counts:", dict(vc))

# Pick up to 5 per vertical, prioritize scraped > mx_pattern
verticals = ['cpa', 'construction', 'auto_repair', 'landscaping', 'pest_control']
selected = []
for v in verticals:
    pool = [e for e in unique if e['_vertical'] == v]
    # Sort: scraped first
    pool.sort(key=lambda x: 0 if x.get('source') == 'scraped' else 1)
    selected.extend(pool[:5])
    print(f"  {v}: picked {min(len(pool),5)} of {len(pool)}")

print(f"Selected: {len(selected)}")

# Strip internal _vertical key
output = []
for e in selected:
    row = {k: v for k, v in e.items() if not k.startswith('_')}
    output.append(row)

# Write output
import os
os.makedirs('/home/azureuser/.openclaw/agents/making-money/workspace/outreach', exist_ok=True)
out_path = '/home/azureuser/.openclaw/agents/making-money/workspace/outreach/batch2_chunk3.json'
with open(out_path, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Written {len(output)} entries to {out_path}")
print("DONE:", len(output))
