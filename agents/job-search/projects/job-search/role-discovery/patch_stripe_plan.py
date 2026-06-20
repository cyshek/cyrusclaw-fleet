#!/usr/bin/env python3
import json

with open('output/inline-plan-stripe-7923047.json') as f:\n    plan = json.load(f)\n\n# Update URL to embed URL (renders standard GH form, not stripe.com wrapper)\nplan['url'] = 'https://job-boards.greenhouse.io/embed/job_app?for=stripe&token=7923047'

# Add missing dropdowns
existing_ids = {d['id'] for d in plan['dropdowns']}
if 'question_66834369' not in existing_ids:
    plan['dropdowns'].append({'id': 'question_66834369', 'label': 'United States'})
if 'question_66834372' not in existing_ids:
    # Remote work option - Kirkland WA is remote from NY
    plan['dropdowns'].append({'id': 'question_66834372', 'label': 'Yes'})

with open('output/inline-plan-stripe-7923047-embed.json', 'w') as f:\n    json.dump(plan, f, indent=2)\n\nprint('Saved embed plan')\nprint('URL:', plan['url'])
print('Dropdowns:', [(d['id'], d['label']) for d in plan['dropdowns']])
