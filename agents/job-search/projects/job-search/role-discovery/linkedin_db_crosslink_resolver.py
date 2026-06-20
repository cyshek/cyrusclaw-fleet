#!/usr/bin/env python3
"""LinkedIn-stranded DB cross-link resolver -- ZERO network, zero cost.

The cheapest, safest tier of LinkedIn offsite-link resolution: many rows that
LinkedIn discovery stranded with a `linkedin.com/jobs/view/<id>` app_url are for
a company+role we have *already crawled directly* from that company's public ATS
board (a separate, non-LinkedIn row in the SAME tracker.db). For those rows we do
not need to extract anything from LinkedIn (which is anonymously impossible -- see
LINKEDIN-ATS-RESOLUTION-WALL.md) and we do not need any HTTP probe: we just copy
the already-known ATS app_url from the matching direct row.

We rewrite ONLY app_url (the field inline_submit.detect_ats() routes on) and
agent_notes. We deliberately LEAVE source_key as the original linkedin:<id>:
roles.source_key is UNIQUE and the matched direct row already owns its canonical
key, so copying it would collide; preserving the linkedin:<id> also keeps the
row's discovery-source identity intact.

This complements the HTTP resolvers (linkedin_resolver_pipeline.py careers-probe,
linkedin_stranded_brute_resolver.py board-API fetch). It is strictly cheaper and
should run FIRST -- every row it resolves is one fewer HTTP probe the others must
make, and it cannot get rate-limited or blocked.

SAFETY (why this never mis-links):
  - Match key is (normalized company, normalized title) -- the SAME normalization
    linkedin_resolver_pipeline.py uses (pm->product manager, tpm->technical
    program manager, punctuation/whitespace folded).
  - We only resolve a row when EXACTLY ONE distinct direct-ATS app_url exists for
    that (company, title). If a company has two distinct postings that normalize
    to the same title (ambiguous), we SKIP it rather than guess.
  - We only read direct rows that are not closed/rejected, so we never point a row
    at a dead posting that we already know is gone.
  - Dry-run is the default; --apply is required to write. Commits every 25 rows.

CLI:
    linkedin_db_crosslink_resolver.py [--limit N] [--apply] [--db PATH] [--quiet]

Exit codes: 0 ok, 1 fatal (DB open failure).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
PROJ = HERE.parent
DEFAULT_DB = PROJ / "tracker.db"

# Reuse the exact source-key derivation the weekly LinkedIn pipeline uses, so a
# row this resolver rewrites gets the same canonical source_key shape as if the
# careers-probe tactic had resolved it.
from linkedin_resolver_pipeline import derive_source_key  # noqa: E402
# Respect the same company-handling policy the classifier/merger use: Microsoft /
# Amazon / AWS are Cyrus-handled (skip), Google is discovery-only but in scope.
from jd_llm_classifier import company_is_blocked  # noqa: E402


def _looks_like_canonical_source_key(sk: Optional[str]) -> bool:
    """True for proper `ats:slug:id`-shaped keys; False for raw-URL source_keys
    (a large slice of direct rows store the URL itself as source_key)."""
    if not sk or ":" not in sk:
        return False
    head = sk.split(":", 1)[0].lower()
    return head not in ("http", "https")


# --- normalization (identical semantics to linkedin_resolver_pipeline) -------

def normalize_title(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace(" sr ", " senior ").replace(" jr ", " junior ")
    s = re.sub(r"\bpm\b", "product manager", s)
    s = re.sub(r"\btpm\b", "technical program manager", s)
    return s


def norm_company(c: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (c or "").lower())


# --- index of direct-ATS rows ------------------------------------------------

# A direct-ATS row is any non-LinkedIn row with a real off-LinkedIn app_url that
# we are willing to reuse. We exclude closed/rejected so we never resurrect a
# dead posting.
DIRECT_SQL = """
    SELECT company, role, app_url, source_key
    FROM roles
    WHERE source_key NOT LIKE 'linkedin:%'
      AND app_url IS NOT NULL AND app_url != ''
      AND app_url NOT LIKE '%linkedin.com%'
      AND (status IS NULL OR status NOT IN ('closed', 'rejected'))
"""

# Stranded LinkedIn rows still pointing at a LinkedIn job page, not yet applied,
# not already cross-linked.
STRANDED_SQL = """
    SELECT id, company, role, app_url
    FROM roles
    WHERE source_key LIKE 'linkedin:%'
      AND app_url LIKE '%linkedin.com%'
      AND (applied_by IS NULL OR applied_by = '')
      AND (agent_notes IS NULL OR agent_notes NOT LIKE '%LINKEDIN-CROSSLINK%')
    ORDER BY id
