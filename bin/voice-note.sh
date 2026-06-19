#!/usr/bin/env bash
# voice-note.sh — send a Discord voice-message bubble using the raw API.
#
# Usage: voice-note.sh <channel_id> <text>
#        echo "<text>" | voice-note.sh <channel_id> -
#
# Requires: DISCORD_BOT_TOKEN in env, ffmpeg, node, edge-tts (bundled with openclaw).
# Output (stdout): the message ID on success, error to stderr on failure (nonzero exit).
#
# Used by all OpenClaw agents when Cyrus reacts 🔊 to one of their messages.
# Recipe: edge-tts -> mp3 -> ffmpeg ogg/opus -> 3-step Discord upload with flags=8192.

set -euo pipefail

CHANNEL="${1:?channel_id required}"
TEXT="${2:?text required (use - to read stdin)}"

if [[ "$TEXT" == "-" ]]; then
  TEXT="$(cat)"
fi

if [[ -z "${DISCORD_BOT_TOKEN:-}" ]]; then
  echo "DISCORD_BOT_TOKEN not set; sourcing /home/azureuser/.openclaw/.env" >&2
  set -a; source /home/azureuser/.openclaw/.env; set +a
fi
: "${DISCORD_BOT_TOKEN:?still not set after sourcing .env}"

# Strip markdown / emojis / code fences for cleaner TTS
TTS_TEXT=$(printf '%s' "$TEXT" \
  | sed -E 's/```[^`]*```//g' \
  | sed -E 's/`([^`]+)`/\1/g' \
  | sed -E 's/\*\*([^*]+)\*\*/\1/g' \
  | sed -E 's/\*([^*]+)\*/\1/g' \
  | sed -E 's/\[([^]]+)\]\([^)]+\)/\1/g' \
  | python3 -c "import sys,re; t=sys.stdin.read(); t=re.sub(r'[\U0001F300-\U0001FAFF\U00002600-\U000027BF]',' ',t); t=re.sub(r'\s+',' ',t); print(t.strip())")

# Edge-TTS has a length cap; truncate at ~3000 chars
TTS_TEXT="${TTS_TEXT:0:3000}"
# yargs in node-edge-tts mis-parses values starting with '-' as flags; prefix a
# zero-width space so the first char is never '-' (inaudible in TTS output).
case "$TTS_TEXT" in
  -*) TTS_TEXT=$'\u200b'"$TTS_TEXT" ;;
esac

TMPDIR_VN=$(mktemp -d)
trap 'rm -rf "$TMPDIR_VN"' EXIT

MP3="$TMPDIR_VN/v.mp3"
OGG="$TMPDIR_VN/v.ogg"

node /usr/lib/node_modules/openclaw/node_modules/node-edge-tts/bin.js \
  -t "$TTS_TEXT" -f "$MP3" -v en-US-AriaNeural -l en-US >/dev/null 2>&1

ffmpeg -y -i "$MP3" -c:a libopus -b:a 32k -ar 48000 -ac 1 "$OGG" 2>/dev/null

SIZE=$(stat -c%s "$OGG")
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OGG")
WAVE=$(python3 -c "import base64; print(base64.b64encode(bytes([128]*48)).decode())")

SLOT=$(curl -fsS -X POST "https://discord.com/api/v10/channels/$CHANNEL/attachments" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"files\":[{\"filename\":\"voice-message.ogg\",\"file_size\":$SIZE,\"id\":\"0\"}]}")

UPLOAD_URL=$(echo "$SLOT" | python3 -c "import sys,json; print(json.load(sys.stdin)['attachments'][0]['upload_url'])")
UPLOAD_NAME=$(echo "$SLOT" | python3 -c "import sys,json; print(json.load(sys.stdin)['attachments'][0]['upload_filename'])")

curl -fsS -X PUT "$UPLOAD_URL" -H "Content-Type: audio/ogg" --data-binary "@$OGG" >/dev/null

RESP=$(curl -fsS -X POST "https://discord.com/api/v10/channels/$CHANNEL/messages" \
  -H "Authorization: Bot $DISCORD_BOT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"flags\":8192,\"attachments\":[{\"id\":\"0\",\"filename\":\"voice-message.ogg\",\"uploaded_filename\":\"$UPLOAD_NAME\",\"duration_secs\":$DUR,\"waveform\":\"$WAVE\"}]}")

echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])"
