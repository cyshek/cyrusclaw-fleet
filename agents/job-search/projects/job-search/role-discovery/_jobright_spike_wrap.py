import re, json, sys
html=open('role-discovery/_jobright_spike_tmp/wrap.html',encoding='utf-8',errors='replace').read()
m=re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
if not m:
    print('no next_data in wrapper')
    sys.exit(0)
d=json.loads(m.group(1))
open('role-discovery/_jobright_spike_tmp/wrap.json','w').write(m.group(1))
pp=d.get('props',{}).get('pageProps',{})
print('pageProps keys:', list(pp.keys()))
def find_urls(o, path=''):
    out=[]
    if isinstance(o,dict):
        for k,v in o.items():
            if isinstance(v,str) and ('http' in v) and ('jobright.ai' not in v) and any(s in v.lower() for s in ['apply','greenhouse','lever','ashby','workday','smartrecruiters','icims','workable','career','recruit','boards']):
                out.append((path+'/'+k, v[:120]))
            out+=find_urls(v, path+'/'+k)
    elif isinstance(o,list):
        for i,v in enumerate(o[:5]):
            out+=find_urls(v, '%s[%d]'%(path,i))
    return out
urls=find_urls(pp)
print('=== candidate external ATS/apply URLs in wrapper JSON ===')
for p,u in urls[:25]:
    print(' ', p, '=', u)
def find_urlkeys(o, path=''):
    out=[]
    if isinstance(o,dict):
        for k,v in o.items():
            if isinstance(v,str) and ('url' in k.lower() or 'link' in k.lower() or 'apply' in k.lower()):
                out.append((path+'/'+k, v[:110]))
            out+=find_urlkeys(v, path+'/'+k)
    elif isinstance(o,list):
        for i,v in enumerate(o[:3]):
            out+=find_urlkeys(v, '%s[%d]'%(path,i))
    return out
print('=== all url/link/apply-named fields ===')
for p,u in find_urlkeys(pp)[:30]:
    print(' ', p, '=', u)
