import gmail_imap as g
import json; from pathlib import Path; _email = json.loads((Path(__file__).resolve().parents[1] / "personal-info.json").read_text())["contact"]["email"]
try:
    M = g._connect()
    M.select(b"[Gmail]/All Mail")
    typ, data = M.search(None, "ALL")
    n = len(data[0].split()) if data and data[0] else 0
    print(f"IMAP CONNECT OK {_email} — All Mail count:", n)
    M.logout()
except Exception as e:
    print("IMAP FAIL:", repr(e))
