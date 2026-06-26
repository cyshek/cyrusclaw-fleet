import subprocess
path = '/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery/natera_v2.py'
with open(path, 'rb') as f:\n+    content = f.read()\n+content_fixed = content.replace(b'as e:\x5c\x6e            print', b'as e:\n            print')\n+with open(path, 'wb') as f:\n+    f.write(content_fixed)\n+r = subprocess.run(['python3', '-m', 'py_compile', path], capture_output=True, text=True)\n+if r.returncode == 0:
    print('Syntax OK')
else:
    print('Error:', r.stderr[:500])
