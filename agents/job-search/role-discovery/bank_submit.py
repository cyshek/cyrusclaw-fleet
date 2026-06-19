#!/usr/bin/env python3
"""Bank a confirmed Ashby/GH submit: set applied + TRIED note. Usage: bank_submit.py <id> [extra-note]"""
import sqlite3, sys
rid = int(sys.argv[1])
extra = sys.argv[2] if len(sys.argv) > 2 else ""
note = " | TRIED 2026-06-09: SUBMITTED via residential (ApplicationSuccess classify=submitted EXIT=0); STATUS.md written." + ((" " + extra) if extra else "")
c = sqlite3.connect('../tracker.db')
c.execute("UPDATE roles SET applied_by='auto', applied_on='2026-06-09', status='applied', agent_notes=COALESCE(agent_notes,'')||? WHERE id=?", (note, rid))
c.commit()
r = c.execute('SELECT id,status,applied_on FROM roles WHERE id=?', (rid,)).fetchone()
n = c.execute("SELECT COUNT(*) FROM roles WHERE applied_on='2026-06-09'").fetchone()[0]
print('banked:', r, '| applied today now:', n, '| integrity:', c.execute('PRAGMA integrity_check').fetchone()[0])
