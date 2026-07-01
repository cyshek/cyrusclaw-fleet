import os, sys
sys.path.insert(0, '.')
# Set to empty string to block proxy injection
proxy_backup = os.environ.get('PROXY_2CAPTCHA', None)
os.environ['PROXY_2CAPTCHA'] = ''
from captcha_solver import CaptchaSolver
s = CaptchaSolver(vendor='twocaptcha')
# Access internal client
tc = s._twocaptcha_client()
print('has_proxy:', tc.has_proxy)
print('proxy_fields:', tc.proxy_fields)
if proxy_backup:
    os.environ['PROXY_2CAPTCHA'] = proxy_backup
