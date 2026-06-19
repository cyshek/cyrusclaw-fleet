#!/usr/bin/env python3
"""
silent-session-watchdog.py — auto-recover wedged/bloated OpenClaw sessions so agents
(and :main itself) stop going silent, and ONLY alert the user when auto-recovery FAILS.

Supersedes session-ceiling-guard.py (which only FLAGGED compactionCount>=15). This
watchdog detects the three silence-causing failure modes seen on 2026-06-05 and
auto-recovers them with the proven-safe method (archive transcript + clear index entry;
the gateway rebuilds a clean session on the next inbound message). It NEVER restarts the
gateway (restarting under load corrupts MORE sessions -- the big lesson that day), NEVER
deletes (only MOVES, recoverable), and NEVER touches the agent workspace / MEMORY.md /
memory/* (durable memory is separate from session state).

FAILURE MODES HANDLED
  1. WEDGED/FAILED   - index status in {failed, timeout, error, crashed, aborted, errored}.
                       The session is in a terminal-error state; recover.
  2. STALE-LOCK      - a <sessionId>.jsonl.lock exists AND (holder pid is dead via
                       kill -0) OR (pid == live gateway MainPID AND lock age > maxHoldMs).
                       A leaked lock makes every inbound message time out with
                       SessionWriteLockTimeoutError. Recover (and move the lock aside).
  3. HIGH-COMPACTION - compactionCount >= COMPACTION_THRESHOLD *and ALSO stale*
                       (updatedAt older than STALE_MIN). Proactively recycles a bloated
                       long-lived session BEFORE it wedges. NOT applied to subagent/cron
                       keys (their churn is normal) and NOT applied to mid-active turns.

KEY FACTS (verified 2026-06-05)
  - sessions.json is { sessionKey -> entry }. entry has: sessionId, status, updatedAt
    (epoch ms), compactionCount (often null), contextTokens (= static window size, e.g.
    128000/200000 -- NOT live fill, useless as a pressure signal; IGNORED here).
  - status=="done" is the NORMAL idle terminal state -- NOT a failure. Never recovered.
  - status=="running" means an in-flight turn. Never recovered (even if updatedAt is
    stale -- a stale 'running' is left as an OBSERVE note, not auto-reset, because we
    can't safely tell "crashed mid-turn" from "long turn" without risking a live turn).
  - lock file schema: {pid, createdAt (ISO), maxHoldMs, starttime (linux jiffies)}.
    starttime lets us guard against PID reuse: a pid is "the same process" only if its
    /proc/<pid>/stat starttime matches the recorded one.
  - Transcript files for a sessionId: <sid>.jsonl, <sid>.trajectory.jsonl,
    <sid>.trajectory-path.json, and any other <sid>* files (checkpoints). Some failed
    entries have NO transcript files at all -- that's fine, just clear the index entry.

SAFETY INVARIANTS
  - Backup sessions.json (timestamped) to _session_backups/ before any write.
  - Atomic write: tempfile in same dir + os.replace; then re-parse to validate.
  - MOVE broken transcript files into _session_backups/recovered-<ts>/<agent>/ (never rm).
  - 90s mid-write guard: skip any entry touched in the last MIN_WRITE_GUARD_S, EXCEPT a
    lock whose holder pid is provably DEAD (safe to reap immediately).
  - Idempotent: safe to run every 10-15 min. Clearing an already-clean index is a no-op.

OUTPUT / EXIT
  - Always exit 0.
  - Prints a structured per-action log + a summary.
  - If it recovered >=1 session: prints a line starting "RECOVERED:".
  - If it found a problem it could NOT safely auto-recover: prints a line starting
    "ESCALATE:" (this is the ONLY condition the cron should surface to the user).
  - Clean OR all-auto-recovered  => no ESCALATE line => cron stays silent (NO_REPLY).

FLAGS
  --dry-run   detect + print what it WOULD do; makes ZERO writes/moves.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime

# ----------------------------------------------------------------------------- config
OPENCLAW_ROOT = "/home/azureuser/.openclaw"
AGENTS_ROOT = os.path.join(OPENCLAW_ROOT, "agents")
BACKUP_ROOT = os.path.join(OPENCLAW_ROOT, "_session_backups")
STAMP_DIR = os.path.join(OPENCLAW_ROOT, "var", "silent-session-watchdog")

# status values that mean "terminal error -> recover". 'done' and 'running' are NOT here.
FAILED_STATUSES = {"failed", "timeout", "error", "crashed", "aborted", "errored"}

COMPACTION_THRESHOLD = 18        # proactive recycle at/above this (chronic grinders hit 20-22)
STALE_MIN = 20                   # "not mid-active-turn" if updatedAt older than this many minutes
STALE_S = STALE_MIN * 60
MIN_WRITE_GUARD_S = 90           # never touch an entry written this recently (except dead-pid locks)

NOW_MS = int(time.time() * 1000)


# ----------------------------------------------------------------------------- helpers
def ts_slug():
    return datetime.now().strftime("%Y%m%dT%H%M%S")


def parse_ts_ms(v):
    """Return epoch-ms for an updatedAt-like field, or None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 1e12 else float(v) * 1000.0
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp() * 1000.0
        except Exception:
            return None
    return None


