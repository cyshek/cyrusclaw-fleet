import sys, os
sys.path.insert(0, '.')
from captcha_solver import CaptchaSolver

print('Solving hcaptcha via 2captcha...', flush=True)
tok = CaptchaSolver(vendor='twocaptcha').solve_hcaptcha(
    'e33f87f8-88ec-4e1a-9a13-df9bbb1d8120',
    'https://jobs.lever.co/veeva/6bcc8228-5b43-43e5-b96b-d62679b8c64a/apply',
    is_invisible=True,
    user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36'
)
print(f'Token len: {len(tok)}', flush=True)
print(f'Token: {tok}', flush=True)
