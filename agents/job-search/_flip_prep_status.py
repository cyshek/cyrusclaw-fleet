#!/usr/bin/env python3
"""Flip prep_status for 72 reconciled rows based on STATUS.md content.

Authoritative match: scan all submitted/*/STATUS.md and index by role_id (the
field inside STATUS.md). Then classify by headline prefix.
"""
import sqlite3
import re
from pathlib import Path

ROLE_IDS = [589, 597, 643, 708, 756, 791, 792, 795, 797, 799, 814, 816, 817, 818, 836, 890, 891, 892, 919, 935, 936, 937, 938, 939, 941, 942, 943, 967, 968, 1015, 1105, 1112, 1119, 1124, 1126, 1134, 1153, 1202, 1206, 1209, 1213, 1232, 1235, 1248, 1321, 1326, 1331, 1343, 1352, 1356, 1359, 1361, 1362, 1363, 1364, 1366, 1367, 1377, 1380, 1381, 1382, 1383, 1385, 1386, 1387, 1388, 1389, 1390, 1391, 1397, 1552, 1555]

WS = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search")
SUB = WS / "applications" / "submitted"
DB = WS / "tracker.db"

ROLE_ID_RE = re.compile(r"role_id:\s*(\d+)", re.IGNORECASE)

def build_index():
    """Map role_id -> list of (folder_path, headline, status_text)."""
    idx = {}
    for d in SUB.iterdir():
        if not d.is_dir():
            continue
        sf = d / "STATUS.md"
        if not sf.exists():
            continue
        try:
            text = sf.read_text(errors="replace")
        except Exception:
            continue
        m = ROLE_ID_RE.search(text)
        if not m:
            continue
        rid = int(m.group(1))
        # headline = first non-empty stripped line
        headline = ""
        for line in text.split("\n"):
            s = line.strip()
            if s:
                headline = s.lstrip("#").strip()
                break
        idx.setdefault(rid, []).append((d, headline, text))
    return idx

def classify(headline):
    h = headline.upper()
    # Order matters: check PREP-READY-MANUAL variants first
    if h.startswith("PREP-READY"):
        # PREP-READY, PREP-READY-MANUAL, PREP-READY-CSP-CAPTCHA, PREP-READY-IFRAME-RUNNER, etc.
        return "manual_ready"
    if h.startswith("SUBMITTED"):
        return "submitted"
    if h.startswith("BLOCKED") and "DISQUALIFIER" in h:
        return "skipped"
    if "MAINTENANCE" in h and "RETRY" in h:
        return None  # NULL
    if h.startswith("ABORT"):
        # ABORT-CAPTCHA-FAIL, ABORT-DRYRUN-BLOCKERS, etc. — treat as still-needs-attention, leave NULL
        return None
    if h.startswith("BLOCKED"):
        return None
    return "UNKNOWN"

def main():
    idx = build_index()
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    results = {"manual_ready": 0, "submitted": 0, "skipped": 0, "left_null": 0, "unknown": 0, "no_folder": 0}
    details = []

    for rid in ROLE_IDS:
        matches = idx.get(rid, [])
        if not matches:
            results["no_folder"] += 1
            details.append((rid, "NO_FOLDER", None, None))
            continue
        # If multiple folders reference same role_id, prefer manual_ready over null over unknown
        chosen = None
        chosen_status = None
        for (folder, headline, _) in matches:
            st = classify(headline)
            if chosen is None:
                chosen = (folder, headline); chosen_status = st
            elif st == "manual_ready" and chosen_status != "manual_ready":
                chosen = (folder, headline); chosen_status = st
            elif st == "submitted" and chosen_status not in ("manual_ready",):
                chosen = (folder, headline); chosen_status = st

        folder, headline = chosen
        st = chosen_status
        prep_path = f"applications/submitted/{folder.name}"

        if st is None:
            results["left_null"] += 1
            details.append((rid, "LEFT_NULL", folder.name, headline))
            continue
        if st == "UNKNOWN":
            results["unknown"] += 1
            details.append((rid, "UNKNOWN", folder.name, headline))
            continue

        cur.execute("UPDATE roles SET prep_status=?, prep_path=? WHERE id=?", (st, prep_path, rid))
        results[st] += 1
        details.append((rid, st, folder.name, headline))

    conn.commit()
    conn.close()

    print("=== RESULTS ===")
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("\n=== DETAILS ===")
    for d in details:
        print(d)

if __name__ == "__main__":
    main()
