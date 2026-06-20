import json, re
with open('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/output/inline-plan-thumbtack-20b7b151-75bf-4265-995d-30c081e86b7d.json') as f:\n+    p = json.load(f)\n+\n+for step in p.get('steps', []):
    fn = step.get('args', {}).get('fn', '')
    if 'not listed' in fn.lower():
        print('Found location-not-listed step:')
        idx = fn.lower().find('not listed')
        print(fn[max(0,idx-300):idx+300])
        print('---')
        break

print('Plan keys:', list(p.keys())[:10])
print('Status:', p.get('status'))
print('Plan result:', p.get('plan_result'))
