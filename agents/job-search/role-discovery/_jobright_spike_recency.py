import json
data = json.load(open('role-discovery/_jobright_spike_tmp/next.json'))
items = data['props']['pageProps']['defaultData']
print("=== publishTime ordering (first 12) ===")
rows=[]
for it in items:
    j=it['jobResult']; c=it.get('companyResult') or {}
    rows.append((j.get('publishTime') or '', j.get('publishTimeDesc') or '', j.get('jobId') or '', (c.get('companyName') or '')[:22], (j.get('jobTitle') or '')[:40]))
for r in rows[:12]:
    print(f"  {r[0]} | {r[1]:<14} | {r[3]:<22} | {r[4]}")
times=[r[0] for r in rows if r[0]]
print("\nfirst:", times[0], " last:", times[-1], " sorted_desc:", times==sorted(times, reverse=True))
ids=[it['jobResult']['jobId'] for it in items[:6]]
open('role-discovery/_jobright_spike_tmp/sample_ids.txt','w').write("\n".join(ids))
print("sample ids written:", ids)
