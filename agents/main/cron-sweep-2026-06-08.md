# Cron binding-hygiene sweep — 2026-06-08 (cadence find)

## CONTEXT / WHY
Two related class bugs fleet-wide on `kind:agentTurn` crons:

**BUG A — peer-channel `session:` target (the fragile assistant-tail class).**
A cron with `sessionTarget: session:agent:<peer>:discord:channel:<id>` fails intermittently with `Cannot continue from message role: assistant` when that channel session's transcript tail is an assistant msg at fire time, OR it falls back to a stale `sessionKey` (often main's DM) and the run echoes into the wrong place. Today's earlier sweep fixed all `*-distill`/`weekly-handoff-distill` jobs but MISSED the openclaw-updates maintenance jobs.

**BUG B — isolated cron carrying a live-channel/live-DM `sessionKey` base.**
For an `isolated` job, `sessionKey` is the BASE off which each run derives `<base>:run:<uuid>`. If that base is a LIVE channel session (`...discord:channel:...`) or the LIVE main DM (`agent:main:discord:default:direct:...`), a mid-run compaction can still wedge with the assistant-tail error, AND it's a cross-contamination path with that live session's tail state. Today's fix corrected `sessionTarget` on the distill family but left their stale `sessionKey` base = a HALF-FIX.

## PROVEN-GOOD RECIPE (gateway-through CLI — do NOT raw-edit jobs.json [gateway-cached] and do NOT use cron update/MCP [silently drops sessionTarget/sessionKey])
For each offender, run from `/home/azureuser/.openclaw`:
```
openclaw cron edit <jobId> \
  --session isolated \
  --agent <peer> \
  --session-key agent:<peer>:cron:<jobId> \
  --announce --channel discord \
  --to channel:<deliveryChannelId> \
  --best-effort-deliver
```
- `--session isolated` → fixes BUG A (off the fragile session-target)
- `--session-key agent:<peer>:cron:<jobId>` → fixes BUG B (dedicated cron-scoped base, nothing else writes it)
- `--to channel:<id>` → channel-PREFIXED delivery (several offenders are missing the `channel:` prefix)
- preserve schedule/payload (the edit only patches the flags you pass; leave schedule/message alone)

## BACKUP FIRST
`cp cron/jobs.json cron/jobs.json.bak.cron-sweep-$(date +%s)` and confirm job count stays 35.

