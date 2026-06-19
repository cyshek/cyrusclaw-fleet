#!/usr/bin/env python3
"""Auto-bump github-copilot fallback tiers to newest sonnet + gpt in the catalog.
Updates ALL fallback blocks in openclaw.json. Backs up first. Prints a bump summary
or 'NOCHANGE'. Does NOT touch primary models. Does NOT restart (caller hot-reloads)."""
import json, re, subprocess, shutil, datetime, sys

CFG = "/home/azureuser/.openclaw/openclaw.json"

def catalog():
    out = subprocess.run(["openclaw","models","list"], capture_output=True, text=True).stdout
    ids = []
    for line in out.splitlines():
        m = re.match(r'\s*(github-copilot/\S+)', line)
        if m: ids.append(m.group(1))
    return ids

def newest(ids, family_regex):
    # family_regex captures a version tuple; pick highest numeric version
    best=None; best_key=None
    for i in ids:
        m = re.search(family_regex, i)
        if not m: continue
        ver = tuple(int(x) for x in re.findall(r'\d+', m.group(1)))
        if best_key is None or ver > best_key:
            best_key, best = ver, i
    return best

def main():
    ids = catalog()
    # newest plain sonnet (exclude -codex/-mini/-nano variants), newest plain gpt-5.x (exclude codex/mini/nano)
    sonnet = newest(ids, r'claude-sonnet-(\d+(?:\.\d+)?)$')
    gpt    = newest([i for i in ids if not re.search(r'(codex|mini|nano)', i)], r'gpt-(5\.\d+)$')
    if not sonnet or not gpt:
        print("NOCHANGE (could not resolve newest sonnet/gpt: sonnet=%s gpt=%s)" % (sonnet,gpt)); return
    desired = [sonnet, gpt]

    cfg = json.load(open(CFG))
    agents = cfg.get("agents", {})
    blocks=[]
    dm = agents.get("defaults",{}).get("model")
    if isinstance(dm,dict): blocks.append(("defaults",dm))
    for a in (agents.get("list") or agents.get("entries") or []):
        if isinstance(a,dict) and isinstance(a.get("model"),dict):
            blocks.append((a.get("id"), a["model"]))

    changes=[]
    for who, mb in blocks:
        cur = mb.get("fallbacks")
        if isinstance(cur,list) and cur != desired:
            changes.append((who, list(cur), list(desired)))
            mb["fallbacks"] = list(desired)

    if not changes:
        print("NOCHANGE (already on newest: %s)" % desired); return

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy(CFG, "%s.bak.autobump.%s" % (CFG, ts))
    json.dump(cfg, open(CFG,"w"), indent=2)
    # summarize once (all blocks change identically)
    old = changes[0][1]; new = changes[0][2]
    print("BUMPED %d blocks: %s -> %s" % (len(changes), old, new))

if __name__=="__main__":
    main()
