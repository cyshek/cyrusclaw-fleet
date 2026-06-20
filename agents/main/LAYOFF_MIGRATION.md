# LAYOFF_MIGRATION.md — OpenClaw Fleet Migration Playbook

_Prepared: 2026-06-19 | Status: Ready to execute on day-zero_

---

## TL;DR — What Needs to Change on Day Zero

| Dependency | Current (company) | Personal alternative |
|---|---|---|
| **LLM provider** | GitHub Copilot Enterprise (via company SSO) | GitHub Copilot Individual OR Anthropic API direct |
| **VM** | Azure `Standard_D4as_v7`, RG `personal-agents`, sub `4b2a3918-...`, westus2 | Hetzner CAX21 (ARM, Falkenstein) ~€5/mo |
| **GitHub repo** | ✅ Already personal — `cyshek/cyrusclaw-fleet` (public, main branch) | No action needed |
| **Discord bot** | ✅ Personal Discord server, personal bot token | No action needed |

---

## 1. Current Infrastructure Snapshot

### VM
- **Host:** `openclaw-vm`, Azure `Standard_D4as_v7` (4 vCPU AMD, 16 GB RAM), `westus2`
- **OS:** Ubuntu 22.04 LTS (Jammy), x64
- **Disk:** 64 GB Premium_LRS (OS disk), no data disks
- **Used:** ~26 GB of 62 GB (41% full)
- **Public IP:** `40.65.93.84`
- **Resource group:** `personal-agents`
- **Subscription:** `4b2a3918-407a-4f0f-902d-4808c58614e3`
- **Estimated cost:** ~$133/mo compute + ~$7-17 disk/net = **~$140-150/mo total**
  (Cyrus currently has a $150/mo Azure credit covering this)

### Model Config (from `~/.openclaw/openclaw.json`)
- **Primary model:** `github-copilot/claude-sonnet-4.6`
- **Fallback:** `github-copilot/claude-sonnet-4.6`, `github-copilot/gpt-5.5`
- **Image model:** `github-copilot/claude-opus-4.8`
- **Auth profile:** `github-copilot:github` — provider `github-copilot`, mode `token`
- **Token stored at:** `~/.openclaw/credentials/github-copilot.token.json`
  - Integration ID: `vscode-chat` — **this is a GitHub Copilot OAuth token, refreshed via the Copilot VS Code extension flow. It IS tied to the GitHub account that authorized it.** As long as you keep the same GitHub account (cyshek ✅), it MAY survive — but if the Copilot license was on the corporate account, it will expire immediately on termination.
- **Memory/embedding model:** `github-copilot/text-embedding-3-small` (all 8 agents)

### Keys Currently Set (`~/.openclaw/.env`)
| Key | Purpose | Portability |
|---|---|---|
| `DISCORD_BOT_TOKEN` | Discord channel for all agents | ✅ Personal Discord app — no action needed |
| `GITHUB_TOKEN` | GitHub PAT for fleet repo sync | ✅ Personal cyshek account PAT — verify it's a personal PAT, not enterprise SSO |
| `GITHUB_REPO` | Points to `cyshek/cyrusclaw-fleet` | ✅ Already personal |
| `OPENCLAW_GATEWAY_TOKEN` | Internal gateway auth | ✅ Local — no action needed |
| `RESIDENTIAL_PROXY` | Web scraping proxy | Verify account ownership |
| `CAPSOLVER_API_KEY` | CAPTCHA solving | Verify account ownership |
| `TWOCAPTCHA_API_KEY` | CAPTCHA solving (fallback) | Verify account ownership |
| `ENABLE_CAPSOLVER` | Feature flag | N/A |
| `SIRI_WEBHOOK_TOKEN` | iOS Siri webhook | ✅ Personal |
| `SIRI_DISCORD_LOG_CHANNEL` | Discord channel ID | ✅ Personal |
| `SIRI_TTS_RATE` / `SIRI_TTS_VOICE` | TTS config | ✅ Local |

### Key in `~/.openclaw/secrets.env`
| Key | Purpose |
|---|---|
| `OPENCLAW_GATEWAY_TOKEN` | Internal gateway token (duplicated from .env) |

_(Azure service principal `~/.openclaw/secrets/azure-sp.env` is NOT needed post-migration)_