## VERIFY EACH (no force-run on destructive jobs!)
- After all edits: re-read via `openclaw cron list --json` AND disk `cron/jobs.json` — confirm sessionTarget=isolated, sessionKey=`agent:<peer>:cron:<jobId>`, delivery.to has `channel:` prefix, bestEffort=true.
- Re-run the two audit queries (below) and confirm BUG A peer-channel offenders → 0 (main's 3 own-channel carve-outs stay), and BUG B isolated-on-live-base risk → 0.
- DO NOT force-run: `weekly-system-updates` (already fixed), `weekly-openclaw-update-check`, `monthly-vm-hygiene` — these run apt/openclaw updates + gateway restart/reboot. Binding-fix verification = config persistence only, NOT a live run.
- The light jobs (daily-handoff-touch, mem-distill-*, smoke tests, reminders) MAY be force-run to flip lastRunStatus error→ok IF safe, but it's optional; persistence verification is sufficient.

## ALREADY FIXED THIS CADENCE (do NOT touch, just confirm still good)
- `weekly-system-updates` (72d852e4-a843-482b-a64d-ba4807452c2f) → isolated + agent:openclaw-updates:cron:72d852e4... + to channel:1502552885756432496 + bestEffort. DONE.

## BUG A — peer-channel `session:` OFFENDERS (fix these, openclaw-updates agent, deliver channel 1502552885756432496)
1. `daily-handoff-touch` — id 9127c26b-9f17-423f-9143-b9b70f9405e5 — agent openclaw-updates — to channel:1502552885756432496
2. `weekly-openclaw-update-check` — id ef29b7ed-2247-423e-9b5a-10f38f92612d — agent openclaw-updates — to channel:1502552885756432496
3. `monthly-vm-hygiene` — id e93a5533-912b-4b86-aef3-4a5e856e84f1 — agent openclaw-updates — to channel:1502552885756432496

(main's mem-distill-main / main-peer-state-sync / main-memory-health-watchdog target main's OWN channel = intentional carve-out, LEAVE THEM.)

## BUG B — isolated crons on a live-channel/live-DM sessionKey base (rebase sessionKey only; sessionTarget already isolated)
For these, sessionTarget is ALREADY `isolated` — you ONLY need to fix the sessionKey base (and add channel: prefix to delivery.to if missing). Use:
```
openclaw cron edit <jobId> --session-key agent:<peer>:cron:<jobId> --announce --channel discord --to channel:<deliveryId> --best-effort-deliver
```
Determine <peer> and <deliveryId> from the job's agentId + existing delivery channel. Inventory (resolve exact agentId/delivery from `openclaw cron list --json`):
- `daily-handoff-touch` (job-search) — id 5146349a-f8e3-433e-9d29-6a222cdc7514 — deliver channel 1501827950474166332 (currently missing channel: prefix)
- `mem-distill-job-search` — peer job-search
- `mem-distill-trading-bench` — peer trading-bench
- `mem-distill-making-money` — peer making-money
- `mem-distill-openclaw-updates` — peer openclaw-updates
- `trading-bench: hourly LLM mutation round (1 candidate, quarantined)` — peer trading-bench, deliver channel 1508503706545557656
- `trading-bench: nightly post-market review (weekdays)` — peer trading-bench
- `trading-bench: weekly leaderboard (Sat 9am PT)` — peer trading-bench
- `trading-bench: weekly MEMORY.md distill (self-verifying)` — peer trading-bench
- `remind-cyrus-workday-apple-unblocks` — peer job-search, deliver channel 1501827950474166332 (one-shot reminder — LEAVE if it's a one-shot `at` schedule that already fired/will fire soon; only rebase if recurring. Use judgement.)
- `job-search adapter smoke test` — peer job-search, deliver channel 1501827950474166332
- `weekly-handoff-distill` (openclaw-updates) — id 7c58d04f-bcb0-4510-97cd-e8d2395ad7f1
- `weekly-handoff-distill` (job-search) — id aadd3efe-e1e2-4f2c-bb47-2cb7d0675e56

NOTE: confirm each job's real agentId + delivery channel from `openclaw cron list --json` before editing — do NOT guess. If a job's agentId is ambiguous or it's a fired one-shot, SKIP it and report it instead of guessing.

## AUDIT QUERIES (run before + after)
```bash
cd /home/azureuser/.openclaw && openclaw cron list --json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin); jobs=d if isinstance(d,list) else d.get('jobs',[])
print('=== BUG A: agentTurn on session:...channel (peer offenders) ===')
off=0
for j in jobs:
    pk=(j.get('payload') or {}).get('kind'); st=j.get('sessionTarget','') or ''
    if pk=='agentTurn' and st.startswith('session:') and 'channel' in st:
        carve=any(j.get('id','').startswith(x) for x in ('0d801877','caa8e485','c2e1d3ef'))
        if not carve: off+=1; print('  OFFENDER', j.get('name'), st)
print('peer offenders:', off)
print('=== BUG B: isolated agentTurn on live-channel/live-DM sessionKey ===')
risk=0
for j in jobs:
    pk=(j.get('payload') or {}).get('kind'); st=j.get('sessionTarget','') or ''; sk=j.get('sessionKey','') or ''
    if pk=='agentTurn' and st=='isolated' and ('discord:channel:' in sk or (':direct:' in sk and ':cron:' not in sk)):
        risk+=1; print('  RISK', j.get('name'), sk)
print('isolated-on-live-base:', risk)
"
```

## DELIVERABLE
A short report: which jobs you edited (old→new sessionTarget/sessionKey/delivery), backup filename, final audit counts (should be BUG A peer offenders=0, BUG B risk=0), any jobs you deliberately SKIPPED + why, and confirm store job count stayed 35. Keep it terse.
