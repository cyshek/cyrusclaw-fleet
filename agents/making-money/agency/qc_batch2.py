import json, re
p = json.load(open('batch2_payload.json'))

print('--- all salutations (first line) ---')
SUSPECT = ('attorney','office','officecrew','admin','info','booking','justice','spa','medspa','law','center','clinic')
for x in p:\n    sal = x['body'].splitlines()[0]\n    flag = ''\n    m = re.match(r'Hi (\w+),', sal)\n    if m:\n        nm = m.group(1)\n        if nm != 'there' and nm.lower() in SUSPECT:
            flag = '  <-- SUSPECT'
    print(f"  {sal:30s} | {x['name']}{flag}")

print()
print('--- review-count grammar ("1 reviews" singular bug) ---')
hits = 0
for x in p:\n    if re.search(r'\b1 reviews\b', x['body']):
        print('  GRAMMAR:', x['name'], '-> "1 reviews"')
        hits += 1
print('  none' if not hits else f'  {hits} to fix')

print()
print('--- subjects ---')
for x in p:\n    print(f"  {x['subject']:34s} | {x['name']}")
