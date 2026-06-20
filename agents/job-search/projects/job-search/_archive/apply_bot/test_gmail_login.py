"""
Smoke test for Gmail IMAP credentials.

Run after dropping creds at assets/.gmail_credentials:
    python test_gmail_login.py

Connect-only -- does NOT submit any applications. Confirms the App Password
works and the inbox is reachable.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from gmail_otp import GmailOtpPoller, CRED_PATH


def main() -> int:
    if not CRED_PATH.exists():
        print(f"[FAIL] No credentials file at {CRED_PATH}")
        print("       Create it with two lines: <gmail address> then <app password>")
        return 1

    try:
        poller = GmailOtpPoller()
    except Exception as e:
        print(f"[FAIL] Could not load credentials: {e}")
        return 1

    print(f"[OK]   Loaded creds for {poller.email_addr}")

    try:
        conn = poller._connect()
    except Exception as e:
        print(f"[FAIL] IMAP login failed: {e}")
        print("       Check the App Password is exactly 16 chars (no spaces) and 2FA is on.")
        return 1

    print("[OK]   IMAP4_SSL login succeeded")

    try:
        status, data = conn.select("INBOX")
        if status != "OK":
            print(f"[FAIL] Could not SELECT INBOX: {status} {data}")
            return 1
        count = int(data[0]) if data and data[0] else 0
        print(f"[OK]   INBOX selected -- {count} messages visible")
    finally:
        try:
            conn.logout()
        except Exception:
            pass

    print()
    print("All checks passed. Ready to run:")
    print('  python apply.py --url "<greenhouse url>" --live --gmail-imap')
    return 0


if __name__ == "__main__":
    sys.exit(main())
