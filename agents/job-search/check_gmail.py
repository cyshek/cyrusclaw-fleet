import imaplib, email, time

pw = open('/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/.gmail-app-password').read().strip()

M = imaplib.IMAP4_SSL('imap.gmail.com', 993)
M.login('cyshekari@gmail.com', pw)

# Check ALL MAIL going back 3 days for anything from icims/auth0
for folder in ['[Gmail]/All Mail', '[Gmail]/Spam', 'INBOX', 'Job-Noise/Codes', 'Job-Noise/Receipts']:
    try:
        M.select(folder, readonly=True)
        typ, data = M.search(None, 'SINCE 29-Jun-2026')
        ids = data[0].split() if data and data[0] else []
        print(f"\n=== {folder}: {len(ids)} messages ===")
        for msg_id in ids[-80:]:  # last 80
            typ, md = M.fetch(msg_id, '(RFC822.HEADER)')
            if typ != 'OK':
                continue
            msg = email.message_from_bytes(md[0][1])
            frm = msg.get('From', '')
            subj = msg.get('Subject', '')
            dt = msg.get('Date', '')
            if any(kw in frm.lower() or kw in subj.lower() for kw in ['icims','auth0','keysight','reset','password','verify','activate']):
                print(f"  MATCH: [{dt[-20:]}] From={frm[:60]} Subj={subj[:80]}")
    except Exception as e:
        print(f"  Error {folder}: {e}")

M.logout()
print("\nDone.")
