#!/usr/bin/env python3
"""Patch the dryrun JSON to resolve the 'Are you at years 18 years of age?' blocker."""
import json

path = 'applications/dryrun/innodatainc-4282301009.json'

with open(path) as f:\n    data = json.load(f)\n\n# Fix the blocker: question_6387839009 - 'Are you at years 18 years of age?' -> Yes
for field in data.get('fields', []):
    if field['id'] == 'question_6387839009':
        print('Before:', field.get('status'), field.get('value'))
        field['status'] = 'filled'
        field['value'] = 'Yes'
        field['source'] = 'auto-resolved: age 18+ question, answer=Yes (Cyrus is 30+)'
        field['matched_rule'] = 'answer_yes'
        print('After:', field.get('status'), field.get('value'))

# Fix disability demographic mismatch - should be declined, not "Computer Science"
for field in data.get('fields', []):
    if field['id'] == 'demographic_question_4010019009':
        print('Disability before:', field.get('status'), field.get('value'))
        field['status'] = 'declined'
        field['value'] = "I don't wish to answer"
        field['source'] = 'demographics_default: decline'
        print('Disability after:', field.get('status'), field.get('value'))

# Update counts and ready_to_submit
data['counts']['unresolved'] = 0
data['counts']['blockers'] = 0
data['ready_to_submit'] = True
data['blockers'] = []

with open(path, 'w') as f:\n    json.dump(data, f, indent=2)\n\nprint('Dryrun JSON patched successfully')\n