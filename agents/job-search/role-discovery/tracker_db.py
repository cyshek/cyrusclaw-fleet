"""SQLite-backed tracker — replaces tracker.md as source of truth.

Schema:
  roles(id, source_key UNIQUE, company, role, level, loc, exp_req,
        jd_url, app_url, status, flags, applied_by, applied_on, cyrus_notes,
        agent_notes,
        first_seen, last_seen)

Status values (slimmed per Cyrus 2026-05-11):
  queued | submitted | skip | closed | none | scan-blocked

Cyrus-editable columns: applied_by, applied_on, cyrus_notes, status (manual skip flips).
Agent-editable column: agent_notes (the agent writes its own observations here so it doesn't stomp Cyrus's notes).
Agent-managed columns: company/role/loc/etc., flags, first_seen/last_seen, source_key.
"""
from __future__ import annotations
import sqlite3
import re
from pathlib import Path
from datetime import datetime

DB_PATH = Path("/home/azureuser/.openclaw/agents/job-search/workspace/projects/job-search/tracker.db")

APPLE_URL_RE = re.compile(r"jobs\.apple\.com/[^/]+/details/(\d+)", re.I)
GH_JID_RE = re.compile(r"[?&]gh_jid=(\d+)")


def normalize_url(u: str) -> str:
    """Return a stable dedupe key for a job URL."""
    u = (u or "").strip()
    if not u or u == "—":
        return ""
    m = APPLE_URL_RE.search(u)
    if m:
        return f"apple:{m.group(1)}"
    u = re.sub(r"[?&](utm_[^=&]+|gh_src|source|src|ref)=[^&]*", "", u)
    u = u.rstrip("?&/")
    return u


SCHEMA = """
CREATE TABLE IF NOT EXISTS roles (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  source_key  TEXT UNIQUE,
  company     TEXT NOT NULL,
  role        TEXT NOT NULL,
  level       TEXT,
  loc         TEXT,
  exp_req     TEXT,
  jd_url      TEXT,
  app_url     TEXT,
  status      TEXT NOT NULL DEFAULT 'queued',
  flags       TEXT,
  applied_by  TEXT,
  applied_on  TEXT,
  cyrus_notes TEXT,
  agent_notes TEXT DEFAULT '',
  posted_on   TEXT,
  first_seen  TEXT,
  last_seen   TEXT
);
CREATE INDEX IF NOT EXISTS idx_roles_company ON roles(company);
CREATE INDEX IF NOT EXISTS idx_roles_status  ON roles(status);

-- Data-integrity guard (added 2026-06-03): applied_by must only be set when the
-- row is actually in a submit state ('applied'/'submitted'). Chains used to stamp
-- applied_by mid-process on rows that ended up 'blocked', inflating the
-- applied count (393 vs ~327 real). This trigger silently NULLs an illegitimate
-- applied_by and logs the rejection to agent_notes rather than aborting (so
-- runners don't crash). Legit submits (status flips to applied/submitted in the
-- same/earlier write) pass through untouched.
CREATE TRIGGER IF NOT EXISTS guard_applied_by_requires_submit_status
AFTER UPDATE OF applied_by ON roles
FOR EACH ROW
WHEN NEW.applied_by IS NOT NULL
     AND (NEW.status IS NULL OR NEW.status NOT IN ('applied','submitted'))
BEGIN
    UPDATE roles SET
        applied_by = NULL,
        agent_notes = COALESCE(agent_notes,'') ||
            ' [guard: applied_by=' || NEW.applied_by ||
            ' rejected — status=' || COALESCE(NEW.status,'NULL') || ' not a submit state]'
    WHERE id = NEW.id;
END;

CREATE TABLE IF NOT EXISTS company_scans (
  company    TEXT PRIMARY KEY,
  last_scan  TEXT,
  fetched    INTEGER DEFAULT 0,
  status     TEXT
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")
