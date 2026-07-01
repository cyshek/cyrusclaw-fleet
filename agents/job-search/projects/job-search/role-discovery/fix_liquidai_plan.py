import json
plan_path = 'output/inline-plan-liquid-ai-e560189f-f3a7-4fc9-8b16-5d05ecefe629.json'
plan = json.load(open(plan_path))
for r in plan.get('radios', []):
    if 'currently located' in r.get('label', '').lower():
        print('Before:', r['value'])
        r['value'] = 'Other US location (open to relocation)'
        print('After:', r['value'])
with open(plan_path, 'w') as f:\n    json.dump(plan, f, indent=2)\nprint('Saved.')\nEOF\npython3 fix_liquidai_plan.py
