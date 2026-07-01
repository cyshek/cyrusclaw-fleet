fname = '_icims_runner.py'
with open(fname) as f:
    lines = f.readlines()
# Find the proxy_backup line and fix it
for i, ln in enumerate(lines):
    if '_proxy_backup = os.environ.pop' in ln:
        print(f'Found at line {i+1}: {repr(ln.rstrip())}')
        lines[i] = '    _proxy_backup = os.environ.get("PROXY_2CAPTCHA", None)\n'
        lines.insert(i+1, '    os.environ["PROXY_2CAPTCHA"] = ""  # proxyless: empty string prevents .env reload injecting proxy\n')
        print('Patched')
        break
# Fix the finally block too
for i, ln in enumerate(lines):
    if 'if _proxy_backup is not None:' in ln and i > 750:
        print(f'Found finally at line {i+1}: {repr(ln.rstrip())}')
        break
with open(fname, 'w') as f:
    f.writelines(lines)
print(f'Written {len(lines)} lines')
