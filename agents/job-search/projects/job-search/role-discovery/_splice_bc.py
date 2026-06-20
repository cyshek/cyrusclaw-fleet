fp = "_ashby_runner.py"
s = open(fp).read()
NL = chr(10)
B = open("_blockB.txt").read()
C = open("_blockC.txt").read()

# Anchor B: after the two loop lines, before "        if _loc_str:"
loc_line = "        _loc_str = (_last_v.get('location') or '').strip()"
aB = loc_line + NL + "        if _loc_str:"
assert aB in s, "anchorB missing"
newB = loc_line + NL + B + "        if _loc_str:"
s = s.replace(aB, newB, 1)

# Anchor C: before the post-loop status assignment block
aC = "    if isinstance(_last_v, dict) and _last_v:"
assert aC in s, "anchorC missing"
# only replace the FIRST occurrence inside final_clobber_guard
s = s.replace(aC, C + aC, 1)

open(fp, "w").write(s)
print("spliced B and C")
