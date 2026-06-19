import json
data = json.load(open('role-discovery/_jobright_spike_tmp/next.json'))
items = data['props']['pageProps']['defaultData']
print("num job items:", len(items))
j0 = items[0]['jobResult']
c0 = items[0]['companyResult']
print("\n=== jobResult keys ===")
for k in sorted(j0.keys()):
    v=j0[k]; t=type(v).__name__
    sample = (str(v)[:70]) if not isinstance(v,(dict,list)) else f"<{t} len {len(v)}>"
    print(f"  {k} :: {t} = {sample}")
print("\n=== companyResult keys ===")
for k in sorted(c0.keys()):
    v=c0[k]; t=type(v).__name__
    sample = (str(v)[:60]) if not isinstance(v,(dict,list)) else f"<{t} len {len(v)}>"
    print(f"  {k} :: {t} = {sample}")
