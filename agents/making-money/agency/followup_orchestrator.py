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

def run(cmd):
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, timeout=600)

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
    """Run the replier/bounce scan; return set of lowercase addresses to exclude."""
    scan = os.path.join(HERE, "scan_replies_followup.py")
    r = run([PY, scan])
    log("  [scan] " + (r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()[:200]))
    ex_path = os.path.join(HERE, "followup_exclude.json")
    if os.path.exists(ex_path):
        try:
            d = json.load(open(ex_path))
            return {a.lower() for a in d.get("exclude", [])}
        except Exception:
            return set()
    return set()

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
    batches = discover_batches()
    log(f"Discovered {len(batches)} sent batches: {[b[0] for b in batches]}")

    # Build the live exclude set ONCE (covers all batches).
    exclude = load_exclude()
    log(f"Exclude set (replied/bounced): {len(exclude)} addresses")

    for bid, sendlog, payload in batches:
        d1 = batch_send_date(sendlog)
        if not d1:
            log(f"batch{bid}: no SENT rows, skip")
            continue
        age = age_days(d1)
        t2_log = os.path.join(HERE, f"followup_b{bid}_t2_sendlog.csv")
        t3_log = os.path.join(HERE, f"followup_b{bid}_t3_sendlog.csv")
        t2_done = os.path.exists(t2_log)
        t3_done = os.path.exists(t3_log)
        log(f"batch{bid}: touch-1 {d1.date()} | age {age:.1f}d | t2_done={t2_done} t3_done={t3_done}")

        # ---- TOUCH 2 ----
        if not t2_done and 3 <= age <= 6:
            out = os.path.join(HERE, f"followup_b{bid}_t2_payload.json")
            mk = make_followup(sendlog, payload, out, touch=2)
            if mk.returncode != 0 or not os.path.exists(out):
                log(f"  batch{bid} t2: generate FAILED: {mk.stderr[:200]}")
                summary.append(f"b{bid} t2 GEN-FAIL")
                continue
            total, n_ex = apply_exclude(out, exclude)
            sd = send_followup(out, t2_log)
            last = sd.stdout.strip().splitlines()[-1] if sd.stdout.strip() else sd.stderr[:200]
            log(f"  batch{bid} t2 SENT ({total} drafted, {n_ex} excluded): {last}")
            summary.append(f"b{bid} touch-2: {total-n_ex} sent / {n_ex} excluded")
        # ---- TOUCH 3 ----
        elif t2_done and not t3_done and 7 <= age <= 12:
            out = os.path.join(HERE, f"followup_b{bid}_t3_payload.json")
            mk = make_followup(sendlog, payload, out, touch=3)
            if mk.returncode != 0 or not os.path.exists(out):
                log(f"  batch{bid} t3: generate FAILED: {mk.stderr[:200]}")
                summary.append(f"b{bid} t3 GEN-FAIL")
                continue
            total, n_ex = apply_exclude(out, exclude)
            sd = send_followup(out, t3_log)
            last = sd.stdout.strip().splitlines()[-1] if sd.stdout.strip() else sd.stderr[:200]
            log(f"  batch{bid} t3 (breakup) SENT ({total} drafted, {n_ex} excluded): {last}")
            summary.append(f"b{bid} touch-3: {total-n_ex} sent / {n_ex} excluded")
        else:
            log(f"  batch{bid}: nothing due")

    log("")
    if summary:
        log("FOLLOWUP_SUMMARY: " + " | ".join(summary))
    else:
        log("FOLLOWUP_SUMMARY: nothing due today")

if __name__ == "__main__":
    main()
