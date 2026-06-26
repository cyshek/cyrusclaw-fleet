"""One-shot surgical rewrite of build_nfci_pit in _regime_allocator.py to use the
first-release NFCI dict instead of ALFRED as-of (which 400s pre-2011-05)."""
import re

P = "_regime_allocator.py"
src = open(P).read()

# Anchors: function def line .. its 'return out' that precedes build_baa_pit.
start_anchor = "def build_nfci_pit(rebal_dates: List[str]) -> Dict[str, Tuple[float, str, str]]:"
end_anchor = "def build_baa_pit(rebal_dates: List[str]) -> Dict[str, Tuple[float, str]]:"

i = src.index(start_anchor)
j = src.index(end_anchor)
assert i < j, "anchors out of order"

NL = chr(10)
new_fn_lines = [
    "def build_nfci_pit(rebal_dates: List[str]) -> Dict[str, Tuple[float, str, str]]:",
    '    """For each rebalance date D return (nfci_value_used, nfci_obs_date,',
    "    nfci_release_date) from the cached FIRST-RELEASE NFCI dict (purest PIT:",
    "    first print, no revision leak). The dict maps obs_date -> [release_date,",
    "    first_value]. At month-open D take the LATEST obs whose RELEASE_DATE <= D",
    "    -- the freshest NFCI a trader could legitimately have acted on at D.",
    "",
    "    NFCI's real-time archive begins 2011-05-25 (its first release; ALFRED 400s",
    "    on as-of dates before that). Rebalance dates before the first release get",
    "    no entry here -> caller falls back to the static inv-vol weight. Honest:",
    "    you could not have traded an NFCI regime in 2010.",
    '    """',
    "    with open(NFCI_FIRSTREL) as fh:",
    "        firstrel = json.load(fh)",
    "    recs = sorted(",
    "        ((v[0], k, float(v[1]))",
    "         for k, v in firstrel.items()",
    "         if isinstance(v, list) and v and v[0] is not None and v[1] is not None),",
    "        key=lambda x: x[0])",
    "    rel_dates = [r[0] for r in recs]",
    "",
    "    out: Dict[str, Tuple[float, str, str]] = {}",
    "    for D in rebal_dates:",
    "        j = bisect.bisect_right(rel_dates, D) - 1",
    "        if j < 0:",
    "            continue",
    "        rel, obs, val = recs[j]",
    "        out[D] = (val, obs, rel)",
    "    return out",
    "",
    "",
]
new_fn = NL.join(new_fn_lines)

src2 = src[:i] + new_fn + src[j:]
open(P, "w").write(src2)
print("rewrote build_nfci_pit; new file len", len(src2))
