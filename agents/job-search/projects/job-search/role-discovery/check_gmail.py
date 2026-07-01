import imaplib, email as em, sys, re
sys.path.insert(0, ".")
from gmail_imap import _connect
M = _connect()

_, mboxes = M.list()
print("Mailboxes with jobs/icims:")
for mb in mboxes:
    mb_str = mb.decode()
    if any(k in mb_str.lower() for k in ["icims", "jobs", "keysight", "noise", "code"]):
        print(" ", mb_str)

M.select("INBOX")
_, data = M.search(None, "SINCE", "01-Jul-2026")
print(f"INBOX today: {len(data[0].split())} msgs")
for mid in reversed(data[0].split()):
    _, mdata = M.fetch(mid, "(RFC822)")
    msg = em.message_from_bytes(mdata[0][1])
    print(f"  {msg.get(chr(68)+chr(97)+chr(116)+chr(101),chr(32)*22)[:22]} {msg.get(chr(70)+chr(114)+chr(111)+chr(109),"")[:50]} | {msg.get(chr(83)+chr(117)+chr(98)+chr(106)+chr(101)+chr(99)+chr(116),"")[:40]}")

M.logout()
