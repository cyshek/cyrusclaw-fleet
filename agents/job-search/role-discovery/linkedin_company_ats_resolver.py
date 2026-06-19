#!/usr/bin/env python3
"""LinkedIn-stranded row -> real ATS apply-URL resolver (NO li_at, NO browser).

Cyrus directive (2026-06-09): "all the LinkedIn links point to an actual
company, so use that to find the role." We already capture the company NAME on
every LinkedIn-stranded row (status='manual-apply', app_url = a
linkedin.com/jobs/view/... pointer). The LinkedIn URL is a lossy pointer; the
REAL posting lives on the company's own ATS board, which we can fetch
anonymously via the SAME adapter the weekly crawl already uses
(greenhouse/ashby/lever/workday board APIs — no auth).

This script:
  1. SELECTs stranded rows (status='manual-apply' AND app_url LIKE
     '%linkedin.com/jobs/view%').
  2. Matches each row's company to a companies.yaml entry (exact +
     CONSERVATIVE normalized match; fuzzy is intentionally NOT used because it
     mis-routes — e.g. "Spot AI" -> "SpotOn", "Teradata" -> "Strada").
  3. For a matched company, fetches its CURRENT ATS board (cached per company
     so we hit each board once) and finds the open posting whose title best
     matches the stranded row's title (normalized exact, then a high-threshold
     token-overlap match). That posting's apply URL is the REAL ATS URL.
  4. Classifies each row: RESOLVED / NO_BOARD_MATCH / BOARD_BUT_NO_TITLE_MATCH,
     writes linkedin_resolve_report.json, prints a summary.

DRY-RUN by default (no DB writes). With --apply it backs up the DB, runs
PRAGMA integrity_check before+after, and for RESOLVED rows sets
app_url=<real ATS url>, status='' (back into the actionable queue), and
appends an agent_notes line. It NEVER marks anything 'applied' — resolution
!= submission; the normal submit pipeline picks the rows up later.

Usage (from role-discovery/):
    .venv/bin/python linkedin_company_ats_resolver.py            # dry-run
    .venv/bin/python linkedin_company_ats_resolver.py --apply    # write
    .venv/bin/python linkedin_company_ats_resolver.py --limit-companies 40
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import re
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# canonical DB is ../tracker.db (the role-discovery/tracker.db is a 0-byte stray)
DB_PATH = (HERE.parent / "tracker.db").resolve()
COMPANIES_YAML = HERE / "companies.yaml"
REPORT_PATH = HERE / "linkedin_resolve_report.json"

from adapters import REGISTRY  # noqa: E402
# Reuse the EXACT normalization the LinkedIn adapter / dedup uses so company &
# title keys line up with the rest of the pipeline.
from adapters.linkedin import _norm_company, _norm_title  # noqa: E402

# Adapters whose boards are anonymously fetchable list-style endpoints we can
# scan for a title match. (microsoft/google/apple/meta/uber/snap/bytedance are
# special single-company adapters with their own quirks; we still allow them if
# a stranded company maps to one, but the common case is the four below.)
FETCHABLE_ADAPTERS = {
    "greenhouse", "ashby", "lever", "workday", "smartrecruiters",
    "workable", "eightfold", "microsoft", "google", "apple", "meta",
    "snap", "uber", "rippling", "bytedance", "tiktok",
}

# Keys that are adapter OPTIONS (passed as **opts), mirroring run.run_one().
_NON_OPT_KEYS = {"name", "adapter", "slug", "skip", "reason", "note"}

# Title-overlap threshold for a confident fuzzy title match (Jaccard on
# significant tokens). Normalized-exact always wins first. Raised to 0.7 after
# a dry-run showed loose matching collapsing distinct stranded roles onto a
# generic board stub (e.g. "Product Manager I, AI/ML" -> bare "Product
# Manager"; "Technical Program Manager" -> "Principal Lead Technical Program
# Manager - Windows..."). We REQUIRE a shared distinctive (non-generic) token
# too, so two roles can't match on generic role words alone.
TITLE_OVERLAP_MIN = 0.7

# Per-company board-fetch hard timeout (seconds). Mirrors run.ADAPTER_TIMEOUT_S.
# Some adapters (notably Workday, which loops 7 search terms x pagination on
# huge tenants like Cisco) have no internal request cap and can grind for many
# minutes. Bounding each board keeps the run finite + resumable; a slow board
# degrades to a logged timeout (-> BOARD_BUT_NO_TITLE_MATCH) instead of
# stalling everything.
ADAPTER_TIMEOUT_S = 60

# Generic title tokens that should not by themselves carry a match.
_STOP_TOKENS = {
    "the", "a", "an", "of", "and", "or", "for", "to", "in", "at", "on",
    "i", "ii", "iii", "iv", "v", "sr", "jr", "new", "grad",
}


def log(*a):
    print(*a, flush=True)


# Generic role tokens: a title made up ONLY of these (after stop-token removal)
# is a non-distinctive stub and may match a stranded row ONLY by exact title,
# never by overlap (prevents "Product Manager I, AI/ML" -> bare "Product
# Manager" false hits).
_GENERIC_TOKENS = {
    "product", "program", "project", "manager", "sales", "solutions",
    "solution", "engineer", "architect", "technical", "associate",
    "customer", "senior", "staff", "lead", "principal", "strategy",
    "operations", "business", "analyst", "specialist",
}

# Companies Cyrus handles himself (never auto-resolve into the actionable
# queue). Mirrors jd_llm_classifier.COMPANY_BLOCKLIST (Microsoft / Amazon /
# AWS). Word-boundary regex so "Microsoft" matches but a substring won't
# over-match.
_BLOCKLIST_RE = [
    re.compile(r"\bmicrosoft\b", re.I),
    re.compile(r"\bamazon\b", re.I),
    re.compile(r"\baws\b", re.I),
]

# Companies that are discovery-only / manual-apply by policy: we may UPGRADE
# the URL (LinkedIn pointer -> real careers URL) but MUST keep
# status='manual-apply' rather than dropping into the auto-submit queue.
# Google careers is SSO-walled (GOOGLE-CAREERS-RECON verdict) -- never
# auto-submittable, so a resolved Google row stays manual-apply.
_MANUAL_APPLY_RE = [
    re.compile(r"\bgoogle\b", re.I),
    re.compile(r"\balphabet\b", re.I),
]


def is_blocklisted(company: str) -> bool:
    return any(rx.search(company or "") for rx in _BLOCKLIST_RE)


def is_manual_apply_only(company: str) -> bool:
    return any(rx.search(company or "") for rx in _MANUAL_APPLY_RE)


# --------------------------------------------------------------------------- #
# company matching
# --------------------------------------------------------------------------- #
def load_company_index() -> dict[str, dict]:
    data = yaml.safe_load(open(COMPANIES_YAML, encoding="utf-8"))
    idx: dict[str, dict] = {}
    for c in data["companies"]:
        if not c.get("adapter"):
            continue
        key = _norm_company(c["name"])
        # First write wins; companies.yaml has no dup names in practice.
        idx.setdefault(key, c)
    return idx


def match_company(company: str, idx: dict[str, dict]) -> dict | None:
    """Exact-normalized company match only (deliberately conservative)."""
    key = _norm_company(company)
    if not key:
        return None
    return idx.get(key)


# --------------------------------------------------------------------------- #
# board fetch (cached per company-config id)
# --------------------------------------------------------------------------- #
def fetch_board(cfg: dict, cache: dict) -> tuple[list, str | None]:
    """Return (roles, error). Mirrors run.run_one() opts handling. Cached by
    the config's identity so each board is hit at most once per run."""
    cache_key = (cfg.get("adapter"), cfg.get("name"), cfg.get("slug", ""))
    if cache_key in cache:
        return cache[cache_key]

    if cfg.get("skip"):
        res = ([], f"skip:{cfg.get('reason', '')[:60]}")
        cache[cache_key] = res
        return res

    adapter = cfg.get("adapter")
    fn = REGISTRY.get(adapter)
    if not fn:
        res = ([], f"unknown-adapter:{adapter}")
        cache[cache_key] = res
        return res

    name = cfg["name"]
    slug = cfg.get("slug", "")
    opts = {k: v for k, v in cfg.items() if k not in _NON_OPT_KEYS}
    timeout_s = int(cfg.get("timeout_s") or ADAPTER_TIMEOUT_S)
    # Throwaway single-worker executor + shutdown(wait=False) on timeout so an
    # orphaned hung fetch thread dies with the process instead of blocking us
    # (same pattern as run.run_one()).
    _one = cf.ThreadPoolExecutor(max_workers=1)
    try:
        fut = _one.submit(fn, name, slug, **opts)
        roles = fut.result(timeout=timeout_s)
        _one.shutdown(wait=False)
        res = (roles or [], None)
    except cf.TimeoutError:
        _one.shutdown(wait=False, cancel_futures=True)
        res = ([], f"timeout>{timeout_s}s")
    except Exception as e:  # noqa: BLE001
        _one.shutdown(wait=False)
        res = ([], f"{type(e).__name__}:{str(e)[:80]}")
    cache[cache_key] = res
    # Be polite between distinct board fetches.
    time.sleep(0.4)
    return res


