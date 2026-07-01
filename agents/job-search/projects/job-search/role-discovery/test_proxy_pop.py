import os
os.environ['PROXY_2CAPTCHA'] = 'test:test@1.2.3.4:8080'
os.environ['TWOCAPTCHA_API_KEY'] = 'fake'
backup = os.environ.pop('PROXY_2CAPTCHA', None)
print('After pop, PROXY_2CAPTCHA in env:', 'PROXY_2CAPTCHA' in os.environ)
print('backup:', backup[:10])
import sys
sys.path.insert(0, '.')
import twocaptcha_client as tc
client = tc.TwoCaptchaClient()
print('has_proxy:', client.has_proxy)
print('proxy_fields:', client.proxy_fields)
