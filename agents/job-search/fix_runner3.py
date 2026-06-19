import sys

path = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/_eightfold_runner.py'

with open(path, 'r') as fh:
    content = fh.read()

lines = content.split('\n')
new_lines = []
for line in lines:
    if 'open(info_path) as f:' in line and 'personal_info = json.load' in line:
        new_lines.append('    with open(info_path) as f:')
        new_lines.append('        personal_info = json.load(f)')
        new_lines.append('')
        new_lines.append('    # Look up apply_url from DB')
        new_lines.append('    db_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "tracker.db"))')
    else:
        new_lines.append(line)

result = '\n'.join(new_lines)
with open(path, 'w') as fh:
    fh.write(result)
print("Done:", len(new_lines), "lines")
