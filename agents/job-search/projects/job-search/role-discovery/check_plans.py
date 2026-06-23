import json

slugs = [
    ('chime-8530421002', 'output/inline-plan-chime-8530421002.json'),
    ('figma-5837760004', 'output/inline-plan-figma-5837760004.json'),
    ('figma-6009613004', 'output/inline-plan-figma-6009613004.json'),
    ('nice-4847972101', 'output/inline-plan-nice-4847972101.json'),
    ('nice-4849399101', 'output/inline-plan-nice-4849399101.json'),
    ('otter-8402672002', 'output/inline-plan-otter-8402672002.json'),
    ('path-robotics-8571279002', 'output/inline-plan-path-robotics-8571279002.json'),
    ('securitize-4173649009', 'output/inline-plan-securitize-4173649009.json'),
    ('yipitdata-8002296', 'output/inline-plan-yipitdata-8002296.json'),
    ('ziprecruiter-7354406', 'output/inline-plan-ziprecruiter-7354406.json'),
    ('21shares-us-5823209004', 'output/inline-plan-21shares-us-5823209004.json'),
]
for slug, planf in slugs:
    d = json.load(open(planf))
    print(slug + ': plan_role_id=' + str(d.get('role_id')) + ' app_url=' + str(d.get('app_url',''))[:80])
