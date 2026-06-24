import json

PLAN = 'output/inline-plan-dust-4258daef-22e3-42cf-9de1-54bf500f5801.json'
old_key = 'dd82d9f7-1042-4930-a2f2-72da4acebc8d_0413b3cd-4aab-4050-ae54-834671545506'

d = json.load(open(PLAN))

if old_key in d.get('text_fields', {}):
    d['text_fields'][old_key] = '170000'
    print('Updated text_fields comp to 170000')

for step in d.get('steps', []):
    if step.get('tool') == 'ashby.type_text_fields':
        tf = step.get('args', {}).get('text_fields', {})
        if old_key in tf:
            tf[old_key] = '170000'
            print('Updated step text_fields comp to 170000')
    if step.get('tool') == 'browser.act.evaluate':
        fn = step.get('args', {}).get('fn', '')
        needle = '"0413b3cd-4aab-4050-ae54-834671545506": "Open to discuss"'
        if needle in fn:
            step['args']['fn'] = fn.replace(needle, '"0413b3cd-4aab-4050-ae54-834671545506": "170000"')
            print('Updated evaluate fn')

json.dump(d, open(PLAN, 'w'), indent=2)
print('Saved')