# --------------------------------------------------------------------------- #
# title matching
# --------------------------------------------------------------------------- #
def _sig_tokens(title: str) -> set[str]:
    toks = set(_norm_title(title).split())
    return {t for t in toks if t not in _STOP_TOKENS and len(t) > 1}


def match_title(stranded_title: str, roles: list):
    """Find the best board posting for a stranded title.
    Returns (role, match_kind) or (None, None).
    match_kind in {'exact', 'overlap:<score>'}.

    Deliberately STRICT: a dry-run showed loose substring matching collapsing
    distinct stranded roles onto a generic board stub. So:
      1. normalized-exact wins.
      2. otherwise require Jaccard token-overlap >= TITLE_OVERLAP_MIN AND a
         shared DISTINCTIVE (non-generic) token, so two roles can never match
         on generic role words ('product manager', 'sales engineer') alone.
    The old substring rule is removed entirely.
    """
    want_norm = _norm_title(stranded_title)
    want_toks = _sig_tokens(stranded_title)
    want_distinct = want_toks - _GENERIC_TOKENS

    # 1) normalized-exact
    for r in roles:
        if want_norm and _norm_title(r.title) == want_norm:
            return r, "exact"

    # 2) high-threshold token-overlap WITH a shared distinctive token
    if want_toks:
        best = None
        best_score = 0.0
        for r in roles:
            rt = _sig_tokens(r.title)
            if not rt:
                continue
            inter = want_toks & rt
            union = want_toks | rt
            score = len(inter) / len(union) if union else 0.0
            # require at least one shared NON-generic token, so e.g. a
            # "Product Manager, Crypto Trading" only matches a board posting
            # that also shares 'crypto'/'trading', never a bare "Product
            # Manager".
            shared_distinct = (want_distinct & rt) - _GENERIC_TOKENS
            if score > best_score and shared_distinct:
                best_score = score
                best = r
        if best is not None and best_score >= TITLE_OVERLAP_MIN:
            return best, f"overlap:{best_score:.2f}"

    return None, None


