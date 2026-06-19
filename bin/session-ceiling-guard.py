#!/usr/bin/env python3
"""
session-ceiling-guard.py — early-warning for the compaction-deadlock failure mode.

Background: on 2026-06-05 a job-search Discord channel session reached its context
ceiling, repeatedly compacted, then wedged when compaction hit the
`already_compacted_recently` cooldown and couldn't free space — silently dropping
inbound messages at preflight. There is no config knob for the compaction cooldown,
so prevention is (a) idle-reset of group/channel sessions (session.resetByType.group,
12h) and (b) this guard, which flags a session in chronic compaction-grind BEFORE
it wedges.

IMPORTANT — what `contextTokens` actually is: empirically it is the model's static
context-WINDOW SIZE (e.g. 128000 or 200000), NOT the live fill level. Hundreds of
fresh/idle sessions show contextTokens=128000/200000 with zero real usage, so it is
useless as a pressure signal. The reliable wedge indicator is `compactionCount`: a
session that has compacted many times has been grinding against its window
repeatedly. The wedged session had 4 across a short life; chronically-busy long-lived
:main / channel sessions routinely reach 20+, so we warn well above normal.

Scans every agent's sessions.json. Flags a LONG-LIVED human/main/channel session as
AT RISK when it is ACTIVE (recently touched) AND compactionCount >= WARN_COMPACTIONS.
Subagent / cron / explicit sessions are EXCLUDED — they're short-lived, self-terminate,
and a high compaction count there is normal churn, not a wedge risk to a human channel.

Prints a report to stdout. Exit code 0 always. The cron's agent turn announces to
Discord only when something is flagged (NO_REPLY when clean).
"""
import json, os, glob, time

AGENTS_ROOT = "/home/azureuser/.openclaw/agents"
WARN_COMPACTIONS = 15         # warn well above normal long-lived-session churn
ACTIVE_WINDOW_S = 36 * 3600   # only care about sessions touched in last 36h


def parse_ts(v):
    """Best-effort: accept epoch seconds/ms or ISO string. Return epoch seconds or None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v / 1000.0 if v > 1e12 else float(v)
    if isinstance(v, str):
        try:
            from datetime import datetime
            return datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None
    return None


def main():
    now = time.time()
    flagged = []
    scanned = 0
    for sj in glob.glob(os.path.join(AGENTS_ROOT, "*", "sessions", "sessions.json")):
        agent = sj.split("/")[-3]
        try:
            d = json.load(open(sj))
        except Exception as e:
            flagged.append(f"⚠️ {agent}: sessions.json unreadable ({e})")
            continue
        if not isinstance(d, dict):
            continue
        for key, e in d.items():
            if not isinstance(e, dict):
                continue
            # only long-lived human/main/channel sessions can wedge a channel; skip churny ones
            if (":subagent:" in key) or (":cron:" in key) or (":explicit:" in key):
                continue
            scanned += 1
            comp = e.get("compactionCount") or 0
            # recency gate — ignore long-dead sessions
            last = None
            for f in ("updatedAt", "lastActivityAt", "lastMessageAt", "touchedAt", "mtime"):
                last = parse_ts(e.get(f))
                if last:
                    break
            recent = (last is None) or ((now - last) <= ACTIVE_WINDOW_S)
            if not recent:
                continue
            if isinstance(comp, (int, float)) and comp >= WARN_COMPACTIONS:
                flagged.append(
                    f"🔴 {agent} :: {key}\n"
                    f"     compactionCount={comp} (>= {WARN_COMPACTIONS}) — chronic compaction grind, wedge-risk if it stalls"
                )

    if flagged:
        print(f"SESSION-CEILING-GUARD: {len(flagged)} session(s) in chronic compaction-grind "
              f"(scanned {scanned} long-lived session(s)). Wedge-risk if compaction ever stalls:")
        for f in flagged:
            print(f)
        print("\nAction: if one of these is a human Discord channel and stops responding, "
              "reset/archive it (same fix as 2026-06-05 job-search). Idle-reset (12h) should "
              "normally recycle channel sessions before they get here.")
    else:
        print(f"SESSION-CEILING-GUARD: clean. Scanned {scanned} long-lived session(s); "
              f"none in chronic compaction-grind (>= {WARN_COMPACTIONS}).")


if __name__ == "__main__":
    main()
