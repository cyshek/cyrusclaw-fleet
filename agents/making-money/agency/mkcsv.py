import json, csv
sel=json.load(open('selected.json'))
order={'med_spa':0,'personal_injury_law':1,'family_law':2,'hvac':3,'roofing':4}
sel.sort(key=lambda r: order.get(r['vertical'],9))
f=open('prospects.csv','w',newline='',encoding='utf-8')
w=csv.writer(f, quoting=csv.QUOTE_MINIMAL)
w.writerow(['name','vertical','city_state','website','email','phone','personalization_hook'])
for r in sel:
    w.writerow([r['name'], r['vlabel'], r['city_state'], r['website'], r['email_out'], r['phone'], r['hook']])
f.close()
print('wrote', len(sel), 'rows')
