import time, gmail_imap as g
try:
    code = g.wait_for_verification_code(timeout_seconds=3)
    print("wait_for_verification_code returned:", repr(code))
except Exception as e:
    print("FAIL:", repr(e))
