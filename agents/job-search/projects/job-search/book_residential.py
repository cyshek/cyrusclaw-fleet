#!/usr/bin/env python3
"""Book the 8 confirmed residential Ashby submissions into DB + STATUS.md."""
import sqlite3, os
from datetime import datetime, timezone

TODAY = "2026-06-23"
TS = datetime.now(timezone.utc).isoformat(timespec="seconds")

submissions = [
    (3340, "airops-b52cef06-1909-4c31-865a-5882af69c177", "AirOps", "Product Manager, New Verticals"),
    (2780, "antithesis-41acb777-5f13-45e2-8dfa-19db06a186f7", "Antithesis", "Forward Deployed Engineer"),
    (3140, "elevenlabs-c35a1d78-eb1f-49b9-a575-fc85b4256ba1", "ElevenLabs", "Talent Operations - Program Manager"),
    (3317, "fluidstack-49b1ab6b-d27d-4002-9dbd-89938df3d5ce", "Fluidstack", "Product Manager, Data Centers and Tooling"),
    (3452, "handshake-bbf75e71-d855-4e52-b924-79cbe701928f", "Handshake", "Program Manager"),
    (3390, "latent-9f1e2942-d911-47b1-a860-3a98e2e4e107", "Latent", "Product Manager"),
    (1983, "profound-b076c997-0ba3-4d3c-9dc9-ad0b3ed49b05", "Profound", "Forward Deployed Engineer"),
    (2562, "roboflow-444ee288-cb72-4751-b16d-67c27749e901", "Roboflow", "Forward Deployed Engineer"),
]

conn = sqlite3.connect("tracker.db")
submitted_dir = "role-discovery/applications/submitted"

for role_id, slug, company, title in submissions:
    row = conn.execute("SELECT applied_by, applied_on FROM roles WHERE id=?", (role_id,)).fetchone()
    if row and row[0]:
        print(f"SKIP {slug}: already applied_by={row[0]} on {row[1]}")
        continue
    slug_dir = os.path.join(submitted_dir, slug)
    os.makedirs(slug_dir, exist_ok=True)
    content = "SUBMITTED\n\nsubmitted_by: auto-residential\napplied_on: {}\nrole_id: {}\nsubmitted_at: {}\ncompany: {}\nrole: {}\nnote: Submitted via residential proxy (Webshare 82.23.97.223) in neat-nexus session 2026-06-23\n".format(TODAY, role_id, TS, company, title)
    open(os.path.join(slug_dir, "STATUS.md"), "w").write(content)
    conn.execute("UPDATE roles SET status='submitted', applied_by='auto-residential', applied_on=?, prep_status='submitted' WHERE id=?", (TODAY, role_id))
    print(f"BOOKED: {company} / {title} (id={role_id})")

conn.commit()
conn.close()
print("Done.")