# --------------------------------------------------------------------------- #
# main resolve
# --------------------------------------------------------------------------- #
def resolve(limit_companies: int | None = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, company, role, loc, app_url FROM roles "
        "WHERE status='manual-apply' AND app_url LIKE '%linkedin.com/jobs/view%' "
        "ORDER BY id ASC"
    ).fetchall()
    conn.close()

    log(f"Stranded LinkedIn rows: {len(rows)}")
    idx = load_company_index()

    # Group rows by matched company so we fetch each board once and can respect
    # a --limit-companies cap deterministically.
    matched_cfg_for_company: dict[str, dict | None] = {}
    for r in rows:
        co = r["company"]
        if co not in matched_cfg_for_company:
            matched_cfg_for_company[co] = match_company(co, idx)

    # Deterministic order of companies that DID match a fetchable adapter.
    # Exclude blocklisted companies from board fetching entirely.
    fetchable_companies = [
        co for co, cfg in matched_cfg_for_company.items()
        if cfg and cfg.get("adapter") in FETCHABLE_ADAPTERS and not is_blocklisted(co)
    ]
    fetchable_companies.sort(key=lambda s: s.lower())
    capped = set(fetchable_companies)
    if limit_companies is not None:
        capped = set(fetchable_companies[:limit_companies])
        log(f"--limit-companies={limit_companies}: fetching boards for "
            f"{len(capped)}/{len(fetchable_companies)} matched companies")

    board_cache: dict = {}
    _logged_fetch: set = set()
    results = []
    for r in rows:
        co = r["company"]
        cfg = matched_cfg_for_company[co]
        rec = {
            "id": r["id"],
            "company": co,
            "title": r["role"],
            "loc": r["loc"],
            "old_url": r["app_url"],
        }
        if not cfg or cfg.get("adapter") not in FETCHABLE_ADAPTERS:
            rec["bucket"] = "NO_BOARD_MATCH"
            rec["reason"] = "no-companies.yaml-match" if not cfg else f"non-fetchable-adapter:{cfg.get('adapter')}"
            results.append(rec)
            continue
        if is_blocklisted(co):
            # Microsoft / Amazon / AWS -- Cyrus handles himself; never resolve
            # into the actionable queue.
            rec["bucket"] = "BLOCKLISTED_SKIP"
            rec["reason"] = "company-blocklist (Cyrus handles)"
            rec["matched_company"] = cfg["name"]
            rec["ats"] = cfg["adapter"]
            results.append(rec)
            continue
        if co not in capped:
            rec["bucket"] = "DEFERRED_CAP"
            rec["reason"] = "skipped by --limit-companies (resume to process)"
            rec["matched_company"] = cfg["name"]
            rec["ats"] = cfg["adapter"]
            results.append(rec)
            continue

        roles, err = fetch_board(cfg, board_cache)
        rec["matched_company"] = cfg["name"]
        rec["ats"] = cfg["adapter"]
        if (cfg.get("adapter"), cfg.get("name"), cfg.get("slug", "")) not in _logged_fetch:
            _logged_fetch.add((cfg.get("adapter"), cfg.get("name"), cfg.get("slug", "")))
            log(f"  [board] {cfg['name']} via {cfg['adapter']}: "
                f"{len(roles)} postings{(' ERR:' + err) if err else ''}")
        if err and not roles:
            rec["bucket"] = "BOARD_BUT_NO_TITLE_MATCH"
            rec["reason"] = f"board-fetch-failed:{err}"
            results.append(rec)
            continue

        role, kind = match_title(r["role"], roles)
        if role is None:
            rec["bucket"] = "BOARD_BUT_NO_TITLE_MATCH"
            rec["reason"] = f"no-title-match (board had {len(roles)} postings)"
            results.append(rec)
            continue

        rec["bucket"] = "RESOLVED"
        rec["new_url"] = role.url
        rec["matched_title"] = role.title
        rec["match_kind"] = kind
        rec["matched_loc"] = role.location
        # Google/Alphabet stay manual-apply (SSO-walled, never auto-submittable)
        # -- we only UPGRADE the URL. Everyone else goes to the actionable
        # queue (status='').
        rec["target_status"] = "manual-apply" if is_manual_apply_only(co) else ""
        results.append(rec)

    return results