def gateway_main_pid():
    """Live gateway MainPID via systemd; 0 if unknown."""
    try:
        out = subprocess.run(
            ["systemctl", "--user", "show", "openclaw-gateway.service", "-p", "MainPID", "--value"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        return int(out) if out.isdigit() else 0
    except Exception:
        return 0


def pid_alive(pid):
    """True if pid is alive (kill -0 semantics)."""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but owned by another user
    except Exception:
        return False


def proc_starttime(pid):
    """Field 22 (starttime, clock ticks) from /proc/<pid>/stat, or None."""
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            data = f.read()
        rest = data[data.rfind(")") + 1:].split()  # safe past a comm with spaces/parens
        # rest[0] == 'state' (field 3); starttime is field 22 -> index 19
        return int(rest[19])
    except Exception:
        return None


def lock_holder_dead(lock):
    """
    True if the lock's holder process is gone (safe to reap immediately). Uses pid +
    starttime to defend against PID reuse: alive only if pid is alive AND (no recorded
    starttime OR recorded starttime matches the live process).
    """
    pid = lock.get("pid")
    if not isinstance(pid, int):
        return False  # unknown holder -- do NOT assume dead
    if not pid_alive(pid):
        return True
    rec_start = lock.get("starttime")
    if isinstance(rec_start, int):
        live_start = proc_starttime(pid)
        if live_start is not None and live_start != rec_start:
            return True  # pid reused -> original holder is dead
    return False


def lock_age_ms(lock, lock_path):
    """Age from createdAt if parseable, else from file mtime."""
    created = parse_ts_ms(lock.get("createdAt"))
    if created is not None:
        return NOW_MS - created
    try:
        return NOW_MS - int(os.path.getmtime(lock_path) * 1000)
    except Exception:
        return None


def transcript_files(sessions_dir, sid):
    """All on-disk files for a sessionId (transcript, trajectory, checkpoints, lock)."""
    if not sid:
        return []
    out = []
    for suf in (".jsonl", ".trajectory.jsonl", ".trajectory-path.json", ".jsonl.lock"):
        p = os.path.join(sessions_dir, sid + suf)
        if os.path.exists(p):
            out.append(p)
    for p in glob.glob(os.path.join(sessions_dir, sid + "*")):
        if p not in out and os.path.isfile(p):
            out.append(p)
    return out


def is_churny_key(key):
    return (":subagent:" in key) or (":cron:" in key) or (":explicit:" in key)


# ----------------------------------------------------------------------------- core
class Watchdog:
    def __init__(self, dry_run):
        self.dry_run = dry_run
        self.gw_pid = gateway_main_pid()
        self.recovered = []     # human-readable strings
        self.escalate = []      # human-readable strings (failed auto-recovery -> surface)
        self.observe = []       # non-actioned notes (e.g. stale 'running')
        self.actions_log = []   # structured per-step log

    def log(self, line):
        self.actions_log.append(line)

    # -- atomic index write with backup + validate -------------------------------
    def backup_index(self, sj):
        os.makedirs(BACKUP_ROOT, exist_ok=True)
        agent = sj.split("/")[-3]
        dst = os.path.join(BACKUP_ROOT, f"sessions.{agent}.{ts_slug()}.json")
        if self.dry_run:
            self.log(f"    [dry-run] would back up index -> {dst}")
            return dst
        shutil.copy2(sj, dst)
        self.log(f"    backed up index -> {dst}")
        return dst

    def write_index(self, sj, data):
        """Atomic write + re-parse validation. True on success."""
        if self.dry_run:
            self.log(f"    [dry-run] would atomically rewrite {sj} ({len(data)} entries)")
            return True
        d = os.path.dirname(sj)
        fd, tmp = tempfile.mkstemp(prefix=".sessions.", suffix=".tmp", dir=d)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            with open(tmp, "r") as f:
                json.load(f)  # validate tempfile parses before swap
            os.replace(tmp, sj)
        except Exception as e:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            self.escalate.append(f"index write FAILED for {sj}: {e}")
            self.log(f"    !! index write FAILED ({e}) -- original left untouched")
            return False
        try:
            json.load(open(sj))  # final live re-parse
        except Exception as e:
            self.escalate.append(f"index post-write re-parse FAILED for {sj}: {e}")
            self.log(f"    !! post-write re-parse FAILED ({e})")
            return False
        self.log(f"    rewrote index OK ({len(data)} entries)")
        return True

    def archive_files(self, files, agent, reason_ts):
        """MOVE files into _session_backups/recovered-<ts>/<agent>/. Returns moved basenames."""
        if not files:
            return []
        dest_dir = os.path.join(BACKUP_ROOT, f"recovered-{reason_ts}", agent)
        moved = []
        for src in files:
            base = os.path.basename(src)
            dst = os.path.join(dest_dir, base)
            if self.dry_run:
                self.log(f"    [dry-run] would MOVE {src} -> {dst}")
                moved.append(base)
                continue
            os.makedirs(dest_dir, exist_ok=True)
            try:
                shutil.move(src, dst)
                self.log(f"    moved {base} -> {dst}")
                moved.append(base)
            except Exception as e:
                self.log(f"    !! failed to move {base} ({e})")
        return moved

    def recover_entry(self, sj, agent, key, entry, reason, files_override=None):
        """
        The single safe recovery primitive: backup index, remove the entry, atomically
        write, then move the broken transcript files aside. Used for all three modes.
        """
        sid = entry.get("sessionId")
        sessions_dir = os.path.dirname(sj)
        files = files_override if files_override is not None else transcript_files(sessions_dir, sid)
        self.log(f"  RECOVER [{reason}] agent={agent} key={key} sid={sid}")
        self.log(f"    transcript files: {[os.path.basename(f) for f in files] or 'none'}")

        # read index fresh (may have changed since scan)
        try:
            data = json.load(open(sj))
        except Exception as e:
            self.escalate.append(f"{agent}: sessions.json unreadable at recover time ({e})")
            self.log(f"    !! index unreadable now ({e}) -- aborting this recovery")
            return False
        if key not in data:
            self.log("    entry already gone from index (idempotent no-op)")
            self.archive_files(files, agent, ts_slug())  # still move stray files
            return False

        self.backup_index(sj)
        new_data = {k: v for k, v in data.items() if k != key}
        if not self.write_index(sj, new_data):
            self.log("    !! index write failed -- NOT moving files (keep state consistent)")
            return False
        moved = self.archive_files(files, agent, ts_slug())
        self.recovered.append(
            f"{agent} :: {key} (sid={sid}, reason={reason}, moved={len(moved)} file(s))"
        )
        return True

    # -- per-agent scan ----------------------------------------------------------
    def scan_index(self, sj):
        agent = sj.split("/")[-3]
        sessions_dir = os.path.dirname(sj)
        try:
            data = json.load(open(sj))
        except Exception as e:
            self.escalate.append(f"{agent}: sessions.json UNREADABLE ({e}) -- cannot auto-recover index")
            self.log(f"AGENT {agent}: sessions.json UNREADABLE ({e})")
            return
        if not isinstance(data, dict):
            self.log(f"AGENT {agent}: sessions.json not an object -- skipping")
            return

        # 1) lock pass (a lock can exist for an entry of any status)
        for lock_path in glob.glob(os.path.join(sessions_dir, "*.jsonl.lock")):
            self.handle_lock(sj, agent, data, lock_path)

        # re-read in case a lock recovery mutated the index
        try:
            data = json.load(open(sj))
        except Exception:
            return

        # 2) status + compaction pass
        for key, entry in list(data.items()):
            if not isinstance(entry, dict):
                continue
            status = (entry.get("status") or "").lower()
            comp = entry.get("compactionCount")
            comp = comp if isinstance(comp, (int, float)) else 0
            upd_ms = parse_ts_ms(entry.get("updatedAt"))
            age_s = (NOW_MS - upd_ms) / 1000.0 if upd_ms else None
            fresh = (age_s is not None) and (age_s < MIN_WRITE_GUARD_S)

            # (a) terminal-error status -> recover (unless freshly touched)
            if status in FAILED_STATUSES:
                if fresh:
                    self.observe.append(
                        f"{agent}:{key} status={status} but touched {age_s:.0f}s ago "
                        f"(<{MIN_WRITE_GUARD_S}s) -- deferring to next run")
                    self.log(f"  DEFER failed/young agent={agent} key={key} age={age_s:.0f}s")
                    continue
                self.recover_entry(sj, agent, key, entry, reason=f"status={status}")
                continue

            # (b) stale 'running' -> OBSERVE only (never auto-reset a possibly-live turn)
            if status == "running" and age_s is not None and age_s > STALE_S:
                self.observe.append(
                    f"{agent}:{key} status=running but stale ({age_s/3600:.1f}h since update) -- "
                    f"NOT auto-reset (could be a long turn); watch it")
                continue

            # (c) high-compaction proactive recycle -- long-lived (non-churny) AND stale only
            if comp >= COMPACTION_THRESHOLD and not is_churny_key(key):
                if age_s is None:
                    continue  # no timestamp -> can't confirm not-mid-turn -> skip
                if age_s < STALE_S:
                    self.observe.append(
                        f"{agent}:{key} compactionCount={int(comp)}>={COMPACTION_THRESHOLD} but "
                        f"active ({age_s/60:.0f}m) -- leaving (may be working)")
                    continue
                self.recover_entry(
                    sj, agent, key, entry,
                    reason=f"compaction={int(comp)}>={COMPACTION_THRESHOLD}&stale{age_s/60:.0f}m")
                continue

    # -- lock handling -----------------------------------------------------------
    def handle_lock(self, sj, agent, data, lock_path):
        base = os.path.basename(lock_path)
        m = re.match(r"^(.*)\.jsonl\.lock$", base)
        sid = m.group(1) if m else None
        try:
            lock = json.load(open(lock_path))
        except Exception:
            age = lock_age_ms({}, lock_path)
            if age is not None and age > MIN_WRITE_GUARD_S * 1000:
                self.log(f"  LOCK unparseable+old agent={agent} {base} age={age/1000:.0f}s -> reap")
                self._recover_for_lock(sj, agent, data, sid, lock_path,
                                       reason="unparseable-stale-lock", owning_key=self._owner(data, sid))
            else:
                self.observe.append(f"{agent}: unparseable lock {base} but young -- leaving")
            return

        pid = lock.get("pid")
        maxhold = lock.get("maxHoldMs") or 0
        age = lock_age_ms(lock, lock_path)
        age_s = (age / 1000.0) if age is not None else None
        dead = lock_holder_dead(lock)
        owning_key = self._owner(data, sid)

        if dead:
            # leaked lock -- holder gone. Reap IMMEDIATELY (a dead pid can't be mid-write).
            self.log(f"  LOCK leaked (holder pid={pid} DEAD) agent={agent} {base} "
                     f"age={'?' if age_s is None else f'{age_s:.0f}s'} -> recover")
            self._recover_for_lock(sj, agent, data, sid, lock_path,
                                   reason="stale-lock(dead-pid)", owning_key=owning_key)
            return

        if self.gw_pid and pid == self.gw_pid:
            if age is not None and maxhold and age > maxhold:
                # aged-out past its own maxHoldMs -> recoverable-stale (v1 rule)
                self.log(f"  LOCK gateway-held but AGED OUT agent={agent} {base} "
                         f"age={age_s:.0f}s > maxHoldMs={maxhold/1000:.0f}s -> recover")
                self._recover_for_lock(sj, agent, data, sid, lock_path,
                                       reason="stale-lock(gateway-aged-out)", owning_key=owning_key)
            else:
                # healthy in-flight lock (normal active turn) -- leave it, not an escalation
                self.log(f"  LOCK gateway-held, healthy agent={agent} {base} "
                         f"age={'?' if age_s is None else f'{age_s:.0f}s'} "
                         f"(maxHoldMs={maxhold/1000:.0f}s) -> leave")
            return

        # live, non-gateway holder -- unusual. Don't yank from a live process; escalate
        # only if it persists across two consecutive sightings (stamp-based).
        self._persisting_lock(agent, base, pid, age_s)

    def _owner(self, data, sid):
        for k, v in data.items():
            if isinstance(v, dict) and v.get("sessionId") == sid:
                return k
        return None

    def _recover_for_lock(self, sj, agent, data, sid, lock_path, reason, owning_key=None):
        sessions_dir = os.path.dirname(sj)
        if owning_key and owning_key in data:
            files = transcript_files(sessions_dir, sid)  # includes the lock itself
            self.recover_entry(sj, agent, owning_key, data[owning_key], reason=reason,
                               files_override=files)
        else:
            moved = self.archive_files([lock_path], agent, ts_slug())
            if moved:
                self.recovered.append(
                    f"{agent} :: <orphan lock {os.path.basename(lock_path)}> "
                    f"(reason={reason}, moved aside)")

    def _persisting_lock(self, agent, base, pid, age_s):
        """A live non-gateway lock escalates only on the 2nd consecutive sighting."""
        skey = re.sub(r"[^A-Za-z0-9._-]", "_", f"{agent}__{base}")
        stamp = os.path.join(STAMP_DIR, skey)
        seen_before = os.path.exists(stamp)
        agestr = "?" if age_s is None else f"{age_s:.0f}s"
        esc = (f"{agent}: lock {base} held by LIVE non-gateway pid={pid} across two checks "
               f"(age {agestr}) -- needs manual look")
        if self.dry_run:
            note = ("would ESCALATE (2nd sighting)" if seen_before
                    else "would stamp (1st sighting, no escalate yet)")
            self.log(f"  LOCK live non-gateway holder pid={pid} agent={agent} {base} "
                     f"age={agestr} -> {note}")
            if seen_before:
                self.escalate.append(esc)
            return
        os.makedirs(STAMP_DIR, exist_ok=True)
        if seen_before:
            self.escalate.append(esc)
            self.log(f"  LOCK live non-gateway pid={pid} {base} -> ESCALATE (2nd sighting)")
            try:
                os.unlink(stamp)  # reset after escalating; if it persists again we re-stamp
            except Exception:
                pass
        else:
            self.log(f"  LOCK live non-gateway holder pid={pid} agent={agent} {base} "
                     f"age={agestr} -> stamped (1st sighting, no escalate yet)")
            try:
                with open(stamp, "w") as f:
                    f.write(str(NOW_MS))
            except Exception:
                pass

    # -- top-level run -----------------------------------------------------------
    def run(self):
        self.log(f"silent-session-watchdog start dry_run={self.dry_run} "
                 f"gateway_main_pid={self.gw_pid or 'UNKNOWN'} "
                 f"thresholds(compaction>={COMPACTION_THRESHOLD}, stale>{STALE_MIN}m, "
                 f"write_guard={MIN_WRITE_GUARD_S}s)")
        if not self.gw_pid:
            # Not fatal: dead-pid locks and failed-status recovery still work without it.
            # Only the gateway-aged-out lock branch is skipped. Note it, don't escalate.
            self.log("  WARN: could not resolve gateway MainPID; gateway-held-lock aging "
                     "check disabled this run (dead-pid + failed-status paths unaffected).")
        indexes = sorted(glob.glob(os.path.join(AGENTS_ROOT, "*", "sessions", "sessions.json")))
        self.log(f"  scanning {len(indexes)} agent index file(s)")
        for sj in indexes:
            self.scan_index(sj)

    def report(self):
        print("=" * 78)
        print(f"silent-session-watchdog {'(DRY-RUN)' if self.dry_run else '(LIVE)'} "
              f"{datetime.now().isoformat(timespec='seconds')}")
        print("=" * 78)
        print("\n-- action log --")
        for line in self.actions_log:
            print(line)

        if self.observe:
            print("\n-- observations (no action taken) --")
            for o in self.observe:
                print(f"  OBSERVE: {o}")

        verb = "WOULD RECOVER" if self.dry_run else "RECOVERED"
        print("\n-- summary --")
        if self.recovered:
            # machine-readable line(s). In dry-run we still prefix RECOVERED: so the
            # operator sees exactly what a live run would claim, but the cron only ever
            # runs LIVE, where this line means real recoveries happened.
            tag = "WOULD-RECOVER" if self.dry_run else "RECOVERED"
            print(f"{tag}: {len(self.recovered)} session(s) recovered:")
            for r in self.recovered:
                print(f"  - {r}")
        else:
            print(f"{verb}: none (no wedged/stale-locked/bloated sessions needed recovery)")

        if self.escalate:
            print(f"\nESCALATE: {len(self.escalate)} problem(s) could NOT be safely auto-recovered:")
            for e in self.escalate:
                print(f"  - {e}")
        else:
            print("ESCALATE: none")

        # one-line verdict for quick scanning / cron parsing
        if self.escalate:
            verdict = "VERDICT: ESCALATE (surface to user)"
        elif self.recovered:
            verdict = ("VERDICT: auto-recovered, stay silent" if not self.dry_run
                       else "VERDICT: dry-run found recoverable sessions (no writes made)")
        else:
            verdict = "VERDICT: clean, stay silent"
        print(verdict)


def main():
    ap = argparse.ArgumentParser(description="Auto-recover wedged/bloated OpenClaw sessions.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Detect + print what it WOULD do; make zero writes/moves.")
    args = ap.parse_args()
    wd = Watchdog(dry_run=args.dry_run)
    try:
        wd.run()
    except Exception as e:
        # Never crash the cron; surface as an escalation instead.
        import traceback
        wd.escalate.append(f"watchdog crashed: {e}")
        wd.log("  !! watchdog top-level exception:\n" + traceback.format_exc())
    wd.report()
    # Always exit 0 (the cron decides surfacing based on the ESCALATE line, not exit code).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())