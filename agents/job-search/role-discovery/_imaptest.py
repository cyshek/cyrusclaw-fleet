import gmail_imap as g
try:
    M = g._connect()
    M.select(b"[Gmail]/All Mail")
    typ, data = M.search(None, "ALL")
    n = len(data[0].split()) if data and data[0] else 0
    print("IMAP CONNECT OK cyshekari@gmail.com — All Mail count:", n)
    M.logout()
except Exception as e:
    print("IMAP FAIL:", repr(e))
