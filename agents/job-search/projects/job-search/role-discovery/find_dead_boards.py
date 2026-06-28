import yaml

with open('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/companies.yaml') as f:\n    data = yaml.safe_load(f)\ncompanies = data.get('companies', [])\n\ndead_boards = {\n    'ashby': {'abundant', 'cascade', 'datacurve', 'doe', 'forge', 'handoff', 'harper', 'luma'},
    'greenhouse': {'credera', 'interfaceai', 'latentai', 'materialize', 'snackpass', 'vitablehealth'}
}

found = []
for c in companies:
    boards = c.get('boards', {})
    for ats, ids in dead_boards.items():
        board_val = boards.get(ats)
        if isinstance(board_val, str) and board_val in ids:
            found.append((c.get('name'), ats, board_val))
        elif isinstance(board_val, list):
            for b in board_val:
                if isinstance(b, str) and b in ids:
                    found.append((c.get('name'), ats, b))

print(f'Found {len(found)} dead board entries:')
for name, ats, board in found:
    print(f'  {name}: {ats}[{board}]')