---

## 2. Estimated Token Usage

Based on subagent run counts from `openclaw.sqlite`:

| Period | Subagent runs |
|---|---|
| Jun 8 (active day) | 58 |
| Jun 9 (active) | 46 |
| Jun 19 (active) | 45 |
| Jun 15 (moderate) | 30 |
| Jun 14 (moderate) | 29 |
| Jun 7 | 34 |
| Quiet days (Jun 18, 13) | 1–3 |

**Rough daily pattern:** ~5-15 cron-driven "isolated" runs + variable interactive sessions
- ~37 enabled cron jobs (daily distills, watchdogs, trading-bench reviews, etc.)
- Active sessions: ~20-60 subagent runs/day on busy days, ~1-10 on quiet days

**Token burn estimate (rough):**
- Each subagent run ≈ 10K-80K tokens (cron distills are heavier)
- Cron-only baseline: ~20-30 isolated runs/day × 20K avg ≈ **400K-600K tokens/day**
- Heavy interactive days: add 500K-2M tokens for multi-step tasks
- **Weekly estimate: ~5-15M tokens total input+output**
- **Monthly estimate: ~20-60M tokens**

> **Cost implication:** At direct Anthropic API rates for Claude Sonnet 4.5 ($3/MTok in, $15/MTok out), 30M tokens/month at ~80% input ≈ $72-$180/mo for LLM alone. GitHub Copilot Individual ($10/mo or $19/mo Pro+) is **dramatically cheaper** if the usage fits within their limits.

---

## 3. Migration Option A: GitHub Copilot Individual

### What changes
| Item | Action |
|---|---|
| GitHub Copilot license | Sign up for GitHub Copilot Individual or Pro ($10/mo or $19/mo) on personal `cyshek` account |
| OAuth re-auth | Re-run `openclaw auth login --provider github-copilot` from the VM to get a fresh token tied to `cyshek` |
| `openclaw.json` | **No model string changes needed** — same `github-copilot/` prefix, same models |

### openclaw.json changes required: **NONE**
The current config already uses:
```json
"model": { "primary": "github-copilot/claude-sonnet-4.6" }
"imageModel": { "primary": "github-copilot/claude-opus-4.8" }
"memorySearch": { "provider": "github-copilot", "model": "text-embedding-3-small" }
```
These model IDs work on personal Copilot too, assuming Anthropic models remain in the Copilot catalog.

### Steps
```bash
# 1. On day zero, re-auth from the VM
openclaw auth login --provider github-copilot

# 2. Follow the device-code flow (opens github.com/login/device on your personal cyshek account)
# 3. Confirm auth works
openclaw doctor

# 4. No restart needed — auth reload is live
```

### Caveats
- **GitHub Copilot rate limits apply.** Heavy cron activity (20-60 subagent runs/day) may hit limits on the Individual tier.
- Model availability: `claude-opus-4.8` and `gpt-5.5` availability on Individual tier may differ from Enterprise.
- If rate-limited, consider reducing cron frequency (trading-bench weekly is fine; daily distills fine).

### Cost
| Item | Monthly |
|---|---|
| GitHub Copilot Pro ($19/mo with more models) | $19 |
| OR GitHub Copilot Individual ($10/mo) | $10 |
| Hetzner CAX21 VM (see §5) | ~€5 (~$5.50) |
| **Total** | **~$15-25/mo** |

---

## 4. Migration Option B: Direct Anthropic API Key

### What changes
This requires replacing the `github-copilot` provider with Anthropic's native API.

### openclaw.json changes required

**Step 1: Add the Anthropic provider plugin**
```json
// In plugins.entries:
"anthropic": {
  "enabled": true,
  "config": {
    "apiKey": {
      "source": "env",
      "provider": "default",
      "id": "ANTHROPIC_API_KEY"
    }
  }
}
```

**Step 2: Add key to `.env`**
```bash
echo 'ANTHROPIC_API_KEY=sk-ant-...' >> ~/.openclaw/.env
```

**Step 3: Update all model references fleet-wide**

