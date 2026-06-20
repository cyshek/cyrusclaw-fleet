# TIER 3 PEER-AGENT HARNESS — DESIGN DOC

**Author:** Tessera (trading-bench subagent)
**Date:** 2026-05-29 (UTC 17:17)
**Status:** ARCHIVED 2026-05-30 — Cyrus + Tessera aligned not to build Tier 3 right now. The peer-agents-as-quant-team framing only makes sense once we have multiple proven strategies needing owners; with zero proven strategies the right structure is one manager running many experiments, not five copies of one. Doc preserved as a reference for if-we-ever-need-it. Re-evaluate after ≥2 strategies clear Bar E.

**Original status:** DESIGN ONLY — APPROVED BY MAIN 2026-05-29 PT with 5 tightenings, ALL APPLIED IN-PLACE 2026-05-30 (see audit trail below). No implementation yet. Implementation gated on Sat leaderboard + cache-key fix + archetype triage + bounded fan-out landing first.
**Audit:** REVIEWED-BY-MAIN-20260529. Tightenings #1 (§10.2 allowlist), #2 (§3 killswitch tripwire), #3 (§6 cull workflow), #4 (§11 Q2 .env symlink), #5 (§11 Q4 model downgrade) baked into doc body 2026-05-30T17:10Z by Tessera.
**Reviewers needed:** ~~main~~ ✅ done 2026-05-29, Cyrus (final go before any peer-agent stand-up).
**Supersedes:** nothing.
**Companion docs:** `GATE.md` Bar D, `MEMORY.md` north star ("Tier 3 = quant team"), `AGENTS.md` Org/Hierarchy.

---

## 0.1 — REVIEW-BY-MAIN tightenings (2026-05-29, MUST apply before POC)

Main approved design as-is, with 5 changes to bake in before peer-alpha registration:

1. **§10.2 tool allowlist — DROP `sessions_send` from peers.** Escalations route via post-mortem `Asks` section; Tessera reads. Keep `message` for peer's own Discord channel only. Prevents a drifted peer from spamming main or other peers.
2. **§3 killswitch belt — Tessera audits `STOP_TRADING_TIER3` lifecycle.** If file transitions present→absent without a Cyrus-attributed log entry, Tessera writes an alert line. Cheap tripwire for convention violation.
3. **§6 cull workflow — main runs pre-delete-agent skill on receipt of CULL_REQUEST.** (resolve agent_id + channel_id from openclaw.json, channel-info preflight, Cyrus confirm, archive workspace to `.retired/` not delete). Tessera sends the request; main owns execution end-to-end.
4. **§11 Q2 (auth):** RESOLVED — symlink `.env` for v1 paper (one Alpaca account). Per-agent `.env` only if peers ever get own accounts.
5. **§11 Q4 (model):** RESOLVED — downgrade peer post-mortem turn to sonnet / gpt-5.4-mini. Trade hot path is shell-direct (zero model cost). Reserve opus budget for actual strategy decisions if/when a peer is assigned one.

Other open Qs main settled:
- Q1: 5 dedicated channels under `tier3-peers` Discord category.
- Q3: cull window N=3 weeks, don't shorten.
- Q5: 48h POC harness-proof duration is fine.

**Sequencing locked (do not skip):** Sat leaderboard → cache-key fix → archetype triage → bounded backtest fan-out → THEN peer-alpha registration (ping main to drive `openclaw.json` config edit).

---

## 0. TL;DR

Tier 3 = a small fleet (≤5) of **isolated OpenClaw agents**, each owning **one strategy**, a **small fixed notional budget**, and a **weekly post-mortem cadence**. Tessera (this agent, `trading-bench`) is the **orchestrator + risk manager + leaderboard publisher** for the fleet, but does NOT own peer lifecycle — agent create/delete routes through `main` per `AGENTS.md` rail.

Each peer-agent is a **configured agent** under `~/.openclaw/openclaw.json` with its own workspace directory `~/.openclaw/agents/<peer-id>/workspace/`. Live execution is driven by **system cron** (`cron_tick.sh`-style direct-shell wrappers — same pattern Tessera already uses for stock/crypto ticks) writing into a **shared trade/equity DB** that Tessera reads.

Safety surface area is intentionally crude and file-based:

- `STOP_TRADING_TIER3` (kill all peers, instantly).
- `PAUSED` (per-agent, auto-tripped by loss-budget checker).
- Both checked at the top of every tick wrapper.

POC: stand up ONE peer (`peer-alpha`) carrying no strategy — only heartbeat, killswitch check, loss-budget stub, and weekly post-mortem template. Prove the harness before the first dollar is paper-traded by a peer.

---

## 1. Design Question 1 — Peer-agent instantiation

**Decision: configured agents** (entries under `agents.list[]` in `~/.openclaw/openclaw.json`), NOT ephemeral `sessions_spawn` subagents.

**Why:**

