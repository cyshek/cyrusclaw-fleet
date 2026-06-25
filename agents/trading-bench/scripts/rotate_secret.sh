#!/usr/bin/env bash
# rotate_secret.sh — Discord-free secure ingestion of rotated credentials into the workspace .env
#
# WHY THIS EXISTS (BACKLOG L163): the original key drop pasted Alpaca keys into the
# #trading-bench Discord channel, exposing them in channel history. Discord/chat is NOT a
# secrets channel. This script is the DESIGNATED secure path for the NEXT rotation so no
# secret ever transits Discord (or any chat) again. See SECRETS.md for the full procedure.
#
# THREE intake modes, most-preferred first. A secret value is NEVER passed as a CLI arg
# (those leak into `ps` and shell history):
#   1) FILE DROP   --file [PATH]   ingest a file Cyrus scp'd to .secrets_drop/, then shred it.
#   2) HIDDEN TTY  --key NAME       prompt for ONE value on the terminal (read -s, not echoed).
#   3) ENV-INLINE  --key NAME --from-env   take value from $NAME already exported in Cyrus's shell.
#
# Updates .env atomically (temp+rename), keeps 600 perms, backs up the prior .env to memory/.
# Does NOT touch live trades, runners, GATE, or the killswitch.
#
# Usage:
#   scripts/rotate_secret.sh --file                       # ingest from .secrets_drop/incoming.env
#   scripts/rotate_secret.sh --file /tmp/newkeys.env      # ingest from an explicit dropped file
#   scripts/rotate_secret.sh --key APCA_API_SECRET_KEY    # hidden TTY prompt for one key
#   scripts/rotate_secret.sh --key FRED_API_KEY --from-env
#   scripts/rotate_secret.sh --verify                     # run post-rotation checks only
set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$WORKSPACE/.env"
DROP_DIR="$WORKSPACE/.secrets_drop"
DROP_DEFAULT="$DROP_DIR/incoming.env"
BACKUP_DIR="$WORKSPACE/memory"
VERIFIER="$WORKSPACE/scripts/verify_secrets.py"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

log() { printf '%s\n' "$*" >&2; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

ensure_drop_dir() { mkdir -p "$DROP_DIR"; chmod 700 "$DROP_DIR"; }

backup_env() {
  if [ ! -f "$ENV_FILE" ]; then log "(no existing .env to back up)"; return 0; fi
  local b="$BACKUP_DIR/env_backup_${TS}.env"
  cp -p "$ENV_FILE" "$b"; chmod 600 "$b"
  log "Backed up prior .env -> $b (600)"
}

# set_kv KEY VALUE — replace-or-append in .env, atomic, 600. Never logs the value.
set_kv() {
  local key="$1"; local val="$2"
  [ -n "$key" ] || die "empty key"
  local tmp; tmp="$(mktemp "$ENV_FILE.tmp.XXXXXX")"; chmod 600 "$tmp"
  local found=0
  if [ -f "$ENV_FILE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      case "$line" in
        "$key="*) printf '%s=%s\n' "$key" "$val" >> "$tmp"; found=1 ;;
        *)        printf '%s\n' "$line" >> "$tmp" ;;
      esac
    done < "$ENV_FILE"
  fi
  if [ "$found" -eq 0 ]; then printf '%s=%s\n' "$key" "$val" >> "$tmp"; fi
  mv "$tmp" "$ENV_FILE"; chmod 600 "$ENV_FILE"
  log "Set $key (value hidden). .env is 600."
}

shred_file() {
  local f="$1"; [ -f "$f" ] || return 0
  if command -v shred >/dev/null 2>&1; then shred -u "$f" && log "Shredded drop file: $f"
  else : > "$f"; rm -f "$f"; log "Removed drop file: $f"; fi
}

ingest_file() {
  local src="${1:-$DROP_DEFAULT}"
  [ -f "$src" ] || die "drop file not found: $src (scp it there first; see SECRETS.md)"
  backup_env
  local count=0
  while IFS= read -r raw || [ -n "$raw" ]; do
    local line; line="$(printf '%s' "$raw" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    [ -z "$line" ] && continue
    case "$line" in \#*) continue ;; esac
    case "$line" in *"="*) : ;; *) continue ;; esac
    local k="${line%%=*}"; local v="${line#*=}"
    k="$(printf '%s' "$k" | sed -e 's/[[:space:]]*$//')"
    v="$(printf '%s' "$v" | sed -e 's/^[[:space:]]*//' -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")"
    case "$k" in [A-Z]*) : ;; *) log "skip non-UPPER key: $k"; continue ;; esac
    set_kv "$k" "$v"; count=$((count+1))
  done < "$src"
  [ "$count" -gt 0 ] || die "no valid KEY=VALUE lines in $src"
  shred_file "$src"
  log "Ingested $count key(s) and shredded the drop file."
}

ingest_key() {
  local key="$1"; local from_env="${2:-0}"
  case "$key" in [A-Z]*) : ;; *) die "key must be UPPER_SNAKE: $key" ;; esac
  local val=""
  if [ "$from_env" -eq 1 ]; then
    val="${!key:-}"
    [ -n "$val" ] || die "\$$key is empty/unset. export it first, then re-run with --from-env."
  else
    [ -t 0 ] || die "no TTY for hidden prompt; use --file or --from-env."
    printf 'Paste new value for %s (hidden, will not echo): ' "$key" >&2
    read -rs val; printf '\n' >&2
    [ -n "$val" ] || die "empty value; aborted."
  fi
  backup_env; set_kv "$key" "$val"; unset val
  log "Rotated $key."
}

verify() {
  if [ -f "$VERIFIER" ]; then ( cd "$WORKSPACE" && python3 "$VERIFIER" ) || log "verify reported a problem (above)."
  else log "verifier missing: $VERIFIER"; fi
}

main() {
  ensure_drop_dir
  local mode=""; local key=""; local src=""; local from_env=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --file) mode="file"; if [ "${2:-}" ] && [ "${2#--}" = "${2}" ]; then src="$2"; shift; fi ;;
      --key) mode="key"; key="${2:-}"; shift ;;
      --from-env) from_env=1 ;;
      --verify) mode="verify" ;;
      -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
      *) die "unknown arg: $1 (see --help)" ;;
    esac
    shift
  done
  if [ -z "$mode" ]; then sed -n '2,30p' "$0"; exit 0; fi
  case "$mode" in
    file) ingest_file "${src:-$DROP_DEFAULT}"; verify ;;
    key) [ -n "$key" ] || die "--key requires a NAME"; ingest_key "$key" "$from_env"; verify ;;
    verify) verify ;;
  esac
  log "Done."
}
main "$@"
