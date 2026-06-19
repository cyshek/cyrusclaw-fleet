#!/usr/bin/env python3
"""
bootstrap-size-guard.py  (stdlib-only)

Scans every agent workspace for bootstrap files (AGENTS.md, MEMORY.md, and the
other injected continuity files) that exceed the gateway's per-file injection
cap, and reports which ones need trimming.

It does NOT trim anything itself (a blunt size-trim could eat a hard-won
lesson). It DETECTS + REPORTS. A careful reasoning-trim subagent — spawned by
the daily cron that calls this — does the actual in-place, backed-up trim.

It also reports current box load so the caller can BACK OFF (defer the trim)
when the host is saturated: respawning heavy trim work into a loaded box just
gets killed by the health-monitor's protective restart (lesson 2026-06-08).

Exit code 0 always (it's a reporter). JSON report on stdout.

Limits (from dist DEFAULT_BOOTSTRAP_MAX_CHARS=2e4 / TOTAL=6e4, 2026-06-08):
  per-file cap  = 20000 chars   (over => truncated every session start)
  total cap     = 60000 chars   (sum of injected bootstrap files per agent)
Overridable in openclaw.json via agents.defaults.bootstrapMaxChars /
bootstrapTotalMaxChars (and per-agent). We read those if present.
"""
import json, os, sys, subprocess, glob

OPENCLAW_HOME = os.path.expanduser("~/.openclaw")
CONFIG = os.path.join(OPENCLAW_HOME, "openclaw.json")
AGENTS_DIR = os.path.join(OPENCLAW_HOME, "agents")
MAIN_WS = os.path.join(OPENCLAW_HOME, "workspace")

DEFAULT_PER_FILE = 20000
DEFAULT_TOTAL = 60000

# Files that get injected as bootstrap context (the ones a cap actually bites).
# AGENTS.md + MEMORY.md are the usual offenders; the rest are listed so the
# TOTAL budget is computed honestly.
BOOTSTRAP_FILES = ["AGENTS.md", "MEMORY.md", "SOUL.md", "USER.md", "IDENTITY.md", "TOOLS.md"]
# Warn a bit before the hard cap so we trim proactively, not at the cliff.
WARN_RATIO = 0.92  # 92% of cap => warn; >=100% => breach


def load_cfg():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        return {}


def resolve_caps(cfg, agent_id):
    per_file = DEFAULT_PER_FILE
    total = DEFAULT_TOTAL
    try:
        defaults = (cfg.get("agents") or {}).get("defaults") or {}
        if isinstance(defaults.get("bootstrapMaxChars"), (int, float)) and defaults["bootstrapMaxChars"] > 0:
            per_file = int(defaults["bootstrapMaxChars"])
        if isinstance(defaults.get("bootstrapTotalMaxChars"), (int, float)) and defaults["bootstrapTotalMaxChars"] > 0:
            total = int(defaults["bootstrapTotalMaxChars"])
        # per-agent override
        agents = (cfg.get("agents") or {}).get("entries") or (cfg.get("agents") or {}).get("list") or []
        if isinstance(agents, dict):
            agents = list(agents.values())
        for a in agents:
            if not isinstance(a, dict):
                continue
            if a.get("id") == agent_id or a.get("agentId") == agent_id:
                if isinstance(a.get("bootstrapMaxChars"), (int, float)) and a["bootstrapMaxChars"] > 0:
                    per_file = int(a["bootstrapMaxChars"])
                if isinstance(a.get("bootstrapTotalMaxChars"), (int, float)) and a["bootstrapTotalMaxChars"] > 0:
                    total = int(a["bootstrapTotalMaxChars"])
    except Exception:
        pass
    return per_file, total


def discover_workspaces():
    """Return list of (agent_id, workspace_path)."""
    out = []
    # main lives at ~/.openclaw/workspace
    if os.path.isdir(MAIN_WS):
        out.append(("main", MAIN_WS))
    # peers live at ~/.openclaw/agents/<id>/workspace
    if os.path.isdir(AGENTS_DIR):
        for d in sorted(os.listdir(AGENTS_DIR)):
            if d.startswith("."):
                continue
            ws = os.path.join(AGENTS_DIR, d, "workspace")
            if os.path.isdir(ws):
                out.append((d, ws))
    return out


def box_load():
    """Return (load1, ncpu, saturated_bool). Saturated if load1/ncpu > 0.85."""
    try:
        load1 = os.getloadavg()[0]
    except Exception:
        load1 = 0.0
    try:
        ncpu = os.cpu_count() or 1
    except Exception:
        ncpu = 1
    return load1, ncpu, (load1 / max(ncpu, 1)) > 0.85


def main():
    cfg = load_cfg()
    load1, ncpu, saturated = box_load()
    breaches = []
    warnings = []
    scanned = 0
    for agent_id, ws in discover_workspaces():
        per_file, total = resolve_caps(cfg, agent_id)
        agent_total = 0
        for name in BOOTSTRAP_FILES:
            p = os.path.join(ws, name)
            if not os.path.isfile(p):
                continue
            try:
                n = os.path.getsize(p)  # bytes ~= chars for ASCII-ish md; close enough for a guard
            except Exception:
                continue
            scanned += 1
            agent_total += n
            rec = {"agent": agent_id, "file": name, "path": p, "chars": n, "cap": per_file}
            if n >= per_file:
                rec["over_by"] = n - per_file
                breaches.append(rec)
            elif n >= int(per_file * WARN_RATIO):
                rec["headroom"] = per_file - n
                warnings.append(rec)
        if agent_total >= total:
            breaches.append({"agent": agent_id, "file": "<TOTAL>", "path": ws,
                             "chars": agent_total, "cap": total, "over_by": agent_total - total})

    report = {
        "ok": True,
        "scanned_files": scanned,
        "box": {"load1": round(load1, 2), "ncpu": ncpu, "saturated": saturated},
        "breach_count": len(breaches),
        "warn_count": len(warnings),
        "breaches": breaches,
        "warnings": warnings,
        # caller guidance:
        "action": ("defer_trim_box_saturated" if (breaches and saturated)
                   else ("trim_needed" if breaches else "none")),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
