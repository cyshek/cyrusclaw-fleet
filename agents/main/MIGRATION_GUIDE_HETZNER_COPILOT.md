# MIGRATION GUIDE — GitHub Copilot Individual + Hetzner CAX21
_Break-glass doc. Azure IP: `40.65.93.84` | Target: Hetzner CAX21 ~$5.50/mo + Copilot Pro $19/mo = ~$27/mo_

---

## 1. Before You Lose Access ⏱ ~10 min

Do this while still employed. Once you're cut, some of these become harder.

**1.1** 🖱️ Sign up for **GitHub Copilot Pro** on your personal `cyshek` account: https://github.com/settings/copilot
→ Pick "Pro" ($19/mo) for the full model catalog including Claude and GPT-5.

**1.2** Verify your GitHub PAT is personal (not corporate SSO):
```bash
curl -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['login'], d['type'])"
# Must print: cyshek  User
```
🔑 If it prints a corporate org or fails, create a new PAT at https://github.com/settings/tokens and update `~/.openclaw/.env`.

**1.3** Verify third-party API keys are on personal accounts (just check the dashboards):
- 🖱️ `RESIDENTIAL_PROXY` — log in and confirm it's a personal subscription
- 🖱️ `CAPSOLVER_API_KEY` — https://dashboard.capsolver.com
- 🖱️ `TWOCAPTCHA_API_KEY` — https://2captcha.com/enterpage

**1.4** Take a backup snapshot right now (optional but safe):
```bash
tar -czf ~/openclaw-backup-$(date +%Y%m%d).tar.gz \
  --exclude='~/.openclaw/cache' --exclude='~/.openclaw/browser' \
  --exclude='~/.openclaw/logs' --exclude='~/.openclaw/media' \
  ~/.openclaw/ ~/.config/systemd/user/openclaw-gateway*
```

---

## 2. Day Zero ⏱ ~15 min
_The moment SSO cuts. Everything is still running on the Azure VM — just re-auth Copilot._

**2.1** SSH into the existing VM:
```bash
ssh azureuser@40.65.93.84
```

**2.2** Re-authenticate GitHub Copilot to your personal `cyshek` account:
```bash
openclaw auth login --provider github-copilot
# Follow the device-code flow — opens github.com/login/device
# Sign in as cyshek (personal), not corporate
```

**2.3** Verify everything is healthy:
```bash
openclaw doctor
```

**2.4** 🖱️ Send a test message in your Discord channel to confirm agents respond.

**2.5** Check all crons are still queued:
```bash
openclaw cron list
```

✅ Done. Agents are live. Hetzner migration can happen this week at your own pace.

---

## 3. Week One: Move to Hetzner ⏱ ~45 min total

### 3.1 Provision the VM (~10 min)

**3.1.1** 🖱️ Create account at https://hetzner.com → New Project: `openclaw-fleet`

**3.1.2** 🖱️ Create server:
- Type: **CAX21** (ARM, 4 vCPU, 8 GB RAM, ~€4.51/mo)
- Image: **Ubuntu 22.04**
- Location: Falkenstein (EU) or Ashburn (US-East)
- SSH key: paste your public key (`cat ~/.ssh/id_rsa.pub` or `~/.ssh/id_ed25519.pub`)
- Firewall: allow TCP 22 inbound only; deny everything else inbound

**3.1.3** Note the new IP. Set it as a variable for the rest of this guide:
```bash
NEW_IP="<hetzner-ip-here>"
```

**3.1.4** Install OpenClaw on the new VM:
```bash
ssh root@$NEW_IP "curl -fsSL https://openclaw.dev/install.sh | sudo bash && useradd -m -s /bin/bash azureuser"
```

---

### 3.2 Rsync Data (~10 min)

Run from the **Azure VM** (`40.65.93.84`):

```bash
# Core data — excludes caches, browser profile, raw logs, media blobs
rsync -avz --progress \
  --exclude='cache/' --exclude='browser/' --exclude='logs/' \
  --exclude='media/' --exclude='tmp/' \
  ~/.openclaw/ azureuser@$NEW_IP:~/.openclaw/

# Custom scripts
rsync -avz ~/.openclaw/bin/ azureuser@$NEW_IP:~/.openclaw/bin/

# Systemd service files
rsync -avz ~/.config/systemd/user/openclaw-gateway* \
  azureuser@$NEW_IP:~/.config/systemd/user/
```

---

### 3.3 Start OpenClaw on Hetzner (~10 min)

```bash
ssh azureuser@$NEW_IP

# Fix permissions on scripts
chmod +x ~/.openclaw/bin/*.sh

# Enable systemd lingering (keep gateway alive after SSH disconnect)
sudo loginctl enable-linger azureuser

# Load and enable service files
systemctl --user daemon-reload
systemctl --user enable openclaw-gateway.service
systemctl --user enable openclaw-gateway-watchdog.timer

# Re-auth Copilot (token doesn't transfer — must re-do on new machine)
openclaw auth login --provider github-copilot
# Follow device-code flow again → sign in as cyshek

# Start the gateway
systemctl --user start openclaw-gateway.service

# Verify
openclaw doctor
openclaw cron list
```

---

### 3.4 Parallel Run + Cut Over (~15 min)

**3.4.1** Run **both VMs** for 24–48 hours. Watch Hetzner for errors:
```bash
journalctl --user -u openclaw-gateway -f
```

**3.4.2** 🖱️ When Hetzner looks stable, update your Discord bot settings if you hard-coded the Azure IP anywhere in webhooks. (The bot token itself is already portable — no change needed there.)

**3.4.3** Stop the Azure VM (don't delete yet):
```bash
# From local machine or Azure Portal:
az vm deallocate --resource-group personal-agents --name openclaw-vm
# OR just stop it from the Azure Portal — no CLI needed
```

---

## 4. Wrap Up

**4.1** Wait 1 week. If Hetzner is solid, delete the Azure VM:
```bash
# 🖱️ Azure Portal → Resource Groups → personal-agents → Delete resource group
# Type "personal-agents" to confirm
```
Or via CLI:
```bash
az group delete --name personal-agents --yes --no-wait
```

**4.2** 🖱️ Cancel the Azure subscription credit / remove billing method if no longer needed:
→ https://portal.azure.com → Subscriptions → `4b2a3918-407a-4f0f-902d-4808c58614e3`

**4.3** Clean up stale Azure secrets from the new VM:
```bash
rm -rf ~/.openclaw/secrets/azure-sp.env
```

**4.4** Confirm monthly cost:
| Item | Monthly |
|---|---|
| GitHub Copilot Pro | $19 |
| Hetzner CAX21 | ~$5.50 |
| **Total** | **~$24.50** |
| **vs. Azure today** | ~$140–150 |
| **Monthly savings** | **~$115** |

---

## Appendix: If Copilot Rate-Limits You

Add Anthropic as a fallback. Edit `~/.openclaw/openclaw.json` — change model strings from:
```
github-copilot/claude-sonnet-4.6  →  anthropic/claude-sonnet-4-5
github-copilot/claude-opus-4.8    →  anthropic/claude-opus-4-5
```
And add to `~/.openclaw/.env`:
```bash
ANTHROPIC_API_KEY=sk-ant-...       # 🔑 from console.anthropic.com
OPENAI_API_KEY=sk-...              # 🔑 for embeddings (text-embedding-3-small, ~$1/mo)
```
Then restart: `systemctl --user restart openclaw-gateway.service`

---

_Last updated: 2026-06-19 | Current Azure IP: 40.65.93.84 | Hetzner target: CAX21 (4 vCPU / 8 GB / ~€4.51/mo)_
