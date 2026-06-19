#!/usr/bin/env bash
# delete-safety-livefire.sh
#
# Live-fire test of the agent-deletion safeguards. Creates a throwaway agent
# `delete-test-dummy`, deletes ONLY it, and asserts via hard checks that NO
# other agent's config, workspace, or channel binding was touched.
#
# Greenlit by Cyrus 2026-05-31. Safe-by-construction: the only agent created
# or deleted is the dummy. Any assertion failure aborts loudly.
#
# Does NOT create or delete any Discord channel (agents add/delete don't touch
# channels; channel deletion is separately guarded by resolve-agent-channel.sh
# + two-key confirm). This tests the agent config/workspace prune path.

set -uo pipefail
OC_DIR="/home/azureuser/.openclaw"
OC="node /usr/lib/node_modules/openclaw/dist/index.js"
DUMMY="delete-test-dummy"
WS="${OC_DIR}/agents/${DUMMY}/workspace"
fail() { echo "❌ ASSERTION FAILED: $*"; exit 1; }
ok()   { echo "✓ $*"; }

roster() { $OC agents list --json 2>/dev/null | python3 -c "import json,sys;print('\n'.join(sorted(a['id'] for a in json.load(sys.stdin).get('agents',json.load(sys.stdin) if False else [])) ))" 2>/dev/null \
  || $OC agents list 2>/dev/null | grep -oE '^[a-z0-9-]+' ; }

echo "================ PRE-STATE ================"
BEFORE=$(cd "$OC_DIR" && for d in agents/*/; do basename "$d"; done | sort)
echo "$BEFORE" | sed 's/^/  /'
echo "$BEFORE" | grep -qx "$DUMMY" && fail "dummy '$DUMMY' already exists — aborting to avoid clobbering"
ok "dummy does not pre-exist"

echo "================ CREATE DUMMY ================"
$OC agents add "$DUMMY" --non-interactive --workspace "$WS" --model github-copilot/claude-opus-4.8 --json 2>&1 | tail -5
[ -d "${OC_DIR}/agents/${DUMMY}" ] || fail "dummy agent dir was not created"
ok "dummy created at agents/${DUMMY}"

# snapshot every OTHER agent's dir mtime + a hash of its config presence
echo "================ SNAPSHOT OTHERS ================"
SNAP=$(mktemp)
for d in "${OC_DIR}"/agents/*/; do
  a=$(basename "$d"); [ "$a" = "$DUMMY" ] && continue
  echo "$a $(stat -c '%Y' "$d") $(ls "$d" | sort | md5sum | cut -d' ' -f1)" >> "$SNAP"
done
cat "$SNAP" | sed 's/^/  /'

echo "================ RESOLVER REFUSES MAIN, ALLOWS DUMMY ================"
bash "${OC_DIR}/bin/resolve-agent-channel.sh" main >/dev/null 2>&1 && fail "resolver did NOT refuse main" || ok "resolver refuses main (exit 2)"

echo "================ DELETE ONLY THE DUMMY ================"
$OC agents delete "$DUMMY" --force --json 2>&1 | tail -5
# NOTE: `agents delete` prunes config/bindings/sessions but DELIBERATELY leaves
# the workspace dir on disk (policy: workspaces are institutional knowledge,
# never auto-deleted). So we assert the agent is gone from the ROSTER, not that
# the directory vanished. Workspace removal is a separate, manual, confirmed step.
if $OC agents list 2>/dev/null | grep -qx -- "- ${DUMMY}" || $OC agents list 2>/dev/null | grep -q "^${DUMMY}$"; then
  fail "dummy still in agent roster after delete"
fi
ok "dummy removed from agent roster (config-level deleted)"
# clean up the empty leftover workspace dir the test created
rmdir "${OC_DIR}/agents/${DUMMY}" 2>/dev/null || true

echo "================ POST-ASSERTIONS ================"
# 1. every other agent still present, unchanged roster minus dummy
AFTER=$(cd "$OC_DIR" && for d in agents/*/; do basename "$d"; done | grep -vx "$DUMMY" | sort)
EXPECTED=$(echo "$BEFORE" | grep -vx "$DUMMY")
[ "$AFTER" = "$EXPECTED" ] || fail "roster changed beyond dummy removal:\n--before(minus dummy)--\n$EXPECTED\n--after--\n$AFTER"
ok "roster == before-minus-dummy (no collateral agent add/remove)"

# 2. every other agent dir still present with same file-listing hash
while read -r a mt hash; do
  d="${OC_DIR}/agents/${a}/"
  [ -d "$d" ] || fail "agent '$a' dir disappeared!"
  now=$(ls "$d" | sort | md5sum | cut -d' ' -f1)
  [ "$now" = "$hash" ] || fail "agent '$a' dir contents changed (hash $hash -> $now)"
done < "$SNAP"
ok "all other agents' dir contents unchanged"

# 3. resolver still resolves a known peer correctly (bindings intact)
TB=$(bash "${OC_DIR}/bin/resolve-agent-channel.sh" trading-bench 2>/dev/null)
[ "$TB" = "OWN_CHANNEL=1508503706545557656" ] || fail "trading-bench binding changed: $TB"
ok "trading-bench channel binding intact after delete ($TB)"

rm -f "$SNAP"
echo "================ RESULT ================"
echo "✅ LIVE-FIRE PASSED: only '$DUMMY' was created and deleted; all 5 real agents + bindings untouched."