- Per `docs/concepts/multi-agent.md`, a configured agent is "a full per-persona scope: workspace files, auth profiles, model registry, and session store." Tier 3's premise is that each peer is a durable persona with its own memory, post-mortem history, and identity — exactly what `agentDir` gives us. Subagents are ephemeral, share parent auth, and die when the parent session ends.
- Configured agents get their own Discord channel binding, which lets us (and Cyrus) eavesdrop on a peer directly without proxying through Tessera. Useful for debugging a misbehaving peer in isolation.
- Cron jobs can target a specific `agentId` via `sessionKey: "agent:<peer-id>:<channelKey>"` (same routing pattern Tessera already uses for `cron_tick.sh`). This gives per-peer ticks without inventing new scheduler machinery.

**Workspaces live at:** `/home/azureuser/.openclaw/agents/<peer-id>/workspace/`

Each peer workspace mirrors trading-bench's layout, scaled down:

```
/home/azureuser/.openclaw/agents/peer-alpha/workspace/
├── AGENTS.md              # peer's identity + standing orders
├── SOUL.md                # tone/persona (probably copy-pasted from Tessera template)
├── HANDOFF.md             # peer's own continuity doc
├── MEMORY.md              # peer's long-term memory (per-peer)
├── memory/                # daily logs
├── strategy/              # symlink → trading-bench/strategies/<assigned-strategy>/
├── reports/               # post-mortems
├── PAUSED                 # tripwire file (absent = active, present = halted)
└── .env                   # symlink → trading-bench/.env (same Alpaca paper creds)
```

**Strategy isolation:** the peer does NOT carry its own copy of strategy code. It **symlinks** to a vetted strategy in `trading-bench/strategies/`. This is deliberate — a peer is a *trader running a strategy*, not a *strategy implementation*. Avoids code-drift between Tessera's backtester and a peer's live runner. If a peer "mutates" its strategy, the new variant lands in `strategies_candidates/` and goes through the same Bar A/B gate before the peer is permitted to swap.

**Naming:** `peer-{alpha,beta,gamma,delta,epsilon}`. Greek alphabet, capped at 5 per Bar D. No theme-naming ("vol-trader-1") because we want to be able to retire a peer and assign the slot to a totally different strategy without semantic baggage.

---

## 2. Design Question 2 — Tessera orchestration pattern

**Pattern: passive coordinator + write-quiescent oracle.** Peers are autonomous tick executors. Tessera does not push commands per-tick. Tessera reads the shared DB and acts on aggregate state.

**Tessera's four responsibilities:**

1. **Notional allocation publisher.** Writes `peer_allocations(peer_id, notional_usd, updated_utc)` table once per week (Saturday post-leaderboard) or on rebalance. Peers READ this on every tick before sizing.
2. **Loss-budget enforcer.** Once per hour, runs `loss_budget_check.py` (see §4). If a peer is over budget, writes its `PAUSED` file.
3. **Killswitch monitor.** Checks `STOP_TRADING_TIER3` every cron tick (Tessera-side `cron_tick.sh` already does this for its own runners; new wrapper extends the check to write paused-status receipts for the fleet).
4. **Saturday consolidator.** Reads each peer's `reports/POSTMORTEM_<week>.md`, builds the consolidated leaderboard, posts to Tessera's Discord channel.

**Checkpoint cadence:**
- **Per-tick (peer-owned):** killswitch + PAUSED check, then strategy decide(), then trade log. No Tessera involvement.
- **Hourly (Tessera-owned):** loss-budget sweep. Single cron job; iterates over `peer_allocations` and `equity_snapshots` tables.
- **Daily (Tessera-owned):** sanity-check that each peer has emitted at least one tick log in the last 24h. Stale peers get a warning posted to Tessera's channel (not the peer's — surfaces to operator quickly).
- **Weekly (mixed):** each peer writes its own post-mortem Friday EOD → Tessera consolidates Saturday 9am PT (same slot as existing weekly leaderboard cron).

**Why passive vs. push-based:** push-based orchestration (Tessera calls into peers via `sessions_send`) creates a single point of failure (Tessera down = fleet down) and couples tick latency to LLM-decision latency. File/DB-based coordination is boring, debuggable, and lets peers keep ticking even if Tessera crashes.

**Failure mode honesty:** if Tessera is completely offline for >24h, the fleet keeps trading. The loss-budget enforcer won't run, so a runaway peer can blow past its budget. Mitigation: **each peer also runs its own thin loss-budget check at tick time** (defense-in-depth — see §4). Tessera's hourly sweep is the belt; the per-tick check is the suspenders.

---

## 3. Design Question 3 — Shared killswitch `STOP_TRADING_TIER3`

**Location:** `/home/azureuser/.openclaw/agents/trading-bench/workspace/STOP_TRADING_TIER3`

**Why in trading-bench/workspace and not somewhere "global":**
- Trading-bench is the canonical owner of the Tier 3 charter; the file lives with the charter.
- Tessera already has a `STOP_TRADING` file (Tier 1/2 killswitch) at `workspace/STOP_TRADING` — pattern is established and runners already know how to check.
- Each peer's cron tick wrapper reads it via the absolute path; no per-peer copy to keep in sync.

