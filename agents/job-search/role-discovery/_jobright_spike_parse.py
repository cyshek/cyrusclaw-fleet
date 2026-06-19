import re, json, sys

html = open('role-discovery/_jobright_spike_tmp/cat-product.html', encoding='utf-8', errors='replace').read()
m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
if not m:
    print("NO __NEXT_DATA__ found")
    sys.exit(1)
blob = m.group(1)
open('role-discovery/_jobright_spike_tmp/next.json', 'w').write(blob)
print("next.json bytes:", len(blob))
data = json.loads(blob)

def keys(o, depth=0, maxd=3, prefix=''):
    if depth > maxd:
        return
    if isinstance(o, dict):
        for k in list(o.keys())[:40]:
            v = o[k]
            t = type(v).__name__
            ln = (len(v) if isinstance(v, (list, dict, str)) else '')
            print(f"{prefix}{k} :: {t} [{ln}]")
            if isinstance(v, dict) and depth < maxd:
                keys(v, depth + 1, maxd, prefix + '  ')
            if isinstance(v, list) and v and isinstance(v[0], dict) and depth < maxd:
                print(f"{prefix}  [list item0 keys]: {list(v[0].keys())[:30]}")

keys(data)