In `agents.defaults` and in EVERY agent's `model` block:
```json
// Before:
"primary": "github-copilot/claude-sonnet-4.6"
"fallbacks": ["github-copilot/claude-sonnet-4.6", "github-copilot/gpt-5.5"]

// After (Anthropic direct):
"primary": "anthropic/claude-sonnet-4-5"
"fallbacks": ["anthropic/claude-sonnet-4-5", "anthropic/claude-haiku-3-5"]
```

**Step 4: Update imageModel**
```json
// Before:
"imageModel": { "primary": "github-copilot/claude-opus-4.8" }

// After:
"imageModel": { "primary": "anthropic/claude-opus-4-5" }
```

**Step 5: Update memory/embedding provider**
The current `github-copilot/text-embedding-3-small` embedding won't work without Copilot. Options:
- Switch to `openai` provider with a personal OpenAI key (text-embedding-3-small is $0.02/MTok — essentially free at this scale)
- Or: switch to a local embedding model if available

```json
// In all agents' memorySearch:
"memorySearch": {
  "provider": "openai",
  "model": "text-embedding-3-small",
  "apiKey": { "source": "env", "id": "OPENAI_API_KEY" }
}
```

**Full model path diff** (the models that need changing in `openclaw.json`):
- `agents.defaults.model.primary` → `anthropic/claude-sonnet-4-5`
- `agents.defaults.model.fallbacks` → `["anthropic/claude-sonnet-4-5", "anthropic/claude-haiku-3-5"]`
- `agents.defaults.imageModel.primary` → `anthropic/claude-opus-4-5`
- Every agent in `agents.list[*].model.primary` and `.fallbacks` (8 agents × 2 fields = 16 edits)
- Every agent's `memorySearch.provider` → `openai`, add `OPENAI_API_KEY`

### Cost estimate at current usage (~30M tokens/month)
| Model | Input rate | Output rate | Monthly est. (80% in, 20% out) |
|---|---|---|---|
| Claude Sonnet 4.5 | $3/MTok | $15/MTok | ~$72-$175 |
| Claude Haiku 3.5 (lighter fallback) | $0.80/MTok | $4/MTok | ~$20-$50 |
| OpenAI text-embedding-3-small | $0.02/MTok | n/a | ~$0.60-$1.20 |
| **Total** | | | **~$75-180/mo LLM** |

Combined with Hetzner CAX21 (~$5.50):
**Total: ~$80-185/mo** — considerably more than Option A, but zero dependency on any company service.

---

## 5. VM Migration: Azure → Hetzner CAX21

### Why CAX21
- ARM (Ampere A1) — **4 vCPU, 8 GB RAM** → half the RAM of current D4as_v7 (16 GB)
- **~€4.51/mo** (~$5/mo) — vs ~$140/mo Azure
- Falkenstein, Germany (EU) — add Ashburn VA node if latency matters
- ⚠️ **RAM downgrade is real:** current VM uses ~3.6 GB active + 4 GB buffer/cache with Chrome + node running. CAX21's 8 GB is workable but tight. Consider **CX22** (2 vCPU, 4 GB, ~€3.29/mo) only if you reduce agents.

> **Recommendation:** Start with **CAX21 (4 vCPU, 8 GB)** — monitor, and if tight upgrade to **CAX31 (8 vCPU, 16 GB, ~€10/mo)** for identical resources to today at 1/14th the price.

### Pre-migration backup checklist
Everything that needs to be preserved is under `~/.openclaw/`:

```bash
# CRITICAL — back up everything under .openclaw
# Total size estimate: ~26 GB disk used, but most is logs/cache — essentials are much smaller

# Core config
~/.openclaw/openclaw.json          # Main config
~/.openclaw/.env                   # API keys / tokens
~/.openclaw/secrets.env            # Gateway token
~/.openclaw/secrets/               # Azure SP, spend scripts (optional post-migration)
~/.openclaw/credentials/           # Copilot token, Discord pairing

# Agent workspaces (the important stuff)
~/.openclaw/workspace/             # main agent workspace (MEMORY.md, AGENTS.md, daily logs, etc.)
~/.openclaw/agents/                # all 8 peer agent workspaces (job-search, trading-bench, etc.)
~/.openclaw/shared-memory/         # shared fleet memory

# Systemd service file
~/.config/systemd/user/openclaw-gateway.service
~/.config/systemd/user/openclaw-gateway-watchdog.service
~/.config/systemd/user/openclaw-gateway-watchdog.timer

# Scripts
~/.openclaw/bin/                   # All custom scripts (voice-note.sh, sync-agents.sh, etc.)

# SQLite state DB (optional — can regenerate, but saves cron/session state)
~/.openclaw/state/openclaw.sqlite
```

