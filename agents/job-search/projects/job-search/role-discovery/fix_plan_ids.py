import json

# Map: plan file -> correct role_id (from STATUS.md)
corrections = {
    'output/inline-plan-chime-8530421002.json': 3004,
    'output/inline-plan-nice-4847972101.json': 3296,
    'output/inline-plan-nice-4849399101.json': 3297,
    'output/inline-plan-otter-8402672002.json': 3239,
    'output/inline-plan-path-robotics-8571279002.json': 3478,
}

for planf, correct_id in corrections.items():
    d = json.load(open(planf))
    old_id = d.get('role_id')
    if old_id != correct_id:
        print(f'Updating {planf}: role_id {old_id} -> {correct_id}')
        d['role_id'] = correct_id
        with open(planf, 'w') as f:\n            json.dump(d, f, indent=2)\n    else:
        print(f'Already correct {planf}: role_id={correct_id}')
