import json

path = 'output/inline-plan-starbridge-3b0bd418-6de0-4cc1-a8fe-7a409238532c.json'
p = json.load(open(path))
answer = ("Coming from a technical PM / solutions background (not a quota-carrying sales seat), "
          "I supported a portfolio of large enterprise accounts -- including Databricks, Walmart, SAP, and NetApp -- "
          "driving $14M+ in value realization across 45+ annual engagements, rather than carrying a fixed ACV book.")

n = 0
for st in p.get('steps', []):
    if st.get('tool') == 'ashby.type_text_fields':
        tf = st['args']['text_fields']
        for k in list(tf):
            if 'da61105c' in k:
                tf[k] = answer
                n += 1

for k in list(p.get('text_fields', {})):
    if 'da61105c' in k:
        p['text_fields'][k] = answer

json.dump(p, open(path, 'w'), indent=1)
print('patched step ACV entries:', n)

p2 = json.load(open(path))
for st in p2['steps']:
    if st.get('tool') == 'ashby.type_text_fields':
        for k, v in st['args']['text_fields'].items():
            if 'da61105c' in k:
                print('STEP ACV now len', len(v), ':', repr(v[:55]))
