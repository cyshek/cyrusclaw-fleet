import sys, time
sys.path.insert(0, '.')
from captcha_solver import CaptchaSolver

s = CaptchaSolver(vendor='twocaptcha')
print('Balance:', s.get_balance())

t = time.time()
try:
    tok = s.solve_hcaptcha('94fee806-5cac-4582-9738-384a0f4ea6f8', 
                           'https://careers-amd.icims.com/jobs/87265/login')
    elapsed = time.time() - t
    print('Token OK (%.1fs)' % elapsed)
    print(tok[:80])
except Exception as e:\n    elapsed = time.time() - t\n    print('Error (%.1fs): %s' % (elapsed, e))
