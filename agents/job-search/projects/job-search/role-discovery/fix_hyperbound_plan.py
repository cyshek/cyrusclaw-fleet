import json

plan_path = 'output/inline-plan-hyperbound-2781ed68-e7cc-48d8-b10f-1e9dd3c850db.json'
d = json.load(open(plan_path))

portfolio_field = 'cc6e3a3d-1f2d-49e0-938b-3f3300d65783_65f37ac0-8145-430f-91a7-5c814220b669'
loom_field = 'cc6e3a3d-1f2d-49e0-938b-3f3300d65783_e5777929-6ad3-4bb5-bbe8-ccaec8865f1e'

tf = d.get('text_fields', {})
print("Before:")
print("  portfolio:", repr(str(tf.get(portfolio_field, ''))[:80]))
print("  loom:", repr(str(tf.get(loom_field, ''))[:80]))

tf[portfolio_field] = 'https://github.com/cyshek'
tf[loom_field] = 'https://linkedin.com/in/cyshekari'

print("After:")
print("  portfolio:", repr(tf[portfolio_field]))
print("  loom:", repr(tf[loom_field]))

with open(plan_path, 'w') as f:\n    json.dump(d, f, indent=2)\nprint("Plan updated.")