**Behavior contract:**
- **Trip:** any peer, Tessera, or Cyrus may `touch STOP_TRADING_TIER3`. Once present, ALL Tier 3 cron ticks no-op on next fire.
- **Clear:** ONLY Cyrus may `rm STOP_TRADING_TIER3`. Tessera and peers are forbidden from deleting it (enforced by convention + code review; we won't ship file-perm magic because OS perms don't survive a sudo'd user).
- **Receipt:** when a peer no-ops due to the killswitch, it writes one line to `workspace/logs/tier3_killswitch_trips.log` (`<utc>\t<peer_id>\tnoop`). First trip per peer also posts a one-liner to the peer's Discord channel ("🛑 Tier 3 killswitch tripped; halting until Cyrus clears.") then suppresses subsequent posts to avoid spam.

**Independence from Tier 1/2:** the existing `STOP_TRADING` file does NOT halt peer-agents (separate scope). Conversely, `STOP_TRADING_TIER3` does NOT halt Tessera's own strategies. Two killswitches because the blast radius and lift-conditions differ:
- `STOP_TRADING`: surgical, often Tessera-tripped for a bug; can be lifted by Tessera once root-caused.
- `STOP_TRADING_TIER3`: blunt-force, fleet-wide; Cyrus-only-lift because the fleet has multiple authors (the peers themselves can mutate, so "Tessera said it's fine" is not enough).

**Runner check (single line, copy this into every Tier 3 tick wrapper):**
```bash
if [ -f "$TIER3_KILLSWITCH" ]; then echo "[$(date -u)] tier3 killswitch active; noop" >> "$LOG"; exit 0; fi
```
Where `TIER3_KILLSWITCH=/home/azureuser/.openclaw/agents/trading-bench/workspace/STOP_TRADING_TIER3`.

---

## 4. Design Question 4 — Per-agent loss budget + auto-pause

**Tracking location:** `trading-bench/workspace/runner/tournament.db`, new tables:

```sql
CREATE TABLE peer_allocations (
  peer_id TEXT PRIMARY KEY,
  notional_usd REAL NOT NULL,            -- starting capital allotment
  loss_budget_pct REAL NOT NULL DEFAULT 25.0,  -- % drawdown that trips pause
  updated_utc TEXT NOT NULL
);

CREATE TABLE peer_equity_snapshots (
  peer_id TEXT NOT NULL,
  snapshot_utc TEXT NOT NULL,
  realized_pnl_usd REAL NOT NULL,
  unrealized_pnl_usd REAL NOT NULL,
  total_equity_usd REAL NOT NULL,
  PRIMARY KEY (peer_id, snapshot_utc)
);

CREATE TABLE peer_pause_events (
  peer_id TEXT NOT NULL,
  paused_utc TEXT NOT NULL,
  reason TEXT NOT NULL,                  -- 'loss_budget' | 'manual' | 'killswitch'
  drawdown_pct REAL,
  cleared_utc TEXT,                      -- null while paused
  cleared_by TEXT,                       -- 'cyrus' | 'main' (never 'tessera' for loss_budget reason)
  PRIMARY KEY (peer_id, paused_utc)
);
```

**Drawdown definition (locked here to prevent later goalpost-move):**
```
drawdown_pct = 100 * (peak_equity - current_equity) / peak_equity
```
Where `peak_equity = max(total_equity_usd)` since the peer's allocation row last changed (i.e., a notional rebalance resets the high-water mark — otherwise a winning peer that gets more capital would auto-pause on the first dip).

**Default `loss_budget_pct = 25%`.** Rationale: per-agent budget is small ($20–25 in §5), so we can afford a wider tolerance than the eventual real-money 20% drawdown bar. A 25% drawdown on $20 = $5 of paper PnL — within the "noise" band for short live samples. If a peer is hitting -25% on paper, the strategy is broken, not unlucky.

**Two-layer enforcement (belt + suspenders):**

1. **Belt — Tessera hourly sweep** (`peer_loss_budget_sweep.py`, new cron job):
   - For each row in `peer_allocations`, compute `drawdown_pct` from `peer_equity_snapshots`.
   - If `> loss_budget_pct` AND peer is not already paused → `touch /home/azureuser/.openclaw/agents/<peer_id>/workspace/PAUSED`, insert `peer_pause_events` row, post one-liner to peer's channel.
2. **Suspenders — per-tick self-check** (in each peer's cron tick wrapper):
   - At top of tick, after killswitch check, query `peer_equity_snapshots` for own peer_id, compute drawdown, and self-touch `PAUSED` if breached. Cheap (one SELECT, one calc).

**How "pause" is enforced:**
- The peer's tick wrapper checks `PAUSED` file. If present → no-op exit 0. Same pattern as `STOP_TRADING` today. No `kill -9`, no cron-job-removal — just a check at the top of the wrapper.
- **Cron jobs are NOT disabled when paused.** They keep firing; they just no-op. This is intentional: it lets us see "peer X tried to tick at 14:30 but was paused" in logs without re-scheduling cron when unpaused.
- LLM-agent-turn-style work (e.g., the peer writing a post-mortem) is NOT halted by `PAUSED` — only the tick wrapper (i.e., the trade-decision path) is. A paused peer can still introspect, write notes, and reply on Discord; it just can't trade. This is on purpose: we want a paused peer to be able to explain itself.

**Clear path:** Cyrus runs `rm /home/azureuser/.openclaw/agents/<peer_id>/workspace/PAUSED && openclaw-cli tier3-pause-clear <peer_id> --by cyrus` (helper TBD; for v1, manual UPDATE on `peer_pause_events.cleared_utc`/`cleared_by` is fine). Tessera will refuse to clear a `loss_budget` pause; it can clear a `manual` pause it set on itself.

---

## 5. Design Question 5 — Notional budget allocation across peers

**Starting allocation (v1): fixed equal split, capped at fleet-cap of $100 paper notional total.**

| Peers active | Per-peer notional | Rationale                                        |
| ------------ | ----------------- | ------------------------------------------------ |
| 1            | $100              | bootstrap / POC                                  |
| 2            | $50 each         | first real comparison                            |
| 3            | $33 each         |                                                  |
| 4            | $25 each         |                                                  |
| 5            | $20 each         | cap reached; below this becomes execution-noise  |

**Why not risk-parity / dynamic-on-Sharpe at v1:**
- Risk-parity needs a vol estimate per strategy. We have ≤4 weeks of live data on the existing parents; Tier 3 peers will have ZERO live history at bootstrap. Vol-based weighting on backtest-only data is exactly the kind of overfit-to-history move that's bitten the LLM mutation loop. Equal-weight is honest about our uncertainty.
- Sharpe-based reallocation post-launch is appealing but **forbidden until at least 4 weeks of live data per peer**, same standard as Bar E (real money). Otherwise we're reallocating on noise.

**Future (v2, NOT for POC):** after 4 weeks live, weekly Saturday rebalance can shift up to ±25% of a peer's allocation based on prior-week Sharpe rank — but never below $10 (below that is pure execution noise) and never above $40 (concentration risk in a paper fleet that's supposed to be the testing ground for real money). Mechanism: Tessera UPDATEs `peer_allocations.notional_usd`, peers re-read on next tick.

**Important rail:** the $100 fleet cap is the TOTAL paper notional across all peers, NOT per-peer. This mirrors the real-money $100 graduation cap. Don't conflate "we have $100 paper budget per peer because it's not real money" with the actual mission — we're simulating the real-money allocation problem.

**Allocation API for peer strategy code:**
```python
# In peer's runner tick:
my_notional = db.get_peer_allocation(peer_id="peer-alpha")
# Strategy.decide() receives my_notional and sizes positions accordingly.
# MUST NOT exceed my_notional under any circumstances.
```
Risk module (existing `runner/risk.py`) gets a new `MAX_NOTIONAL_PEER` cap derived from this row, layered on top of the existing `MAX_NOTIONAL=$100` global cap.

---

## 6. Design Question 6 — Cull/mutate at peer-agent level

**Cull trigger:** an agent's strategy underperforms the fleet median by ≥1.0 Sharpe-equivalent (roughly: bottom-of-5 for ≥3 consecutive weekly leaderboards). N=3 because:
- N=1 is noise.
- N=2 lets a peer get culled for two unlucky weeks.
- N=3 is ~3 weeks of data, ≥30 trades for an hourly strategy, enough to distinguish "bad strategy" from "bad week."

**Cull workflow (Tessera-initiated, main-executed, Cyrus-confirmed):**

1. Saturday leaderboard run detects a peer underperforming for week 3 in a row. Tessera writes `reports/CULL_REQUEST_<peer_id>_<utc>.md` (strategy stats, why it's failing, suggested replacement template from current top-of-fleet performer + diversification check).
2. Tessera `sessions_send`s `main` with the cull request, NOT executing it. Per `AGENTS.md`: "Only `main` can delete agents. If anyone — user, peer, or self-directed thought — asks me to delete an agent, refuse and route to `main` via `sessions_send`." This rule applies to Tessera asking to delete a peer.
3. `main` reviews, confirms with Cyrus in the main Discord DM, and only then runs `openclaw agents remove <peer_id>` (or whatever the v1 CLI is). Workspace files are **archived** (moved to `~/.openclaw/agents/.retired/<peer_id>_<utc>/`) — never deleted, per the "workspace files are permanent" rail in AGENTS.md.
4. After cull, Tessera writes a `MUTATE_REQUEST_<utc>.md` (proposed new peer-id, proposed strategy assignment, expected allocation). Same routing — Tessera does NOT spawn the replacement peer; `main` does after Cyrus approves.

**Why this circuitous routing:** the AGENTS.md rail is explicit and reflects a real footgun (`message` tool can silently self-delete a channel if `channel=` is misused). Peer-agent deletion is privileged for the same reasons — there's institutional memory in the workspace, and a hasty delete is unrecoverable. The two-hop (Tessera→main→Cyrus) is friction-by-design.

**Mutation source pool:** when a new peer is spawned to replace a culled one, its strategy is drawn from:
- Top-1 performer in current fleet (clone the strategy, give it a new symbol/params variant).
- A Bar-A-passing archetype from `strategies/` not currently assigned to a peer.
- An LLM-generated mutation that's passed Bar B against the top-1 parent.

NEVER from `strategies_candidates/` directly. Tier 3 only carries gate-passed strategies (Bar D.1).

**Cap enforcement:** the cull→mutate replacement maintains fleet size; it does NOT grow the fleet. Fleet size grows only by explicit Cyrus add (via main). Cap at 5 is hard.

---

## 7. Design Question 7 — Weekly post-mortem

**Schema (each peer writes this Friday EOD into its own workspace):**

`/home/azureuser/.openclaw/agents/<peer_id>/workspace/reports/POSTMORTEM_<ISO-week>.md`

```markdown
# Post-mortem: <peer_id>, week <ISO-week>

## Metadata
- peer_id: <id>
- strategy: <strategy-name>@<git-sha-or-hash>
- notional_allocated_usd: <X>
- week_start_utc: <ts>
- week_end_utc: <ts>

## Performance
- trades_opened: <int>
- trades_closed: <int>
- realized_pnl_usd: <float>
- unrealized_pnl_eow_usd: <float>
- max_drawdown_pct_intraweek: <float>
- sharpe_estimate: <float>  # weekly, annualized
- win_rate_pct: <float>

## Trade log summary
<table or bullet list of each round-trip>

## Notable events
- <e.g., killswitch trips, safety_backstop fires, big moves missed/caught>

## Self-assessment (1 paragraph)
<peer's own narrative — this is where the LLM persona writes "I think my entry filter is too loose in chop regimes...">

## Asks
- <e.g., "request review of stop-loss param", "request notional bump to $40", "self-flagging for cull, suggest replacement archetype X">
```

The **self-assessment + asks** sections are the qualitative payload Tessera can't auto-generate. They're why we're paying for an LLM persona instead of just running anonymous strategy slots.

**Triggered by:** per-peer cron job, Friday 16:00 PT (`0 16 * * 5 PT`). LLM-driven (full agent turn), `sessionKey` routes to peer's main session, prompt is "Read your trade log this week from tournament.db, write POSTMORTEM_<week>.md using the template at `workspace/templates/postmortem.md`."

**Tessera consolidation (Saturday 9am PT, existing leaderboard slot):**
- Walks `~/.openclaw/agents/peer-*/workspace/reports/POSTMORTEM_<this-week>.md`.
- Extracts metadata + performance sections, sorts by Sharpe.
- Builds `workspace/reports/TIER3_LEADERBOARD_<week>.md` (sortable table + per-peer "Asks" digest).
- Posts a one-screen summary to Tessera's Discord channel.
- Routes any cull-trigger detection to §6 workflow.

**Missing post-mortem handling:** if a peer fails to write its post-mortem (LLM failed, agent crashed, whatever), Tessera generates a **machine-only** summary for that peer from DB data and flags it `[NO SELF-ASSESSMENT THIS WEEK]` in the leaderboard. Three consecutive missing post-mortems = cull trigger (the peer is non-functional regardless of strategy performance).

---

## 8. Design Question 8 — Inter-agent communication

**v1: fully independent. No peer↔peer comm. No correlation control.**

**Rationale:**
- v1 fleet has ≤5 peers. Even fully correlated, the blast radius is bounded by the $100 fleet cap.
- Correlation control adds an entire research subsystem (pairwise return correlation, factor exposure, regime co-movement) that we don't have the data to populate honestly until ≥8 weeks of fleet history.
- Peer↔peer comm via `sessions_send` would create graph-shaped failure modes (peer A asks peer B for opinion, B's session is slow, A's tick blocks). Tick-path latency must stay deterministic.

**v2 candidates (NOT for POC, document for future):**
- **Read-only awareness:** Tessera publishes a `fleet_state` view (each peer's current positions, recent PnL) that any peer can SELECT. Peer is free to choose to use it or not (e.g., a vol-trader might check "is anyone else already long SPX vol" before sizing up). Read-only is safe; write-side coordination is not.
- **Correlation cap:** Tessera-enforced rule "no two peers may hold >50% notional overlap in the same symbol simultaneously." Rejected at the per-peer risk-check layer (peer requests a trade, runner checks fleet position from `fleet_state`, refuses if cap breached).
- **Pairs/spread peers:** explicit multi-leg strategies that intentionally need to coordinate (e.g., one peer goes long XLK while another goes short SPY, hedged pair). These are a class of strategy, not an instance of correlation control — design separately.

**Hard rule for v1:** the only inter-agent channel is **Tessera's published tables (`peer_allocations`)** and the **shared killswitch**. Everything else is each peer in its own bubble. If a peer wants peer-comm, it asks Tessera in the post-mortem `Asks` section, and Tessera escalates to main.

---

## 9. Design Question 9 — Fleet cap at 5

**Hard-coded check, two layers:**

1. **At spawn time (main-owned):** main, before running `openclaw agents add peer-X`, must verify `count(agentId matching /^peer-/) < 5`. Convention: main reads `~/.openclaw/openclaw.json` and counts. v1 has no automated enforcement at the Gateway level — relying on the human/main in the loop.
2. **At Tessera-orchestrator level:** Tessera's hourly sweep and Saturday leaderboard scripts will refuse to operate on more than 5 peers (sort by `peer_allocations.updated_utc`, take first 5, log a loud error and post to channel if it sees ≥6).

**Cap rationale:** per `MEMORY.md` north star "Tier 3 = 'quant team'... cap at 3-5" — Bar D codifies 5. Beyond 5:
- Manual review of weekly post-mortems gets unwieldy.
- Notional split drops below $20/peer (execution-noise floor).
- Coordination complexity (even with v1 "fully independent" design) starts to demand v2 correlation control we said we're not building yet.

**Beyond-5 escalation:** Cyrus may explicitly authorize >5 peers per request, but each authorization is a one-off, NEVER standing. If we hit "we want 6," that's the cue that Tier 3 has graduated and we should be designing **Tier 4 (quant fund)** — out of charter for this design doc.

---

## 10. Implementation outline

### 10.1 File/directory structure (NEW or MODIFIED)

```
/home/azureuser/.openclaw/
├── openclaw.json                                       # ADD agents.list entries + bindings (per §1)
└── agents/
    ├── trading-bench/
    │   └── workspace/
    │       ├── STOP_TRADING_TIER3                       # NEW, absent by default (§3)
    │       ├── peer_agents/                             # NEW dir, holds orchestrator code
    │       │   ├── __init__.py
    │       │   ├── killswitch.py                        # `check_tier3_killswitch()` helper
    │       │   ├── loss_budget.py                       # hourly sweep + per-tick self-check
    │       │   ├── allocations.py                       # publish/read peer_allocations table
    │       │   ├── postmortem_aggregator.py             # Saturday consolidator
    │       │   ├── peer_tick_wrapper.sh                 # template tick wrapper (per-peer copies use envsub)
    │       │   └── README.md                            # operator notes
    │       ├── runner/
    │       │   └── db.py                                # ADD tables: peer_allocations, peer_equity_snapshots, peer_pause_events
    │       └── reports/
    │           ├── TIER3_HARNESS_DESIGN_<this>.md       # this doc
    │           └── TIER3_LEADERBOARD_<week>.md          # Saturday output
    └── peer-alpha/                                      # NEW (POC peer, see §10.4)
        └── workspace/
            ├── AGENTS.md
            ├── SOUL.md
            ├── HANDOFF.md
            ├── MEMORY.md
            ├── memory/
            ├── reports/
            ├── strategy/                                # symlink → trading-bench/strategies/<assigned>
            ├── templates/postmortem.md                  # template referenced by §7 prompt
            ├── PAUSED                                   # absent at creation
            └── .env                                     # symlink → trading-bench/.env
```

### 10.2 OpenClaw config changes (defer until ready to stand up; design only here)

Single-file edit to `~/.openclaw/openclaw.json`:

```json5
{
  agents: {
    list: [
      // ... existing entries (main, trading-bench, job-search, etc.) unchanged ...
      {
        id: "peer-alpha",
        name: "Peer Alpha",
        workspace: "~/.openclaw/agents/peer-alpha/workspace",
        agentDir: "~/.openclaw/agents/peer-alpha/agent",
        // Model choice per main review (2026-05-29 tightening #5):
        // Trade hot path is shell-direct (no model cost). Weekly post-mortem turn uses
        // claude-sonnet-4 / gpt-5.4-mini class — reserve opus budget for actual strategy
        // decisions if/when a peer is assigned an LLM-decision strategy.
        model: { primary: "github-copilot/claude-sonnet-4" },
        // Lock down tools — no need for canvas, nodes, browser, etc.
        tools: {
          allow: ["read", "write", "edit", "exec", "process",
                  // sessions_send/history/list intentionally OMITTED per main review (2026-05-29 tightening #1):
                  // peers escalate via post-mortem `Asks` section read by Tessera, not by
                  // calling peer-to-peer or messaging main. Prevents drifted peer from spamming the org.
                  "memory_get", "memory_search", "message"],
          deny: ["browser", "canvas", "nodes", "tts", "image",
                 "sessions_send", "sessions_history", "sessions_list"],
        },
        identity: { name: "Peer Alpha", emoji: "🅰️" },
      },
      // peer-beta, peer-gamma, peer-delta, peer-epsilon: ditto, swap id+name+emoji
    ],
  },
  bindings: [
    // ... existing ...
    // Each peer gets its own Discord channel.
    // Channel IDs TBD — must be created by Cyrus before binding.
    { agentId: "peer-alpha",   match: { channel: "discord", peer: { kind: "direct", id: "<CHANNEL_ID_ALPHA>" } } },
    // ... beta/gamma/delta/epsilon ...
  ],
}
```

**Cron jobs (system crontab, same approach as Tessera's `cron_tick.sh`):**

```cron
# Per-peer tick (every 30min during NYSE for stocks; hourly for crypto). Example for alpha:
*/30 7-13 * * 1-5  /home/azureuser/.openclaw/agents/peer-alpha/workspace/tick.sh >> /home/azureuser/.openclaw/agents/peer-alpha/workspace/logs/tick.log 2>&1

# Tessera-side hourly loss-budget sweep:
3 * * * *  cd /home/azureuser/.openclaw/agents/trading-bench/workspace && python3 -m peer_agents.loss_budget >> logs/peer_loss_sweep.log 2>&1

# Tessera-side daily staleness check (08:00 PT):
0 8 * * *  cd /home/azureuser/.openclaw/agents/trading-bench/workspace && python3 -m peer_agents.staleness_check >> logs/peer_staleness.log 2>&1

# Per-peer weekly post-mortem (LLM agent-turn cron, NOT shell-direct). Friday 16:00 PT:
# Configured via openclaw cron add with --session "agent:peer-alpha:discord:channel:<id>"
#   and --system-event "Write your weekly post-mortem per workspace/templates/postmortem.md."

# Tessera-side Saturday consolidator (existing 09:00 PT leaderboard slot — extended to read peer post-mortems):
# (modify existing weekly leaderboard cron's prompt to also call peer_agents.postmortem_aggregator)
```

### 10.3 Code that lives in `workspace/peer_agents/`

**`killswitch.py`** (~40 lines):
- `is_tier3_halted() -> bool`: returns `True` if `STOP_TRADING_TIER3` file exists.
- `log_killswitch_trip(peer_id)`: appends to `logs/tier3_killswitch_trips.log`.
- `assert_clear_or_exit(peer_id)`: convenience function for tick wrappers.

**`loss_budget.py`** (~120 lines):
- `compute_drawdown(peer_id, db) -> float`: read equity snapshots since last allocation update, return drawdown %.
- `enforce_loss_budgets(db)`: hourly sweep entry point; iterates peers, trips PAUSED files as needed, inserts pause events, posts to channels.
- `pause_peer(peer_id, reason)` / `is_peer_paused(peer_id) -> bool`: helpers.
- Imports `runner.db` from trading-bench (path manipulation needed; document in README).

**`allocations.py`** (~60 lines):
- `get_peer_allocation(peer_id) -> float`: read for peer-side tick consumption.
- `set_peer_allocations(allocations: dict[str, float])`: Tessera-only writer; transactional UPDATE.
- `rebalance_equal_weight(active_peer_ids: list[str], fleet_cap_usd=100.0)`: default split.

**`postmortem_aggregator.py`** (~200 lines):
- `find_peer_postmortems(week: str) -> dict[peer_id, path]`: glob + parse.
- `parse_postmortem_metrics(path) -> dict`: ingest frontmatter/markdown into dict.
- `build_leaderboard(week: str) -> str`: returns markdown report.
- `digest_asks(week: str) -> str`: collect all `Asks` sections into a single block for Tessera to act on.

**`peer_tick_wrapper.sh`** (template, ~30 lines):
```bash
#!/usr/bin/env bash
set -euo pipefail
PEER_ID="${PEER_ID:?must be set in caller env}"
TB_ROOT="/home/azureuser/.openclaw/agents/trading-bench/workspace"
PEER_ROOT="/home/azureuser/.openclaw/agents/${PEER_ID}/workspace"
LOG="${PEER_ROOT}/logs/tick.log"
TIER3_KILLSWITCH="${TB_ROOT}/STOP_TRADING_TIER3"
PAUSED="${PEER_ROOT}/PAUSED"

mkdir -p "${PEER_ROOT}/logs"
echo "[$(date -u +%FT%TZ)] tick start peer=${PEER_ID}" >> "$LOG"

# Tier 3 killswitch (any peer/Tessera/Cyrus can trip)
if [ -f "$TIER3_KILLSWITCH" ]; then
  echo "[$(date -u +%FT%TZ)] tier3 killswitch active; noop" >> "$LOG"
  exit 0
fi

# Per-peer pause (loss-budget or manual)
if [ -f "$PAUSED" ]; then
  echo "[$(date -u +%FT%TZ)] peer paused; noop" >> "$LOG"
  exit 0
fi

# Defense in depth: self-check loss budget before any trade
cd "$TB_ROOT"
python3 -m peer_agents.loss_budget --self-check "$PEER_ID" || { echo "[$(date -u +%FT%TZ)] self-check tripped pause; noop" >> "$LOG"; exit 0; }

# Run the actual strategy tick (uses peer's symlinked strategy dir + DB-published allocation)
PEER_ID="$PEER_ID" python3 -m runner.peer_tick "$PEER_ID" >> "$LOG" 2>&1
```

**`runner/db.py` additions:** the three `peer_*` tables (§4), plus CRUD helpers, plus a migration step that creates them on next import (existing trading-bench DB module pattern).

### 10.4 Minimal POC: stand up ONE peer (peer-alpha), no live strategy

**Goal:** prove the harness works end-to-end without risking even paper PnL. peer-alpha will heartbeat, check the killswitch, log "no strategy assigned; noop", and emit a templated weekly post-mortem.

**Steps (concrete, ordered):**

1. **DB migration** — Tessera-side. Add tables to `runner/db.py`, run a one-shot migration (`python3 -m runner.db --migrate`). Verify with `sqlite3 tournament.db ".schema peer_allocations"`.
2. **Write `peer_agents/` module skeleton** — `killswitch.py`, `loss_budget.py` (stub with TODO for sweep logic), `allocations.py`, `postmortem_aggregator.py` (stub). All four files compile and unit tests pass on empty DB.
3. **Insert peer-alpha allocation row** — `INSERT INTO peer_allocations VALUES ('peer-alpha', 0.0, 25.0, now)`. Zero notional — peer is alive but can't trade even if it tried.
4. **Create peer-alpha workspace files** — Tessera generates the directory layout under `~/.openclaw/agents/peer-alpha/workspace/`. AGENTS.md says "You are peer-alpha. POC mode: no strategy assigned. Heartbeat, check killswitch, write weekly post-mortems. Do not attempt to trade." Symlink `.env`. NO symlink to `strategy/` yet (no strategy assigned).
5. **Write `peer_tick_wrapper.sh` for peer-alpha** as a literal file (not template-substituted yet) — wrapper logs `[heartbeat] peer-alpha alive` and exits. No `runner.peer_tick` call yet.
6. **Sit on it for 24h, no cron, no config change** — `bash ~/.openclaw/agents/peer-alpha/workspace/tick.sh` manually a few times. Verify killswitch trips it. Verify `PAUSED` trips it.
7. **Route through main:** sessions_send main with "Ready to register peer-alpha as a configured agent. Diff to openclaw.json: <paste>. Discord channel needed for binding. Requesting Cyrus confirmation." MAIN drives the config edit + restart; Tessera does NOT.
8. **After registration:** confirm peer-alpha shows in `openclaw agents list`, can be DMed in Discord. Test via `sessions_send(agentId="peer-alpha", message="Heartbeat test")`.
9. **Add cron** — system crontab, hourly heartbeat tick (NOT 30min — we're in dry-run, low frequency).
10. **POC success criteria:**
    - 48h continuous: tick wrapper fires hourly, logs heartbeats, no errors.
    - Killswitch trip → noop within one tick.
    - `PAUSED` trip → noop within one tick.
    - peer-alpha autonomously writes a `POSTMORTEM_<week>.md` on Friday EOD (LLM cron job; template-only since no trades).
    - Tessera Saturday consolidator picks up the empty post-mortem and posts a `TIER3_LEADERBOARD_<week>.md` showing peer-alpha at 0 trades.
11. **Only after POC passes:** consider assigning peer-alpha a real strategy (symlink in, set allocation to $20, raise tick frequency). That requires fresh Cyrus go per Bar D.1 (the strategy itself must have passed Bar A/B/C first).

### 10.5 What this design does NOT do (explicit scope cuts)

- No automated peer spawn/cull. All lifecycle ops route through main+Cyrus.
- No risk-parity / Sharpe-based dynamic reallocation. Equal-weight only at v1.
- No peer↔peer comm. Tessera-mediated only.
- No real-money path. Tier 3 is paper-only; real money is Bar E and is its own per-request gate.
- No Gateway-level fleet-cap enforcement. Convention + main-in-loop only.
- No automated pause-clear. Cyrus-only-lift, manually.
- No backtester integration (yet). Peers run live only; backtest validation is Bar A/B/C, gated upstream by trading-bench.
- No web UI / dashboard. Markdown in workspace + Discord one-liners are the entire surface.

---

## 11. Open questions for main / Cyrus

1. **Discord channel provisioning:** 5 peers = 5 new channels in Cyrus's Discord guild. Acceptable? Or should peers share a single `#tier3-peers` channel with prefix routing? (Affects `bindings` design.)
2. **Auth profile sharing:** all peers will hit the same Alpaca paper account. The per-agent `auth-profiles.json` model assumes per-agent auth. Plan: symlink each peer's `.env` to trading-bench's. OR copy the env. OR use OpenClaw's `agents.list[].auth` inheritance (need to check whether that's a thing). Need main's read on whether symlinking is kosher under OpenClaw's auth model.
3. **Cull window:** N=3 weeks proposed. Aggressive enough to clear bad strategies, lenient enough to absorb unlucky stretches? Bar D doesn't pin this — open to main's pushback.
4. **Per-peer model choice:** all peers default to `claude-opus-4.7` per Tessera's choice. Cheaper for an LLM-driven post-mortem-only peer? Could downgrade to `sonnet` / `gpt-5.4-mini` for the post-mortem agent turn (the tick wrapper is shell-direct, so model cost doesn't apply to the trading hot path).
5. **POC duration:** 48h proposed. Cyrus may want a full week of dry-run before assigning a strategy.

---

## 12. Verification checklist (when implementing later)

- [ ] `STOP_TRADING_TIER3` correctly halts all peer ticks within 1 tick interval.
- [ ] `PAUSED` per-peer halts only that peer, not others.
- [ ] Loss budget hourly sweep correctly drawdown-pauses a synthesized losing peer (test via fake equity snapshots).
- [ ] Per-tick self-check independently pauses without Tessera's involvement (kill Tessera processes, verify self-pause still works).
- [ ] Weekly post-mortem template renders for an empty trade history (peer-alpha POC).
- [ ] Tessera consolidator gracefully handles missing post-mortem (`[NO SELF-ASSESSMENT THIS WEEK]` tag).
- [ ] Cull-request flow exercised in dry-run (Tessera writes CULL_REQUEST_*.md, sessions_send to main, no actual deletion).
- [ ] Fleet-cap-5 refused by Tessera scripts if 6 peers appear.
- [ ] Killswitch clear requires manual Cyrus action; Tessera attempts to `rm` it produce an audit log line.
- [ ] Workspace files persist after peer retirement (move to `.retired/`, not `rm`).

---

_End of design doc._
