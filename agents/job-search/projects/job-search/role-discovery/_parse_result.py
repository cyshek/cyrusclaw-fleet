import re, json
log = open('/tmp/run_1555.log').read()
i = log.rfind(chr(10) + '{')
obj = log[i:] if i >= 0 else log
try:
    d = json.loads(obj.strip())
    print('ok:', d.get('ok'))
    print('classify:', d.get('classify'))
    print('submit_success:', d.get('submit_success'))
    print('app_url:', d.get('app_url') or d.get('application_url'))
    print('confirmation:', d.get('confirmation') or d.get('confirmation_text'))
except Exception as e:
    print('parse fail:', e)
    m = re.findall(r'"app_url":\s*"([^"]+)"', log)
    print('app_url matches:', m[-3:] if m else 'none')
    cl = re.findall(r'"classify":\s*"([^"]+)"', log)
    print('classify matches:', cl[-2:] if cl else 'none')
