import base64

with open('/home/azureuser/.openclaw/agents/making-money/workspace/outreach/outreach_pipeline.py', 'rb') as f:\n    raw = f.read()\n\n# The broken bytes: literal backslash + n = 0x5c 0x6e (2 bytes)
# Real newline = 0x0a (1 byte)
# Pattern 1: send_email with SMTP_SSL
b1_broken = b'    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:\\n        s.login(GMAIL, APP_PASS)\\n        s.send_message(msg)\\n\\n\\ndef load_results():'
b1_fixed  = base64.b64decode('ICAgIHdpdGggc210cGxpYi5TTVRQX1NTTCgic210cC5nbWFpbC5jb20iLCA0NjUpIGFzIHM6CiAgICAgICAgcy5sb2dpbihHTUFJTCwgQVBQX1BBU1MpCiAgICAgICAgcy5zZW5kX21lc3NhZ2UobXNnKQoKCmRlZiBsb2FkX3Jlc3VsdHMoKTo=')

# Pattern 2: save_results with json.dump
b2_broken = b'    with open(RESULTS_FILE, "w") as f:\\n        json.dump(results, f, indent=2)\\n\\n\\ndef get_sent_set(results, field="email"):'
b2_fixed  = base64.b64decode('ICAgIHdpdGggb3BlbihSRVNVTFRTX0ZJTEUsICJ3IikgYXMgZjoKICAgICAgICBqc29uLmR1bXAocmVzdWx0cywgZiwgaW5kZW50PTIpCgoKZGVmIGdldF9zZW50X3NldChyZXN1bHRzLCBmaWVsZD0iZW1haWwiKTo=')

print('b1 found:', b1_broken in raw)
print('b2 found:', b2_broken in raw)

if b1_broken in raw:
    raw = raw.replace(b1_broken, b1_fixed)
    print('Fixed b1')
if b2_broken in raw:
    raw = raw.replace(b2_broken, b2_fixed)
    print('Fixed b2')

with open('/home/azureuser/.openclaw/agents/making-money/workspace/outreach/outreach_pipeline.py', 'wb') as f:\n    f.write(raw)\nprint('Done')\n