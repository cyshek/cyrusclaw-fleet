"""Driver: run resolve_row across remaining slug-confirmed rows and print structured report."""
import json, sys
sys.path.insert(0, 'projects/job-search')
from linkedin_phase_b2 import resolve_row

ROWS = [
    # (rid, li_jid, ats, slug, expected_title_kw, li_url)
    (1056, 4394915191, 'greenhouse','axon',['product manager','hardware'],'https://www.linkedin.com/jobs/view/product-manager-ii-hardware-at-axon-4394915191'),
    (1140, 4351760206, 'greenhouse','hackerrank',['forward deployed','engineer'],'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-hackerrank-4351760206'),
    (1141, 4375000029, 'greenhouse','sixfold',['solutions engineer'],'https://www.linkedin.com/jobs/view/solutions-engineer-at-sixfold-4375000029'),
    (1147, 4401665335, 'ashby','neuralconcept',['solutions engineer'],'https://www.linkedin.com/jobs/view/solutions-engineer-at-neural-concept-4401665335'),
    (1166, 4410197158, 'lever','sitetracker',['solution architect'],'https://www.linkedin.com/jobs/view/solution-architect-at-sitetracker-4410197158'),
    (1213, 4386953210, 'ashby','moment',['forward deployed engineer'],'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-moment-4386953210'),
    (1299, 4415429063, 'ashby','dust',['solutions engineer'],'https://www.linkedin.com/jobs/view/solutions-engineer-at-dust-4415429063'),
    (1320, 4384712368, 'greenhouse','mattermost',['forward deployed engineer'],'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-mattermost-4384712368'),
    (1325, 4414925294, 'ashby','blaxel',['forward deployed engineer'],'https://www.linkedin.com/jobs/view/forward-deployed-engineer-fde-at-blaxel-yc-x25-4414925294'),
    (1332, 4415571509, 'ashby','thought-machine',['forward deployed engineer'],'https://www.linkedin.com/jobs/view/forward-deployed-engineer-at-thought-machine-4415571509'),
    (1301, 4403656824, 'lever','basis',['solutions engineer'],'https://www.linkedin.com/jobs/view/solutions-engineer-at-basis-4403656824'),
]
out = []
for rid, jid, ats, slug, kw, lurl in ROWS:
    status, ev = resolve_row(rid, jid, ats, slug, kw, lurl)
    ev['rid'] = rid
    ev['ats'] = ats
    ev['slug'] = slug
    ev['linkedin_url'] = lurl
    ev['status'] = status
    out.append(ev)
    print(f"rid={rid} | {ats}:{slug} | status={status} | confidence={ev.get('confidence','-')} | hits={len(ev.get('phrase_hits',[]))}")
    if status == 'match':
        j = ev['job']
        print(f"  -> {j['title']} | {j['location']} | {j['url']}")
        for p in ev['phrase_hits'][:3]:
            print(f"     ✓ {p[:100]}")
    elif 'reason' in ev:
        print(f"  reason: {ev['reason']}")
        if 'sample_titles' in ev:
            print(f"  sample titles: {ev['sample_titles'][:5]}")
with open('projects/job-search/applications/_linkedin-phase-b2-report.json','w') as f:
    json.dump(out, f, indent=2)
print(f'\nwrote phase-b2 report ({len(out)} rows)')
