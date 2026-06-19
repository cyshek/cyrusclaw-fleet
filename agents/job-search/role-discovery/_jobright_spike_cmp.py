import re,json
for f,name in [('role-discovery/_jobright_spike_tmp/cat-product.html','product-design'),('role-discovery/_jobright_spike_tmp/cat2.html','sales-bd')]:
    h=open(f,encoding='utf-8',errors='replace').read()
    m=re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',h,re.S)
    if not m:
        print(name,'NO_DATA'); continue
    d=json.loads(m.group(1))
    items=d['props']['pageProps'].get('defaultData',[])
    times=[it['jobResult'].get('publishTime') for it in items if it.get('jobResult')]
    hosts=set()
    for it in items:
        al=it['jobResult'].get('applyLink','')
        hosts.add(al.split('/')[2] if '://' in al else al[:20])
    print('%s: %d jobs | newest=%s | oldest=%s | applyLink_hosts=%s'%(name,len(items),times[0] if times else '-',times[-1] if times else '-',hosts))
