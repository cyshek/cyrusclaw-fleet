fp = "_ashby_runner.py"
s = open(fp).read()
NL = chr(10)
if "_wa_radio_specs = []" in s:
    print("blockA already present"); raise SystemExit(0)
A = open("_blockA.txt").read()
aA = "    _consec_ok = 0" + NL + "    _last_v = {}" + NL + "    for _i in range(8):"
assert aA in s, "anchorA missing"
newA = "    _consec_ok = 0" + NL + "    _last_v = {}" + NL + A + "    for _i in range(8):"
s = s.replace(aA, newA, 1)
open(fp, "w").write(s)
print("blockA inserted")
