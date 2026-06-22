from adapters import workday

TESTS = [
    ('Micron', 'micron.wd1.myworkdayjobs.com', 'micron', 'External'),
    ('CrowdStrike', 'crowdstrike.wd5.myworkdayjobs.com', 'crowdstrike', 'crowdstrikecareers'),
    ('Target', 'target.wd5.myworkdayjobs.com', 'target', 'targetcareers'),
    ('Pfizer', 'pfizer.wd1.myworkdayjobs.com', 'pfizer', 'PfizerCareers'),
    ('ServiceTitan', 'servicetitan.wd1.myworkdayjobs.com', 'servicetitan', 'ServiceTitan'),
]

for name, host, tenant, site in TESTS:
    try:
        roles = workday.fetch(name, '', host=host, tenant=tenant, site=site)
        print(f'{name}: {len(roles)} target-term roles fetched')
        for r in roles[:2]:
            print(f'    - {r.title[:60]} | {r.location[:30]}')
    except Exception as e:
        print(f'{name}: ERROR {type(e).__name__}: {e}')
