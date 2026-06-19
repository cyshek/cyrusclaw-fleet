#!/usr/bin/env python3
"""Alert-only: detect whether a NEWER github-copilot top-tier primary model
(Opus) has landed in the live catalog vs the configured primary. PRINTS A LINE
ONLY ON A GENUINE DELTA; otherwise 'NOCHANGE'.

Standing rule (Cyrus via main, 2026-06-09): NEVER auto-switch the primary.
This script ONLY reports. It does not edit openclaw.json, does not stage,
does not restart anything. The weekly cron decides whether to ping Discord.

Output contract:
  PRIMARY_UPDATE: <newer-id> available (currently <current-id>)
  NOCHANGE
  NOCHANGE (could not resolve ...)   # fail-safe, no ping
"""
import json, re, subprocess

CFG = "/home/azureuser/.openclaw/openclaw.json"


def catalog():
    try:
        out = subprocess.run(["openclaw", "models", "list"],
                             capture_output=True, text=True, timeout=60).stdout
    except Exception:
        return []
    ids = []
    for line in out.splitlines():
        m = re.match(r'\s*(github-copilot/\S+)', line)
        if m:
            ids.append(m.group(1))
    return ids


def current_primary():
    try:
        c = json.load(open(CFG))
        dm = c.get("agents", {}).get("defaults", {}).get("model")
        if isinstance(dm, dict):
            return dm.get("primary")
    except Exception:
        pass
    return None


def vtuple(s):
    return tuple(int(x) for x in re.findall(r'\d+', s))


def newest_in_family(ids, family_regex):
    """Pick highest numeric version matching family_regex (one capture group)."""
    best = None
    best_key = None
    for i in ids:
        if re.search(r'(codex|mini|nano|haiku)', i):
            continue
        m = re.search(family_regex, i)
        if not m:
            continue
        ver = vtuple(m.group(1))
        if best_key is None or ver > best_key:
            best_key, best = ver, i
    return best


def main():
    cur = current_primary()
    if not cur:
        print("NOCHANGE (could not resolve current primary from config)")
        return
    ids = catalog()
    if not ids:
        print("NOCHANGE (could not resolve catalog)")
        return

    newest_opus = newest_in_family(ids, r'claude-opus-(\d+(?:\.\d+)?)$')
    if not newest_opus:
        print("NOCHANGE (no copilot opus in catalog)")
        return

    cur_ver = vtuple(cur)
    new_ver = vtuple(newest_opus)

    if "claude-opus" in cur and new_ver > cur_ver:
        print("PRIMARY_UPDATE: %s available (currently %s)" % (newest_opus, cur))
        return
    if "claude-opus" not in cur:
        print("PRIMARY_UPDATE: %s available (currently %s, non-opus primary)" % (newest_opus, cur))
        return

    print("NOCHANGE (on newest copilot primary: %s)" % cur)


if __name__ == "__main__":
    main()
