import time, gmail_imap as g
try:
    M = g._connect()
    print("LOGIN OK as", g.GMAIL_USER)
    code, ids = g._scan_mailbox(M, "[Gmail]/All Mail", time.time()-86400*7)
    print("scan ok; recent verification code found in last 7d:", code)
    M.logout()
except Exception as e:
    print("FAIL:", repr(e))
