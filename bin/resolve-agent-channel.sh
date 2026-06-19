#!/usr/bin/env bash
# resolve-agent-channel.sh <agent_id>
#
# Authoritative agent -> OWN-channel resolver for safe deletion.
#
# WHY THIS EXISTS: the pre-delete checklist used to say "resolve the binding
# from openclaw.json", but agent<->channel bindings actually live in each
# agent's sessions.json. CRITICAL FOOTGUN: main's sessions.json references
# EVERY agent's channel (because main has talked to all of them). Naively
# scraping "channels seen in the agent's session file" therefore makes `main`
# look like it owns everything, and is exactly how main once self-deleted.
#
# This resolver returns the SINGLE channel an agent uniquely owns, by taking
# the set of channels in <agent>/sessions.json and SUBTRACTING every channel
# that also appears in ANY OTHER agent's session file. An agent's own channel
# is the one no other agent references. main has no such unique channel by this
# definition (all its channels are shared), so main resolves to EMPTY and is
# explicitly refused.
#
# Output (stdout): one line `OWN_CHANNEL=<id>` on success.
# Exit codes: 0 = exactly one own-channel resolved; 2 = main/refused;
#             3 = agent not found; 4 = zero or >1 own-channels (ambiguous, ABORT).

set -uo pipefail
OC_DIR="/home/azureuser/.openclaw"
AGENTS_DIR="${OC_DIR}/agents"
AID="${1:-}"

[ -z "$AID" ] && { echo "ERROR: usage: resolve-agent-channel.sh <agent_id>" >&2; exit 3; }
[ -d "${AGENTS_DIR}/${AID}" ] || { echo "ERROR: agent '$AID' not found in ${AGENTS_DIR}" >&2; exit 3; }

if [ "$AID" = "main" ]; then
  echo "REFUSED: 'main' is never a deletion target. Its session file references every agent's channel; it owns no unique channel by design." >&2
  exit 2
fi

python3 - "$AID" "$AGENTS_DIR" <<'PY'
import json, os, re, sys
aid, agents_dir = sys.argv[1], sys.argv[2]

def chans_of(agent):
    f = os.path.join(agents_dir, agent, "sessions", "sessions.json")
    if not os.path.isfile(f):
        return set()
    try:
        blob = json.dumps(json.load(open(f)))
    except Exception:
        return set()
    return set(re.findall(r'discord:channel:(\d{17,19})', blob))

all_agents = [d for d in os.listdir(agents_dir)
              if os.path.isdir(os.path.join(agents_dir, d))]

target = chans_of(aid)
# Union of channels referenced by every OTHER *PEER* agent.
# CRITICAL: exclude 'main' from the subtraction set. main legitimately talks to
# every peer, so its session file references every peer channel; counting main
# would make every peer look "shared" and resolve to nothing (the bug the
# live-fire test caught on 2026-05-31). A channel is only genuinely shared if
# TWO PEERS reference it. main's references don't count.
others = set()
for a in all_agents:
    if a == aid or a == "main":
        continue
    others |= chans_of(a)

own = sorted(target - others)   # channels unique to this agent (peer-wise)

if len(own) == 1:
    print(f"OWN_CHANNEL={own[0]}")
    sys.exit(0)
elif len(own) == 0:
    print(f"ABORT: agent '{aid}' has NO uniquely-owned channel "
          f"(target channels={sorted(target)} all shared with other agents). "
          f"Refusing to resolve a delete target. Manual review required.",
          file=sys.stderr)
    sys.exit(4)
else:
    print(f"ABORT: agent '{aid}' resolves to MULTIPLE unique channels {own}. "
          f"Ambiguous — refusing. Manual review required.", file=sys.stderr)
    sys.exit(4)
PY