# --------------------------------------------------------------------------- #
# reporting + apply
# --------------------------------------------------------------------------- #
def summarize(results: list) -> dict:
    buckets: dict[str, list] = {}
    for r in results:
        buckets.setdefault(r["bucket"], []).append(r)
    counts = {k: len(v) for k, v in buckets.items()}
    return {"counts": counts, "buckets": buckets}


def print_summary(results: list):
    s = summarize(results)
    log("\n=== RESOLVE SUMMARY ===")
    for b in ("RESOLVED", "BOARD_BUT_NO_TITLE_MATCH", "NO_BOARD_MATCH",
              "BLOCKLISTED_SKIP", "DEFERRED_CAP"):
        log(f"  {b:26} {s['counts'].get(b, 0)}")
    log(f"  {'TOTAL':26} {len(results)}")

    resolved = s["buckets"].get("RESOLVED", [])
    if resolved:
        log("\n--- RESOLVED (old -> new) ---")
        for r in resolved[:20]:
            tgt = r.get("target_status", "")
            tgt_label = "manual-apply" if tgt == "manual-apply" else "queue"
            log(f"  [{r['id']}] {r['company']} | {r['title'][:48]!r} -> {tgt_label}")
            log(f"       via {r['ats']} ({r['match_kind']}) -> matched {r['matched_title'][:48]!r}")
            log(f"       OLD {r['old_url']}")
            log(f"       NEW {r['new_url']}")

    # Distinct NO_BOARD_MATCH companies (what the cheap web-search key unlocks).
    nbm = s["buckets"].get("NO_BOARD_MATCH", [])
    nbm_companies = sorted({r["company"] for r in nbm}, key=lambda x: x.lower())
    log(f"\n--- NO_BOARD_MATCH distinct companies ({len(nbm_companies)}) ---")
    log("  " + ", ".join(nbm_companies))
    return s


