#!/usr/bin/env python3
"""
Automated follow-up orchestrator for agency cold outreach.
Called daily by cron. Fully automated: generates, scans for repliers/bounces, excludes
them, sends, and logs. Idempotent (a touch with a sendlog on disk is never re-sent).

Cadence (per batch, measured from touch-1 send date = earliest ts in batchN_sendlog.csv):
  - touch-2  : age in [3, 6] days, if no followup_b{N}_t2_sendlog.csv yet
  - touch-3  : age in [7, 12] days, if t2 already sent and no t3 sendlog yet
Hard ceiling = 3 touches total (touch-1 original + touch-2 + touch-3). Then STOP forever.

Replier/bounce safety: runs scan_replies_followup.py (INBOX+Spam) to build the live
exclude set, marks matching rows "replied": true, and the sender skips them. So anyone
who replied (positive OR negative) or hard-bounced is never followed up.

Prints a concise summary. Exits 0. Designed to be safe to run every day.
"""
import csv, json, os, re, subprocess, sys, glob
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python3"

def log(*a):
    print(*a, flush=True)

def run(cmd, timeout=600):
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=timeout)

def read_exclude_file():
    """Load the CURRENT followup_exclude.json (last-known good). Never raises."""
    ex_path = os.path.join(HERE, "followup_exclude.json")
    if os.path.exists(ex_path):
        try:
            d = json.load(open(ex_path))
            return {a.lower() for a in d.get("exclude", [])}
        except Exception:
            return set()
    return set()

def batch_send_date(sendlog):
    """Earliest SENT timestamp in a sendlog -> touch-1 date (UTC)."""
    ts = []
    with open(sendlog, newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("status") or "").strip().upper() == "SENT" and r.get("timestamp_utc"):
                try:
                    ts.append(datetime.fromisoformat(r["timestamp_utc"]))
                except Exception:
                    pass
    return min(ts) if ts else None

def age_days(dt):
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0

def load_exclude():
    """Refresh the replier/bounce scan, then return (exclude_set, scan_ok, note).

    FAIL-SAFE: if the scan crashes / times out / exits non-zero, we DO NOT treat that as
    'nobody to exclude' and we DO NOT abort the run. We fall back to the last-known
    followup_exclude.json on disk (sticky excludes) and flag scan_ok=False so the caller
    can surface a warning. Missing a freshly-bounced address for one day is far less bad
    than silently skipping a whole in-window batch.
    """
    scan = os.path.join(HERE, "scan_replies_followup.py")
    scan_ok = True
    note = ""
    try:
        r = run([PY, scan], timeout=90)   # fast scan is ~5s; 90s is a generous ceiling
        last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else (r.stderr.strip()[:200] or "(no output)")
        log("  [scan] " + last)
        if r.returncode != 0:
            scan_ok = False
            note = f"scan exit {r.returncode}"
            log(f"  [scan] WARNING: non-zero exit ({r.returncode}); using last-known exclude file.")
    except subprocess.TimeoutExpired:
        scan_ok = False
        note = "scan TIMEOUT"
        log("  [scan] WARNING: scan TIMED OUT; using last-known exclude file (fail-safe).")
    except Exception as e:
        scan_ok = False
        note = f"scan error: {e}"
        log(f"  [scan] WARNING: scan crashed ({e}); using last-known exclude file (fail-safe).")
    exclude = read_exclude_file()
    return exclude, scan_ok, note

def apply_exclude(payload_path, exclude):
    """Mark rows whose 'to' is in exclude as replied:true. Returns (n_total, n_excluded)."""
    rows = json.load(open(payload_path))
    n_ex = 0
    for t in rows:
        if (t.get("to") or "").strip().lower() in exclude:
            t["replied"] = True
            n_ex += 1
    json.dump(rows, open(payload_path, "w"), ensure_ascii=False, indent=2)
    return len(rows), n_ex

def make_followup(sendlog, payload, out, touch):
    cmd = [PY, os.path.join(HERE, "make_followup.py")]
    if touch == 3:
        cmd += ["--touch", "3"]
    cmd += [sendlog, payload, out]
    return run(cmd)

def send_followup(payload, sendlog):
    return run([PY, os.path.join(HERE, "send_followup.py"), payload, sendlog])

def discover_batches():
    """Return list of (batch_id, sendlog_path, payload_path) for batches 1..N."""
    out = []
    for sl in sorted(glob.glob(os.path.join(HERE, "batch*_sendlog.csv"))):
        m = re.search(r"batch(\d+)_sendlog\.csv$", sl)
        if not m:
            continue
        bid = m.group(1)
        payload = os.path.join(HERE, f"batch{bid}_payload.json")
        if os.path.exists(payload):
            out.append((bid, sl, payload))
    return out

