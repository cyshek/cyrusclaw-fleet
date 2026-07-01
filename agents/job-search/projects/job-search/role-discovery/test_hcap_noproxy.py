import sys, time, os
sys.path.insert(0, '.')

# Remove proxy to use proxyless
proxy_backup = os.environ.pop('PROXY_2CAPTCHA', None)
print('Proxy removed:', proxy_backup is not None)

from captcha_solver import CaptchaSolver
s = CaptchaSolver(vendor='twocaptcha')
print('Balance:', s.get_balance())
print('Starting solve at', time.strftime('%H:%M:%S'))
t = time.time()

try:
    tok = s.solve_hcaptcha('94fee806-5cac-4582-9738-384a0f4ea6f8',
                           'https://careers-amd.icims.com/jobs/87265/login')
    elapsed = time.time() - t
    print('SUCCESS (%.1fs): %s...' % (elapsed, tok[:50]))
except Exception as e:
    elapsed = time.time() - t
    print('FAIL (%.1fs): %s' % (elapsed, e))
