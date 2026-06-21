# MIGRATION_RUNBOOK.md — My Execution Plan for Layoff Day
_This is MY notes — what I run, in order, when Cyrus says "I got laid off."_
_Last updated: 2026-06-20_

## When Cyrus tells me he got laid off:

### STEP 1 — Re-auth Copilot (5 min, do FIRST before anything else)
The GitHub Copilot Enterprise token will be dead or dying. Re-auth to his personal account immediately so agents stay live.

```bash
openclaw auth login --provider github-copilot
```
This prints a device code + URL. Tell Cyrus:
> "Go to https://github.com/login/device and enter code XXXX-XXXX. Sign in as **cyshek** (personal account, NOT work account)."

Once he approves, confirm:
```bash
openclaw doctor
```
All agents should still be responsive. **The fleet keeps running on Azure while we migrate — no rush after this.**

---

### STEP 2 — Provision Hetzner VM (10 min)
Tell Cyrus to:
> "Go to hetzner.com, create an account, and add a payment method. Tell me when done."

Once he has an account, get his API token from https://console.hetzner.cloud → Security → API Tokens → Create Token (Read & Write).

Then I provision via API:
```bash
# Set token from Cyrus
HETZNER_TOKEN="<token-from-cyrus>"

# Upload his SSH key
SSH_KEY=$(cat ~/.ssh/id_rsa.pub)

curl -X POST https://api.hetzner.cloud/v1/ssh_keys \
  -H "Authorization: Bearer $HETZNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"openclaw-vm\",\"public_key\":\"$SSH_KEY\"}"

# Get the SSH key ID from response, then create server:
curl -X POST https://api.hetzner.cloud/v1/servers \
  -H "Authorization: Bearer $HETZNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "openclaw-vm",
    "server_type": "cax21",
    "image": "ubuntu-22.04",
    "location": "ash",
    "ssh_keys": ["openclaw-vm"],
    "firewalls": []
  }'
# Note the new server IP from the response
```

---

### STEP 3 — Install OpenClaw on new VM (5 min)
```bash
NEW_IP="<ip-from-step-2>"

ssh root@$NEW_IP "apt-get update -q && apt-get install -y rsync && \
  curl -fsSL https://openclaw.dev/install.sh | sudo bash && \
  useradd -m -s /bin/bash azureuser && \
  mkdir -p /home/azureuser/.ssh && \
  cp /root/.ssh/authorized_keys /home/azureuser/.ssh/ && \
  chown -R azureuser:azureuser /home/azureuser/.ssh"
```

---

### STEP 4 — Rsync everything from Azure → Hetzner (10-15 min)
```bash
NEW_IP="<ip-from-step-2>"

rsync -avz --progress \
  --exclude='cache/' \
  --exclude='browser/' \
  --exclude='logs/' \
  --exclude='media/' \
  --exclude='tmp/' \
  --exclude='.browser-data/' \
  --exclude='.browser-contexts/' \
  ~/.openclaw/ azureuser@$NEW_IP:~/.openclaw/

rsync -avz ~/.config/systemd/user/openclaw-gateway* \
  azureuser@$NEW_IP:~/.config/systemd/user/
```

---

### STEP 5 — Start OpenClaw on Hetzner (5 min)
```bash
ssh azureuser@$NEW_IP << 'EOF'
sudo loginctl enable-linger azureuser
systemctl --user daemon-reload
systemctl --user enable openclaw-gateway.service
systemctl --user enable openclaw-gateway-watchdog.timer
systemctl --user start openclaw-gateway.service
sleep 5
openclaw doctor
openclaw cron list | head -20
EOF
```

Then re-auth Copilot ON THE NEW VM:
```bash
ssh azureuser@$NEW_IP "openclaw auth login --provider github-copilot"
```
Tell Cyrus the device code again — same approval flow.

---

### STEP 6 — Verify all 8 agents healthy (5 min)
```bash
ssh azureuser@$NEW_IP "openclaw agents list"
```
Send a test message in Discord from each agent channel. Confirm responses.

Check crons loaded:
```bash
ssh azureuser@$NEW_IP "openclaw cron list | wc -l"
# Should be ~37 jobs
```

---

### STEP 7 — Run parallel for 24-48h
Keep Azure VM running alongside Hetzner for 1-2 days. Monitor Hetzner. If anything breaks, Azure is still there as fallback.

To pause Azure (stop billing without deleting):
```bash
az vm deallocate --resource-group personal-agents --name openclaw-vm
```

---

### STEP 8 — Cut over Discord bot (2 min)
The Discord bot token is the same — no change needed. But if there are any webhooks pointing to the Azure IP (40.65.93.84), update them to the new Hetzner IP.

Check:
```bash
grep -r "40.65.93.84" ~/.openclaw/ 2>/dev/null
```

---

### STEP 9 — Decommission Azure (when stable)
After 1 week on Hetzner with no issues:
```bash
az group delete --name personal-agents --yes --no-wait
```
Tell Cyrus to cancel Azure subscription at portal.azure.com if the credit runs out / isn't needed.

---

## ⭐ Cyrus's 3 jobs (tell him ONLY these when he says he got laid off):
1. 🖱️ Go to github.com/login/device and enter the code I give you (x2 — once now, once after we move to Hetzner)
2. 🖱️ Sign up at hetzner.com + add a payment method
3. 🖱️ Give me the Hetzner API token (console.hetzner.cloud → Security → API Tokens → Create Token, Read+Write)

**That's it. Everything else is mine.**

---

## Cost after migration
| Item | Monthly |
|---|---|
| GitHub Copilot Pro | $19 |
| Hetzner CAX21 | ~$5.50 |
| **Total** | **~$24.50** |

---

## Key files for reference
- `LAYOFF_MIGRATION.md` — full technical details + Option B (Anthropic API) if Copilot rate-limits
- `MIGRATION_GUIDE_HETZNER_COPILOT.md` — Cyrus-facing step-by-step
- `OpenClaw_Migration_Guide.docx` — same, for Google Drive
- Azure VM: `Standard_D4as_v7`, RG `personal-agents`, `westus2`, IP `40.65.93.84`
