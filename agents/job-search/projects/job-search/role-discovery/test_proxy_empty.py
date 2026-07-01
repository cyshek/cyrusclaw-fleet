import os, sys
os.environ['PROXY_2CAPTCHA'] = 'user:pass@1.2.3.4:8080'
os.environ['TWOCAPTCHA_API_KEY'] = os.environ.get('TWOCAPTCHA_API_KEY', 'fake')
# Set to empty string instead of pop
backup = os.environ.get('PROXY_2CAPTCHA', None)
os.environ['PROXY_2CAPTCHA'] = ''
print('After set-empty, PROXY_2CAPTCHA:', repr(os.environ.get('PROXY_2CAPTCHA')))
sys.path.insert(0, '.')
import twocaptcha_client as tc
client = tc.TwoCaptchaClient()
print('has_proxy:', client.has_proxy)
print('proxy_fields:', client.proxy_fields)
