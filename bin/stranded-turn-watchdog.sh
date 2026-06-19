#!/usr/bin/env bash
# stranded-turn-watchdog.sh
# Detects a job-search channel session whose LAST run failed (empty/zero-token model
# response) leaving a user message UNANSWERED, and auto-retries ONCE so Cyrus doesn't
# have to flag "it went quiet" each time.
#
# Root cause this addresses: transient empty model completions (totalTokens:0,
# stopReason null/error) fail the turn without replying; the user's question is
# left stranded at the tail of the transcript. A single re-poke spawns a fresh
# turn that picks it up.
#
# Scope: job-search channel session only (the recurring offender). Generalize later
# if other agents show the same pattern.
#
# Safety:
# - Retries AT MOST once per stranded message (dedup stamp keyed on the user msg id).
# - Never retries if a chain/subagent is actively running (won't interrupt work).
# - Only fires when the tail is: user message -> failed/empty assistant turn.
# - Read-only except for the single sessions_send re-poke + its own stamp file.

set -uo pipefail

AGENT="job-search"
CHANNEL_ID="1501827950474166332"
SESSION_KEY="agent:job-search:discord:channel:${CHANNEL_ID}"
SESS_DIR="/home/azureuser/.openclaw/agents/${AGENT}/sessions"
STAMP_DIR="/home/azureuser/.openclaw/var/stranded-watchdog"
mkdir -p "$STAMP_DIR"

# Resolve the channel session transcript (newest matching sessionId via sessions_list is
# overkill for cron; the channel session file is stable once created). Find the .jsonl whose
# tail references this channel and is most recently modified.
TRANSCRIPT="$(ls -t "${SESS_DIR}"/*.jsonl 2>/dev/null | while read -r f; do
  if grep -ql "channel:${CHANNEL_ID}" "$f" 2>/dev/null || grep -ql "${CHANNEL_ID}" "$f" 2>/dev/null; then
    echo "$f"; break
  fi
done)"

if [[ -z "${TRANSCRIPT:-}" || ! -f "$TRANSCRIPT" ]]; then
  echo "stranded-watchdog: no channel transcript found; nothing to do."
  exit 0
fi

# Don't interrupt active work: if a submit/render process is live, bail.
if ps aux | grep -iE 'drive_row|_runner|inline_submit|ashby_autofill|tailor_resume|bullet_rewriter|chain_0' | grep -qv grep; then
  echo "stranded-watchdog: active job-search work running; standing down."
  exit 0
fi

# Inspect the tail with python: find last user message + whether the most recent
# assistant turn after it was empty/failed.
ANALYSIS="$(python3 - "$TRANSCRIPT" <<'PY'
import sys, json
f = sys.argv[1]
last_user_id = None
last_user_text = ""
# track the most recent assistant turn and whether it was empty
recent = []  # (role, text, empty, msg_id)
for line in open(f, errors="ignore"):
    line=line.strip()
    if not line: continue
    try: o=json.loads(line)
    except: continue
    if o.get("type")!="message": continue
    m=o.get("message",{})
    role=m.get("role")
    c=m.get("content")
    text=""
    if isinstance(c,str): text=c
    elif isinstance(c,list):
        for x in c:
            if isinstance(x,dict) and x.get("type")=="text": text+=x.get("text","")
    usage=m.get("usage",{}) if isinstance(m,dict) else {}
    tot=usage.get("totalTokens",None)
    empty = (role=="assistant" and (not text.strip()) )
    recent.append((role, text.strip(), empty, o.get("id"), tot))

# Walk from the end: find the last assistant turn; check if it's empty AND the
# message before the model got to it was a user turn with real text.
# Stranded condition: the LAST role==assistant entry is empty, and somewhere after the
# previous *non-empty assistant* there is a user message (unanswered).
last_assistant_idx=None
for i in range(len(recent)-1,-1,-1):
    if recent[i][0]=="assistant":
        last_assistant_idx=i; break

stranded=False
user_id=None
user_text=""
if last_assistant_idx is not None and recent[last_assistant_idx][2]:  # last assistant empty
    # find nearest preceding user message
    for j in range(last_assistant_idx-1,-1,-1):
        if recent[j][0]=="user" and recent[j][1]:
            stranded=True
            user_id=recent[j][3]
            user_text=recent[j][1][:400]
            break
else:
    # Alt case: transcript ends on a USER message with NO assistant turn after it at all
    if recent and recent[-1][0]=="user" and recent[-1][1]:
        stranded=True
        user_id=recent[-1][3]
        user_text=recent[-1][1][:400]

print(json.dumps({"stranded":stranded,"user_id":user_id,"user_text":user_text}))
PY
)"

STRANDED="$(echo "$ANALYSIS" | python3 -c 'import sys,json;print(json.load(sys.stdin)["stranded"])' 2>/dev/null)"
USER_ID="$(echo "$ANALYSIS" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("user_id") or "")' 2>/dev/null)"
USER_TEXT="$(echo "$ANALYSIS" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("user_text") or "")' 2>/dev/null)"

if [[ "$STRANDED" != "True" ]]; then
  echo "stranded-watchdog: no stranded user turn. OK."
  exit 0
fi

# Dedup: only one retry per stranded user message id.
STAMP="${STAMP_DIR}/$(echo -n "${USER_ID:-notail}" | tr -c 'a-zA-Z0-9' '_').done"
if [[ -f "$STAMP" ]]; then
  echo "stranded-watchdog: already retried user msg ${USER_ID}; not re-poking."
  exit 0
fi

echo "stranded-watchdog: STRANDED user msg ${USER_ID} detected. Re-poking once."
echo "  user_text: ${USER_TEXT}"

# Emit the re-poke instruction to stdout for the cron's agentTurn to act on.
# The cron payload reads RETRY=1 and the captured user text, then issues the
# sessions_send to the channel session.
touch "$STAMP"
echo "RETRY_NEEDED user_id=${USER_ID}"
echo "USER_TEXT_BEGIN"
echo "${USER_TEXT}"
echo "USER_TEXT_END"
exit 0
