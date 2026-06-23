import json

plan_path = 'output/inline-plan-norm-ai-3fd0b773-58b9-48d9-9ab1-ba8078072c88.json'
with open(plan_path) as f:\n    plan = json.load(f)\n\n# Find and fix the NYC radio value\nfor r in plan.get('radios', []):
    if 'New York City' in r.get('label', ''):
        print(f'Before: {r}')
        r['value'] = 'No'
        r['alternates'] = ['no']
        print(f'After: {r}')

# Also fix in the steps JS (the __payload inside the fn strings)
for step in plan.get('steps', []):
    if step.get('tool') == 'browser.act.evaluate':
        fn = step.get('args', {}).get('fn', '')
        if 'Kirkland' in fn and 'New York City' in fn:
            # Fix the value in the payload
            new_fn = fn.replace('"value": "Kirkland", "alternates": []', '"value": "No", "alternates": ["no"]')
            if new_fn != fn:
                step['args']['fn'] = new_fn
                print('Fixed step fn payload')

with open(plan_path, 'w') as f:\n    json.dump(plan, f, indent=2)\nprint('Plan saved')\n