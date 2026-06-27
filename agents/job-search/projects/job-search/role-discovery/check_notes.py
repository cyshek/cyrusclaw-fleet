import sqlite3
conn = sqlite3.connect('../tracker.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

ids_to_check = [1295, 1320, 1399, 1488, 1549, 1575, 1601, 2617, 2620, 2659]
for rid in ids_to_check:
    c.execute('SELECT id, company, role, agent_notes FROM roles WHERE id=?', (rid,))
    r = c.fetchone()
    if r:\n        print(f"=== {r['id']} {r['company']} ===")
        print((r['agent_notes'] or '')[:600])
        print()
conn.close()