def integrity_check(db_path: Path) -> str:
    c = sqlite3.connect(db_path)
    res = c.execute("PRAGMA integrity_check").fetchone()[0]
    c.close()
    return res


def apply_changes(results: list) -> dict:
    resolved = [r for r in results if r["bucket"] == "RESOLVED"]
    if not resolved:
        log("\n[apply] No RESOLVED rows — nothing to write.")
        return {"changed": 0}

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DB_PATH.parent / f"tracker.db.bak.linkedin-resolve-{ts}"
    shutil.copy2(DB_PATH, bak)
    log(f"\n[apply] Backed up DB -> {bak}")

    pre = integrity_check(DB_PATH)
    log(f"[apply] integrity_check BEFORE: {pre}")
    if pre != "ok":
        log("[apply] ABORT: pre-write integrity_check is not 'ok'.")
        return {"changed": 0, "aborted": "pre-integrity"}

    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    n_changed = 0
    for r in resolved:
        target_status = r.get("target_status", "")
        note_line = (f"linkedin->ATS resolved {today}: "
                     f"{r['matched_company']} / {r['matched_title']} via {r['ats']}"
                     f" [{r['match_kind']}]")
        cur = conn.execute("SELECT agent_notes FROM roles WHERE id=?", (r["id"],))
        row = cur.fetchone()
        existing = (row[0] if row and row[0] else "")
        new_notes = (existing + ("\n" if existing else "") + note_line)
        conn.execute(
            "UPDATE roles SET app_url=?, status=?, agent_notes=? WHERE id=?",
            (r["new_url"], target_status, new_notes, r["id"]),
        )
        n_changed += 1
    conn.commit()
    conn.close()

    post = integrity_check(DB_PATH)
    log(f"[apply] integrity_check AFTER:  {post}")
    log(f"[apply] rows updated: {n_changed}")
    return {"changed": n_changed, "backup": str(bak),
            "integrity_before": pre, "integrity_after": post}


def post_apply_status_counts():
    conn = sqlite3.connect(DB_PATH)
    # status of rows that were stranded LinkedIn pointers, now possibly moved.
    rows = conn.execute(
        "SELECT status, COUNT(*) FROM roles "
        "WHERE app_url LIKE '%greenhouse%' OR app_url LIKE '%ashby%' "
        "OR app_url LIKE '%lever%' OR app_url LIKE '%myworkday%' "
        "GROUP BY status"
    ).fetchall()
    conn.close()
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write resolved URLs back to tracker.db (default: dry-run)")
    ap.add_argument("--limit-companies", type=int, default=None,
                    help="cap board fetches to first N matched companies (resume aid)")
    args = ap.parse_args()

    log(f"DB: {DB_PATH}")
    log(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")

    results = resolve(limit_companies=args.limit_companies)
    s = print_summary(results)

    out = {
        "generated_at": datetime.now().isoformat(),
        "db": str(DB_PATH),
        "mode": "apply" if args.apply else "dry-run",
        "counts": s["counts"],
        "results": results,
    }
    REPORT_PATH.write_text(json.dumps(out, indent=2, default=str))
    log(f"\nReport written -> {REPORT_PATH}")

    if args.apply:
        res = apply_changes(results)
        out["apply_result"] = res
        REPORT_PATH.write_text(json.dumps(out, indent=2, default=str))
        log(f"[apply] result: {res}")


if __name__ == "__main__":
    main()
