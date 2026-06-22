import json, os, glob, datetime

sessions_file = os.path.expanduser("~/.openclaw/agents/main/sessions/sessions.json")
sessions_dir = os.path.expanduser("~/.openclaw/agents/main/sessions")

with open(sessions_file) as f:\n    data = json.load(f)\n\nreferenced = set()\nsessions = data.get('sessions', data) if isinstance(data, dict) else data\nfor s in sessions:
    tid = s.get('transcriptId') or s.get('id') or s.get('sessionId', '')
    if tid:
        referenced.add(tid + '.jsonl')

all_jsonl = set(os.path.basename(f) for f in glob.glob(os.path.join(sessions_dir, '*.jsonl')))
all_jsonl = {f for f in all_jsonl if not f.endswith('.lock')}
orphans = all_jsonl - referenced

print(f"Referenced: {len(referenced)}, All jsonl: {len(all_jsonl)}, Orphans: {len(orphans)}")

archive_dir = os.path.join(sessions_dir, f"orphans-{datetime.date.today().strftime('%Y%m%d')}")
os.makedirs(archive_dir, exist_ok=True)
moved = 0
for f in orphans:
    src = os.path.join(sessions_dir, f)
    dst = os.path.join(archive_dir, f)
    os.rename(src, dst)
    moved += 1

print(f"Moved {moved} orphan transcripts to {archive_dir}")
os.system(f"du -sh '{archive_dir}'")
