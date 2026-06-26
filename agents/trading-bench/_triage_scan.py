"""Compute the SAFE-TO-ARCHIVE set of root _*.py scratch files.

Method:
  1. ROOTS = root _*.py imported by package/test/runner code (NON-scratch).
     These MUST stay (production imports them).
  2. Build the scratch import graph (which root _*.py imports which other root
     _*.py).
  3. Transitive closure: anything reachable FROM a load-bearing root via
     "X imports Y" must ALSO stay (it's a dependency of a kept file).
  4. KEEP-DRIVERS: explicit allowlist of report-drivers I want to retain even
     though nothing imports them (e.g. the COT sweep just shipped).
  5. SAFE = all root _*.py  -  (closure of load-bearing)  -  keep-drivers.

Prints the three sets. Does NOT move anything (dry-run by design).
"""
import os
import re
import glob

ROOT = "."
scratch = sorted(os.path.basename(p) for p in glob.glob("_*.py"))
mods = {f[:-3]: f for f in scratch}  # module-name -> filename

PKG_DIRS = ["runner", "tests", "strategies", "strategies_candidates"]

def imports_in(path):
    """Return set of root-scratch module names imported by file at path."""
    out = set()
    try:
        txt = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return out
    for m in mods:
        if re.search(r"(^|\n)\s*import %s\b" % re.escape(m), txt) or \
           re.search(r"(^|\n)\s*from %s import" % re.escape(m), txt):
            out.add(m)
    return out

# 1. package-imported roots (load-bearing seeds)
seeds = set()
for d in PKG_DIRS:
    for dp, _, fns in os.walk(d):
        if "__pycache__" in dp:
            continue
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            for m in imports_in(os.path.join(dp, fn)):
                seeds.add(m)

# 2. scratch->scratch import graph
graph = {m: imports_in(mods[m]) for m in mods}

# 3. transitive closure from seeds (follow "kept imports dep" edges)
keep = set()
stack = list(seeds)
while stack:
    m = stack.pop()
    if m in keep or m not in mods:
        continue
    keep.add(m)
    for dep in graph.get(m, ()):
        if dep not in keep:
            stack.append(dep)

# 4. keep-drivers allowlist (retain even if unreferenced)
KEEP_DRIVERS = {"_cot_percentile_wf_sweep"}  # just-shipped COT WF sweep driver
keep |= (KEEP_DRIVERS & set(mods))

# 5. safe set
safe = sorted(set(mods) - keep)

print("TOTAL root _*.py:", len(mods))
print("PACKAGE-IMPORTED seeds (%d):" % len(seeds), sorted(seeds))
print("MUST-KEEP closure (%d):" % len(keep), sorted(keep))
print("KEEP-DRIVERS allowlist:", sorted(KEEP_DRIVERS & set(mods)))
print("SAFE-TO-ARCHIVE (%d):" % len(safe))
for f in safe:
    sz = os.path.getsize(mods[f])
    print("   %-44s %6d B" % (mods[f], sz))
tot = sum(os.path.getsize(mods[f]) for f in safe)
print("SAFE total bytes: %d (%.0f KB)" % (tot, tot / 1024))
