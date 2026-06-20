#!/usr/bin/env python3
"""
gmail_sort_applications.py — move job-application emails out of the inbox into a
dedicated Gmail label/folder so Cyrus doesn't miss important non-job mail.

Cyrus directive (2026-06-02): "For the emails confirming we applied and the
one-time-code emails, move these to a separate folder in my inbox."

Two classes moved:
  - APPLICATION CONFIRMATIONS ("application received/submitted", "thank you for
    applying", recruiter acks) from ATS / careers senders.
  - ONE-TIME CODES / OTP ("verification code", "security code") from ATS senders.

Target label: "Job Applications" (created if missing). In Gmail, moving = COPY
to the label + remove the \\Inbox flag (the message stays under that label,
leaves the inbox). We DO NOT delete anything.

SAFETY:
  - Conservative matchers (sender-domain OR strong subject pattern) to avoid
    sweeping real recruiter conversations Cyrus wants to see. By default it only
    moves messages that match an ATS/automated sender OR an unambiguous OTP/
    confirmation subject. Tune with --aggressive (subject-only matches too).
  - --dry-run (DEFAULT) prints what WOULD move, touches nothing.
  - --apply actually moves. --since-days N limits scope (default 9999 = all).
  - Never deletes; only relabels + de-inboxes.

Usage:
  python3 gmail_sort_applications.py                 # dry-run, all inbox
  python3 gmail_sort_applications.py --apply         # move (one-time backfill)
  python3 gmail_sort_applications.py --apply --since-days 7   # ongoing sweep
"""
from __future__ import annotations
import argparse, email, imaplib, pathlib, re, ssl, sys, time
from email.header import decode_header

ROOT = pathlib.Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search")
PW_FILE = ROOT / ".gmail-app-password"
GMAIL_USER = "cyshekari@gmail.com"
IMAP_HOST, IMAP_PORT = "imap.gmail.com", 993
LABEL = "Job Applications"

# Automated ATS / careers sender domains (high-precision: these are not personal mail).
ATS_SENDER = re.compile(
    r"greenhouse-mail|greenhouse\.io|ashbyhq|hi\.ashbyhq|lever\.co|jobs-noreply|"
    r"myworkday|@.*\.workday|smartrecruiters|icims|jobvite|successfactors|taleo|"
    r"eightfold|bamboohr|workable|breezy|teamtailor|rippling|gem\.com|"
    r"no-?reply.*(jobs|careers|talent|recruit)|(jobs|careers|talent|recruiting)@",
    re.I)

# Unambiguous OTP / one-time-code subjects.
OTP_SUBJ = re.compile(
    r"verification code|security code|one[\s-]?time (code|pass)|\bOTP\b|"
    r"confirm your identity|your .*code is|code to (confirm|verify|complete)", re.I)

# Application-confirmation subjects (acknowledgements of a submitted application).
CONF_SUBJ = re.compile(
    r"application (was )?(received|submitted|complete)|thank you for (applying|your application|your interest)|"
    r"we(’| ha)?ve received your application|your application (to|for|has been)|"
    r"received your application|application confirmation|regarding your application", re.I)


def dh(s) -> str:
    return "".join((t.decode(e or "utf-8", "ignore") if isinstance(t, bytes) else t)
                   for t, e in decode_header(s or ""))


def load_pw() -> str:
    return PW_FILE.read_text().strip().replace(" ", "")


def ensure_label(M: imaplib.IMAP4_SSL) -> None:
    typ, boxes = M.list()
    have = any(LABEL in b.decode() for b in (boxes or []))
    if not have:
        M.create(f'"{LABEL}"')
        print(f"[label] created '{LABEL}'")


def classify(subj: str, frm: str, aggressive: bool) -> str | None:
    f = frm.lower()
    ats = bool(ATS_SENDER.search(f))
    if OTP_SUBJ.search(subj):
        # OTP only when from an automated/ATS sender (or aggressive) — avoid
        # moving a human email that merely says "code".
        if ats or aggressive:
            return "otp"
    if CONF_SUBJ.search(subj):
        if ats or aggressive:
            return "confirmation"
    # ATS sender with application-ish subject even if pattern above missed
    if ats and re.search(r"applicat|apply|candidat|interview|role|position", subj, re.I):
        return "ats"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually move (default dry-run)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--aggressive", action="store_true",
                    help="also move subject-only matches (not just ATS senders)")
    ap.add_argument("--since-days", type=int, default=9999)
    ap.add_argument("--max", type=int, default=5000)
    args = ap.parse_args()
    do_apply = args.apply and not args.dry_run

    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, ssl_context=ssl.create_default_context())
    M.login(GMAIL_USER, load_pw())
    if do_apply:
        ensure_label(M)
    M.select("INBOX")

    crit = "ALL"
    if args.since_days < 9999:
        since = time.strftime("%d-%b-%Y", time.gmtime(time.time() - args.since_days * 86400))
        crit = f'(SINCE {since})'
    typ, data = M.search(None, crit)
    ids = data[0].split()[-args.max:]
    print(f"scanning {len(ids)} inbox messages (crit={crit}), apply={do_apply}, aggressive={args.aggressive}")

    moved = {"otp": 0, "confirmation": 0, "ats": 0}
    to_move = []
    # Batch-fetch headers in one round-trip per chunk (per-message fetch is ~100x
    # slower over IMAP). Gmail accepts comma-separated id sets.
    CHUNK = 200
    id_list = [x.decode() for x in ids]
    for c in range(0, len(id_list), CHUNK):
        chunk = id_list[c:c + CHUNK]
        typ, d = M.fetch(",".join(chunk), "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
        # d alternates: (b'<id> (BODY...', b'<headers>'), b')', ...
        cur_id = None
        for part in d:
            if isinstance(part, tuple) and len(part) == 2:
                meta = part[0].decode("utf-8", "ignore")
                m = re.match(r"\s*(\d+)", meta)
                cur_id = m.group(1) if m else None
                msg = email.message_from_string(part[1].decode("utf-8", "ignore"))
                subj, frm = dh(msg.get("Subject")), dh(msg.get("From"))
                kind = classify(subj, frm, args.aggressive)
                if kind and cur_id:
                    to_move.append((cur_id, kind, subj, frm))
                    moved[kind] += 1

    print(f"matched {len(to_move)}: OTP={moved['otp']} confirmations={moved['confirmation']} ats={moved['ats']}")
    for i, kind, subj, frm in to_move[:25]:
        print(f"  [{kind}] {subj[:58]!r} <- {frm[:40]}")
    if len(to_move) > 25:
        print(f"  ... +{len(to_move)-25} more")

    if not do_apply:
        print("DRY-RUN — nothing moved. Re-run with --apply to move.")
        M.logout(); return 0

    n = 0
    for i, kind, subj, frm in to_move:
        try:
            M.copy(i, f'"{LABEL}"')               # add to label
            M.store(i, "+FLAGS", "\\Deleted")      # remove from INBOX
            n += 1
        except Exception as e:
            print(f"  move-fail id={i}: {e}")
    M.expunge()
    print(f"MOVED {n} message(s) to '{LABEL}' and out of inbox.")
    M.logout()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
