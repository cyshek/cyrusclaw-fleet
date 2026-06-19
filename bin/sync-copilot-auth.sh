#!/usr/bin/env bash
# sync-copilot-auth.sh — propagate main's github-copilot:github credential to all peer agents.
#
# WHY THIS EXISTS (investigated 2026-06-10, see workspace/memory/2026-06-10.md):
#   Each agent stores its model credential in its OWN agents/<id>/agent/auth-profiles.json.
#   They are independent files (NOT shared). Symlinking them to main's file is UNSAFE:
#   the OpenClaw atomic JSON writer reads with O_NOFOLLOW (refuses to follow symlinks) and
#   writes via temp-file + rename that rm's any symlink it finds (dist/json-files-*.js).
#   Official guidance: "copy auth-profiles.json instead of sharing the entire agentDir."
#   So the supported model is: ONE canonical source (main), copied out to peers.
#
#   The credential is a long-lived `ghu_` GitHub OAuth token (mode:token). It does NOT
#   rotate per-call (the short-lived Copilot *API* token derived from it lives in
#   auth-state/memory, NOT in auth-profiles.json — auth-profiles.json mtime stays stable).
#   So peers only go stale if the ghu_ token itself is RE-ISSUED. When that happens,
#   re-auth main ONCE, then run THIS script to fan the new token out to every peer.
#
# WHAT IT DOES:
#   - Reads the github-copilot:github profile from main's auth-profiles.json (source of truth).
#   - For each peer, backs up its existing auth-profiles.json (.bak-<ts>) and writes a copy
#     of main's profile block. Does NOT touch auth-state.json (that is per-agent runtime state
#     — usage stats / failure cooldowns — and MUST stay independent).
#   - chmod 600, chown to the invoking user. Idempotent: skips a peer already byte-identical.
#
# USAGE:
#   /home/azureuser/.openclaw/bin/sync-copilot-auth.sh            # apply
#   /home/azureuser/.openclaw/bin/sync-copilot-auth.sh --dry-run  # show what would change
#
# DOES NOT restart the gateway and DOES NOT delete anything (only .bak copies + overwrites).

set -euo pipefail

ROOT="/home/azureuser/.openclaw/agents"
MAIN_PROFILE="$ROOT/main/agent/auth-profiles.json"
PEERS=(job-search making-money trading-bench travel openclaw-updates resume-tailor interview-prep)
TS="$(date +%Y%m%d-%H%M%S)"
DRY=0
[[ "${1:-}" == "--dry-run" ]] && DRY=1

if [[ ! -f "$MAIN_PROFILE" ]]; then
  echo "FATAL: main profile not found at $MAIN_PROFILE" >&2
  exit 1
fi

# Sanity: main must actually contain the github-copilot:github token profile.
if ! python3 -c "import json,sys; d=json.load(open('$MAIN_PROFILE')); sys.exit(0 if d.get('profiles',{}).get('github-copilot:github',{}).get('type')=='token' and d['profiles']['github-copilot:github'].get('token') else 1)"; then
  echo "FATAL: main profile does not contain a valid github-copilot:github token. Re-auth main first:" >&2
  echo "       openclaw models auth login-github-copilot --agent main   (TTY)" >&2
  exit 1
fi

MAIN_MD5="$(md5sum "$MAIN_PROFILE" | awk '{print $1}')"
echo "Source (main) auth-profiles.json md5=$MAIN_MD5  ($(stat -c '%s bytes, mtime %y' "$MAIN_PROFILE"))"
echo "Mode: $([[ $DRY == 1 ]] && echo DRY-RUN || echo APPLY)"
echo

changed=0
for p in "${PEERS[@]}"; do
  dst="$ROOT/$p/agent/auth-profiles.json"
  if [[ ! -e "$dst" ]]; then
    echo "  $p: MISSING ($dst) — would create"
    if [[ $DRY == 0 ]]; then
      mkdir -p "$(dirname "$dst")"
      cp -p "$MAIN_PROFILE" "$dst"; chmod 600 "$dst"; chown "$(id -un):$(id -gn)" "$dst" 2>/dev/null || true
      echo "    created."
    fi
    changed=$((changed+1)); continue
  fi
  # Refuse to write through a symlink (the runtime would destroy it anyway; flag it loudly).
  if [[ -L "$dst" ]]; then
    echo "  $p: WARNING — $dst is a SYMLINK (unsafe for the auth writer). Skipping; remove it and re-run." >&2
    continue
  fi
  dmd5="$(md5sum "$dst" | awk '{print $1}')"
  if [[ "$dmd5" == "$MAIN_MD5" ]]; then
    echo "  $p: already in sync (md5 match) — skip"
    continue
  fi
  echo "  $p: differs (md5=$dmd5) — would back up to $dst.bak-$TS and overwrite"
  if [[ $DRY == 0 ]]; then
    cp -p "$dst" "$dst.bak-$TS"
    cp -p "$MAIN_PROFILE" "$dst"; chmod 600 "$dst"; chown "$(id -un):$(id -gn)" "$dst" 2>/dev/null || true
    echo "    backed up + synced."
  fi
  changed=$((changed+1))
done

echo
echo "Peers needing change: $changed"
if [[ $DRY == 0 && $changed -gt 0 ]]; then
  echo "Done. (auth-state.json left untouched per-agent on purpose.)"
  echo "Verify: for a in main ${PEERS[*]}; do openclaw models auth list --agent \"\$a\" | grep copilot; done"
fi
