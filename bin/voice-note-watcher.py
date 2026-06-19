#!/usr/bin/env python3
"""voice-note-watcher.py — poll Discord for 🔊 reactions on bot messages and
auto-send a voice-note bubble using ~/.openclaw/bin/voice-note.sh.

Independent of any agent session. Runs forever. State is the set of
(channel_id, message_id) tuples we've already handled, persisted to a JSON
file so restarts don't replay history.

Resource budget: one HTTP call per channel per poll cycle (default 6s),
returns last 20 messages each. Discord rate limit is plenty.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import urllib.request
import urllib.error

TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
if not TOKEN:
    env_file = Path("/home/azureuser/.openclaw/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DISCORD_BOT_TOKEN="):
                TOKEN = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
if not TOKEN:
    print("FATAL: DISCORD_BOT_TOKEN not found", file=sys.stderr)
    sys.exit(1)

# Channel IDs from openclaw.json bindings (kept in sync manually for now)
CHANNELS = [
    "1501825713261510817",  # main (active DM with cyrus)
    "1501827950474166332",  # job-search
    "1502552885756432496",  # openclaw-updates
    "1504222524093894727",  # travel
    "1508503706545557656",  # trading-bench
    "1508695851697049812",  # making-money
]

TRIGGER_EMOJI = "🔊"
POLL_INTERVAL_SEC = 6
MESSAGE_FETCH_LIMIT = 20
STATE_FILE = Path("/home/azureuser/.openclaw/state/voice-note-watcher.json")
HELPER = "/home/azureuser/.openclaw/bin/voice-note.sh"

STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_state():
    if STATE_FILE.exists():
        try:
            return set(tuple(x) for x in json.loads(STATE_FILE.read_text()))
        except Exception:
            return set()
    return set()


def save_state(state):
    # Cap to most recent 500 entries to avoid unbounded growth
    if len(state) > 500:
        state = set(list(state)[-500:])
    STATE_FILE.write_text(json.dumps([list(t) for t in state]))


def http_get(url):
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bot {TOKEN}", "User-Agent": "openclaw-voice-watcher/1.0"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def fetch_recent_messages(channel_id):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={MESSAGE_FETCH_LIMIT}"
    try:
        return http_get(url)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            time.sleep(5)
        elif e.code in (401, 403, 404):
            print(f"[{channel_id}] permanent error {e.code}, removing from watch", file=sys.stderr)
            return None
        else:
            print(f"[{channel_id}] http {e.code}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[{channel_id}] fetch error: {e}", file=sys.stderr)
        return []


def send_voice_note(channel_id, text):
    try:
        result = subprocess.run(
            [HELPER, channel_id, text],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            print(f"[{channel_id}] sent voice note: {result.stdout.strip()}", flush=True)
            return True
        else:
            print(f"[{channel_id}] helper failed: {result.stderr.strip()[:500]}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"[{channel_id}] helper exception: {e}", file=sys.stderr)
        return False


def main():
    state = load_state()
    print(f"voice-note-watcher: started, {len(CHANNELS)} channels, state has {len(state)} entries", flush=True)
    dead_channels = set()
    while True:
        for ch in CHANNELS:
            if ch in dead_channels:
                continue
            msgs = fetch_recent_messages(ch)
            if msgs is None:
                dead_channels.add(ch)
                continue
            for m in msgs:
                mid = m.get("id")
                if not mid:
                    continue
                if not m.get("author", {}).get("bot"):
                    continue  # only react to bot messages
                key = (ch, mid)
                if key in state:
                    continue
                rxns = m.get("reactions", [])
                if not any(r.get("emoji", {}).get("name") == TRIGGER_EMOJI for r in rxns):
                    continue
                text = m.get("content", "").strip()
                if not text:
                    # might be an embed-only or attachment-only message; mark as seen so we don't loop
                    state.add(key)
                    continue
                if send_voice_note(ch, text):
                    state.add(key)
                    save_state(state)
                else:
                    # don't mark seen; will retry next cycle. but to avoid hot-looping,
                    # add a brief sleep
                    time.sleep(3)
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