"""


def build_direct_index(con: sqlite3.Connection
                       ) -> Dict[Tuple[str, str], set]:
    """(norm_company, norm_title) -> set of distinct (app_url, source_key)."""
    idx: Dict[Tuple[str, str], set] = {}
    for company, role, app_url, source_key in con.execute(DIRECT_SQL):
        key = (norm_company(company), normalize_title(role))
        if not key[0] or not key[1]:
            continue
        idx.setdefault(key, set()).add((app_url, source_key))
    return idx


def resolve_row(company: str, role: str,
                idx: Dict[Tuple[str, str], set]
                ) -> Optional[Tuple[str, str]]:
    """Return (app_url, source_key) iff exactly one distinct direct-ATS app_url
    exists for this (company, title); else None."""
    cands = idx.get((norm_company(company), normalize_title(role)))
    if not cands:
        return None
    urls = {c[0] for c in cands}
    if len(urls) != 1:
        return None  # ambiguous -> skip
    # pick the (url, source_key) for that single url (any source_key for it)
    target_url = next(iter(urls))
    for u, sk in cands:
        if u == target_url:
            return u, sk
    return None


def main(argv: Optional[Iterable[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="max stranded rows to attempt (0 = all)")
    ap.add_argument("--apply", action="store_true",
                    help="write to tracker.db (default: dry-run)")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)

    log = (lambda *a, **k: None) if args.quiet else print
    write_mode = bool(args.apply)

    try:
        con = sqlite3.connect(args.db)
    except Exception as e:  # pragma: no cover
        print(f"[crosslink] FATAL: cannot open {args.db}: {e}", file=sys.stderr)
        return 1

    idx = build_direct_index(con)
    stranded = con.execute(STRANDED_SQL).fetchall()
    if args.limit:
        stranded = stranded[: args.limit]
    log(f"[crosslink] direct-ATS keys={len(idx)} stranded-rows={len(stranded)} "
        f"mode={'APPLY' if write_mode else 'DRY-RUN'}", flush=True)

    stamp = datetime.now().strftime("%Y-%m-%d")
    resolved = ambiguous_or_miss = 0
    by_ats: Dict[str, int] = {}
    samples: List[dict] = []

    for i, (rid, company, role, li_url) in enumerate(stranded, 1):
        # Microsoft/Amazon/AWS stay Cyrus-handled -- never touch their rows.
        # (Google is allowed: it's discovery-only/manual-apply but in scope, so
        # improving its app_url is useful.)
        if company_is_blocked(company):
            ambiguous_or_miss += 1
            continue
        hit = resolve_row(company or "", role or "", idx)
        if not hit:
            ambiguous_or_miss += 1
            continue
        new_url, src_sk = hit
        # NOTE: roles.source_key is UNIQUE, and the matched direct row already
        # owns its canonical key -- so we must NOT copy it onto this row (that
        # collides). We only rewrite app_url (what inline_submit.detect_ats()
        # routes on) + agent_notes, and PRESERVE the original linkedin:<id>
        # source_key as this row's stable identity. We still compute the ATS
        # label purely for the summary/reporting.
        if _looks_like_canonical_source_key(src_sk):
            ats = src_sk.split(":", 1)[0]
        else:
            ats = derive_source_key(new_url).split(":", 1)[0]
        by_ats[ats] = by_ats.get(ats, 0) + 1
        resolved += 1
        if len(samples) < 8:
            samples.append({"id": rid, "company": company, "role": role,
                            "ats": ats, "url": new_url})
        if write_mode:
            note = (f"LINKEDIN-CROSSLINK {stamp}: matched direct-ATS row "
                    f"(same company+title) -> {ats} | original: {li_url}")
            con.execute(
                "UPDATE roles SET app_url=?, agent_notes=? WHERE id=?",
                (new_url, note, rid),
            )
            if i % 25 == 0:
                con.commit()

    if write_mode:
        con.commit()
    con.close()

    summary = {
        "mode": "apply" if write_mode else "dry-run",
        "stranded_attempted": len(stranded),
        "resolved": resolved,
        "ambiguous_or_miss": ambiguous_or_miss,
        "by_ats": by_ats,
        "sample_resolved": samples,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