**Exclusions (skip these — they're large and regenerable):**
```
~/.openclaw/cache/          (embedding cache — will rebuild)
~/.openclaw/logs/           (optional — archive separately if wanted)
~/.openclaw/browser/        (Chrome user data — will recreate)
~/.openclaw/media/          (media blobs)
~/.openclaw/tmp/
```

### Migration steps

#### Phase 1: Provision Hetzner VM
```bash
# 1. Create account at hetzner.com
# 2. Create project "openclaw-fleet"
# 3. Create server:
#    - Type: CAX21 (ARM, 4 vCPU, 8 GB RAM)
#    - Image: Ubuntu 24.04 (or 22.04 if you want parity)
#    - Location: Falkenstein or Ashburn (US East)
#    - SSH key: add your public key
#    - Firewall: allow SSH (22), deny everything else (gateway binds loopback only)
# 4. Note the new public IP
```

#### Phase 2: Rsync from Azure → Hetzner (while Azure is still live)
```bash
# From the Azure VM (or from your local machine as a relay):

NEW_IP="<hetzner-ip>"

# First: install openclaw on the new VM
ssh azureuser@$NEW_IP "curl -fsSL https://openclaw.dev/install.sh | sudo bash"

# Then sync all critical data:
rsync -avz --exclude='cache/' --exclude='browser/' --exclude='logs/' --exclude='media/' --exclude='tmp/' \
  ~/.openclaw/ azureuser@$NEW_IP:~/.openclaw/

# Sync bin/ scripts
rsync -avz ~/.openclaw/bin/ azureuser@$NEW_IP:~/.openclaw/bin/

# Sync systemd units
rsync -avz ~/.config/systemd/user/ azureuser@$NEW_IP:~/.config/systemd/user/
```

#### Phase 3: Configure and start on Hetzner
```bash
ssh azureuser@$NEW_IP

# 1. Re-enable systemd user units
systemctl --user daemon-reload
systemctl --user enable openclaw-gateway.service
systemctl --user enable openclaw-gateway-watchdog.timer
loginctl enable-linger azureuser   # keep gateway alive after SSH disconnect

# 2. Re-auth GitHub Copilot (token doesn't transfer)
openclaw auth login --provider github-copilot

# 3. Start gateway
systemctl --user start openclaw-gateway.service

# 4. Run doctor
openclaw doctor

# 5. Test Discord (send a test message from your Discord channel)

# 6. Verify crons are loaded
openclaw cron list
```

#### Phase 4: DNS / IP updates
```bash
# Update anywhere the Azure public IP (40.65.93.84) was used:
# - Any port-forwards or tunnels (cloudflared? Check ~/.openclaw/state/cloudflared.log)
# - SIRI_WEBHOOK_TOKEN endpoint if it's IP-based
# - Discord bot webhook if applicable

# Check if cloudflared tunnel is running (would survive IP change automatically):
cat ~/.openclaw/state/cloudflared.log | tail -5
```

#### Phase 5: Verify, then decommission Azure
```bash
# Run for 24-48 hours on Hetzner with all agents active
# Confirm: crons firing, Discord working, all 8 agents responsive
# Then: stop Azure VM (don't delete yet — pause 1 week)
# After 1 week clean: delete Azure VM + RG personal-agents
```

### Hetzner firewall config (minimal)
```
Inbound: allow TCP 22 (SSH) from your IPs only
Inbound: allow TCP 18789 ONLY from loopback (gateway binds loopback — don't expose)
Outbound: all allowed
```

---

## 6. GitHub Repo — Already Done ✅

- **Repo:** `https://github.com/cyshek/cyrusclaw-fleet` (public, `main` branch)
- **Auto-sync cron:** `nightly-github-sync` (2am PST daily) — rsync all 8 agent workspaces → monorepo → push
- **No action needed** on day zero for the repo itself

**One action to verify:** Confirm `GITHUB_TOKEN` in `.env` is a **Personal Access Token from the cyshek personal account**, not a company-managed token or enterprise SSO token. A corporate SSO GitHub PAT will be revoked on termination.

```bash
# Verify token owner (will print account info):
curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user | python3 -c "import sys,json; d=json.load(sys.stdin); print('Account:', d['login'], '| Type:', d['type'])"
# Should print: Account: cyshek | Type: User
```

---

## 7. Cost Comparison Summary

| Setup | LLM | VM | Other | Monthly Total |
|---|---|---|---|---|
| **Current (company)** | GitHub Copilot Enterprise (company-paid ≈ $0 to you) | Azure D4as_v7 ~$140 (Azure credit covers) | ~$0 | **~$0 out of pocket** |
| **Option A: GH Copilot Individual + Hetzner** | GitHub Copilot Pro $19/mo | Hetzner CAX21 ~$5.50 | misc ~$2 | **~$27/mo** |
| **Option B: Anthropic API + Hetzner** | Anthropic API ~$75-180/mo | Hetzner CAX21 ~$5.50 | OpenAI embed ~$1 | **~$80-185/mo** |
| **Option B (light): Anthropic Haiku fallback + Hetzner** | Anthropic (Haiku-heavy) ~$25-50/mo | Hetzner CAX21 ~$5.50 | $1 | **~$30-55/mo** |

**Recommendation:** Start with **Option A** (GitHub Copilot Individual + Hetzner). If rate-limited, move to Option B with a Haiku-heavy fallback strategy.

---

## 8. Day-Zero Checklist

```
□ BEFORE termination:
  □ Check GITHUB_TOKEN owner (curl -s api.github.com/user)
  □ Verify RESIDENTIAL_PROXY / CAPSOLVER / TWOCAPTCHA account ownership
  □ Sign up for GitHub Copilot Individual on cyshek account (takes 5 min)

□ DAY ZERO (the moment access is cut):
  □ openclaw auth login --provider github-copilot  (re-auth to personal cyshek account)
  □ openclaw doctor  (verify all agents healthy)
  □ Test a message in each Discord channel
  □ The rest can wait — agents keep running on the Azure VM until you migrate

□ WEEK ONE:
  □ Provision Hetzner CAX21
  □ Rsync ~/.openclaw/ to new VM
  □ Start openclaw on Hetzner
  □ Re-auth Copilot on Hetzner
  □ Run 24-48h parallel (both VMs up)
  □ Cut over Discord bot to Hetzner
  □ Shut down Azure VM (don't delete yet)

□ WEEK TWO:
  □ Confirm Hetzner stable
  □ Delete Azure VM + RG personal-agents
  □ Remove Azure SP from ~/.openclaw/secrets/
  □ Celebrate ~$115/mo savings

□ OPTIONAL — if Copilot rate-limited:
  □ Add ANTHROPIC_API_KEY to .env
  □ Edit openclaw.json model strings per Option B instructions above
  □ Add OPENAI_API_KEY for embeddings
  □ Restart gateway (only needed for plugin config changes)
```

---

## 9. Key Files Reference

| File | Purpose | Action on migration |
|---|---|---|
| `~/.openclaw/openclaw.json` | Main config | Backup + update model strings if going Anthropic |
| `~/.openclaw/.env` | API keys | Re-verify all key ownership; copy to new VM |
| `~/.openclaw/secrets.env` | Gateway token | Copy to new VM |
| `~/.openclaw/credentials/github-copilot.token.json` | Copilot OAuth token | Will need re-auth; don't copy |
| `~/.openclaw/workspace/` | main agent memory/files | rsync to new VM |
| `~/.openclaw/agents/` | all 8 peer workspaces | rsync to new VM |
| `~/.openclaw/shared-memory/` | Fleet-wide shared memory | rsync to new VM |
| `~/.openclaw/bin/` | Custom scripts | rsync to new VM |
| `~/.config/systemd/user/` | systemd service files | rsync + daemon-reload on new VM |
| `~/.openclaw/state/openclaw.sqlite` | Sessions, crons, state | rsync (or let rebuild — crons recreate from DB) |

---

_This playbook is self-contained. Execute §8 checklist on day zero, follow §5 for VM migration in week one._