def main():
    summary = []
    decisions = []          # explicit per-batch decision lines (EVERY batch, EVERY run)
    batches = discover_batches()
    log(f"Discovered {len(batches)} sent batches: {[b[0] for b in batches]}")

    # Refresh the scan FIRST (scan -> generate -> apply_exclude -> send), fail-safe.
    exclude, scan_ok, scan_note = load_exclude()
    log(f"Exclude set (replied/bounced): {len(exclude)} addresses" + ("" if scan_ok else f"  [SCAN DEGRADED: {scan_note} -> using last-known exclude]"))
    if not scan_ok:
        summary.append(f"SCAN-DEGRADED({scan_note})")

    def decide(bid, verdict, detail=""):
        line = f"batch{bid}: {verdict}" + (f" ({detail})" if detail else "")
        decisions.append(line)
        log("  DECISION -> " + line)

    for bid, sendlog, payload in batches:
        d1 = batch_send_date(sendlog)
        if not d1:
            decide(bid, "SKIP", "no SENT rows in sendlog")
            continue
        age = age_days(d1)
        t2_log = os.path.join(HERE, f"followup_b{bid}_t2_sendlog.csv")
        t3_log = os.path.join(HERE, f"followup_b{bid}_t3_sendlog.csv")
        t2_done = os.path.exists(t2_log)
        t3_done = os.path.exists(t3_log)
        log(f"batch{bid}: touch-1 {d1.date()} | age {age:.2f}d | t2_done={t2_done} t3_done={t3_done}")

        # ---- TOUCH 2 ----
        if t3_done:
            decide(bid, "CEILING-REACHED", "t3 already sent; 3-touch ceiling, stop forever")
            continue
        if not t2_done and age < 3:
            decide(bid, "TOO-YOUNG-FOR-T2", f"age {age:.2f}d < 3d floor")
            continue
        if not t2_done and age > 6:
            decide(bid, "MISSED-T2-WINDOW", f"age {age:.2f}d > 6d; t2 window passed (will consider t3 at 7-12d)")
            # do NOT continue: fall through so a batch past t2 window can still get t3 if eligible
        if not t2_done and 3 <= age <= 6:
            out = os.path.join(HERE, f"followup_b{bid}_t2_payload.json")
            mk = make_followup(sendlog, payload, out, touch=2)
            if mk.returncode != 0 or not os.path.exists(out):
                decide(bid, "T2-GEN-FAIL", (mk.stderr or "")[:160])
                summary.append(f"b{bid} t2 GEN-FAIL")
                continue
            total, n_ex = apply_exclude(out, exclude)
            sd = send_followup(out, t2_log)
            last = sd.stdout.strip().splitlines()[-1] if sd.stdout.strip() else (sd.stderr or "")[:200]
            if sd.returncode != 0 or not os.path.exists(t2_log):
                decide(bid, "T2-SEND-FAIL", last)
                summary.append(f"b{bid} t2 SEND-FAIL")
                continue
            decide(bid, "SENT-T2", f"{total-n_ex} sent / {n_ex} excluded / {total} drafted")
            log(f"  batch{bid} t2: {last}")
            summary.append(f"b{bid} touch-2: {total-n_ex} sent / {n_ex} excluded")
            continue
        # ---- TOUCH 3 (breakup) ----
        if t2_done and not t3_done and age < 7:
            decide(bid, "IDEMPOTENT-T2-DONE", f"t2 sent; age {age:.2f}d < 7d, t3 not due yet")
            continue
        if (t2_done or age > 6) and not t3_done and 7 <= age <= 12:
            out = os.path.join(HERE, f"followup_b{bid}_t3_payload.json")
            mk = make_followup(sendlog, payload, out, touch=3)
            if mk.returncode != 0 or not os.path.exists(out):
                decide(bid, "T3-GEN-FAIL", (mk.stderr or "")[:160])
                summary.append(f"b{bid} t3 GEN-FAIL")
                continue
            total, n_ex = apply_exclude(out, exclude)
            sd = send_followup(out, t3_log)
            last = sd.stdout.strip().splitlines()[-1] if sd.stdout.strip() else (sd.stderr or "")[:200]
            if sd.returncode != 0 or not os.path.exists(t3_log):
                decide(bid, "T3-SEND-FAIL", last)
                summary.append(f"b{bid} t3 SEND-FAIL")
                continue
            decide(bid, "SENT-T3", f"{total-n_ex} sent / {n_ex} excluded / {total} drafted (breakup)")
            log(f"  batch{bid} t3: {last}")
            summary.append(f"b{bid} touch-3: {total-n_ex} sent / {n_ex} excluded")
            continue
        if age > 12:
            decide(bid, "PAST-ALL-WINDOWS", f"age {age:.2f}d > 12d; no further touches")
            continue
        decide(bid, "NOTHING-DUE", f"age {age:.2f}d")

    log("")
    log("PER-BATCH DECISIONS: " + " || ".join(decisions))
    if summary:
        log("FOLLOWUP_SUMMARY: " + " | ".join(summary))
    else:
        status = "nothing due today" + ("" if scan_ok else f" (NOTE: scan degraded: {scan_note})")
        log("FOLLOWUP_SUMMARY: " + status)
if __name__ == "__main__":
    main()
