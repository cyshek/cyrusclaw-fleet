"""Orchestrator: load companies.yaml, fan out adapters in parallel, filter, write output.

Usage:
    python run.py                        # full sweep, write output/YYYYMMDD-HHMM-roles.json
    python run.py --only Anthropic       # one company
    python run.py --only-adapter ashby   # all companies on a given ATS
    python run.py --dry-run              # don't write output files
"""
from __future__ import annotations
import argparse
import concurrent.futures as cf
import json
import re
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
import yaml

# Make `core` and `adapters` importable when run from project dir
sys.path.insert(0, str(Path(__file__).parent))

from core import Role, is_qualifying_title, is_us_location, is_qualifying_experience  # noqa
from adapters import REGISTRY  # noqa


HERE = Path(__file__).parent
CONFIG = HERE / "companies.yaml"

# Per-company adapter hard timeout (seconds). Prevents one hung host (e.g. a
# dead lever/apple slug with no internal request timeout) from stalling the
# whole crawl, since output is written only after all futures complete.
ADAPTER_TIMEOUT_S = 90
OUT_DIR = HERE / "output"


def load_companies():
    with open(CONFIG, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["companies"]


def run_one(c: dict) -> tuple[dict, list[Role], str | None]:
    """Run one company. Returns (config, roles, error)."""
    if c.get("skip"):
        return c, [], "skip"
    adapter_name = c.get("adapter")
    if not adapter_name:
        return c, [], "no-adapter"
    fn = REGISTRY.get(adapter_name)
    if not fn:
        return c, [], f"unknown-adapter:{adapter_name}"

    name = c["name"]
    slug = c.get("slug", "")
    opts = {k: v for k, v in c.items() if k not in {"name", "adapter", "slug", "skip", "reason", "note"}}

    # Per-adapter hard timeout (2026-06-03): some adapters (lever, apple,
    # linkedin) have no per-request timeout and can hang on a dead host.
    # run() writes output only after ALL futures complete, so one hung
    # company would sink the whole crawl. Cap each company so a single bad
    # host degrades to a logged timeout instead of stalling everything.
    timeout_s = int(c.get("timeout_s") or ADAPTER_TIMEOUT_S)
    # NOTE: do NOT use `with ThreadPoolExecutor(...)` here — its __exit__ calls
    # shutdown(wait=True), which blocks until the hung worker finishes,
    # defeating the timeout. Submit on a throwaway executor and abandon it on
    # timeout (shutdown(wait=False)); the orphaned thread dies with the process.
    _one = cf.ThreadPoolExecutor(max_workers=1)
    try:
        fut = _one.submit(fn, name, slug, **opts)
        roles = fut.result(timeout=timeout_s)
        _one.shutdown(wait=False)
        return c, roles, None
    except cf.TimeoutError:
        _one.shutdown(wait=False, cancel_futures=True)
        return c, [], f"timeout>{timeout_s}s"
    except Exception as e:
        _one.shutdown(wait=False)
        return c, [], f"{type(e).__name__}: {e}"


def filter_roles(roles: list[Role]) -> list[Role]:
    """Apply title, exp, and location filter; dedupe same role × multi-location."""
    filtered = []
    for r in roles:
        if not is_qualifying_title(r.title):
            continue
        if not is_qualifying_experience(r.exp_required):
            continue
        if not is_us_location(r.location):
            continue
        filtered.append(r)

    # Dedupe by (company, normalized-title): same role posted to multiple US cities
    # collapses into one row. Keep the first one's URL but aggregate locations.
    by_key: dict[tuple[str, str], Role] = {}
    extra_locs: dict[tuple[str, str], list[str]] = {}
    for r in filtered:
        key = (r.company.lower(), re.sub(r"\s+", " ", r.title.lower()).strip())
        if key not in by_key:
            by_key[key] = r
            extra_locs[key] = [r.location] if r.location else []
        else:
            if r.location and r.location not in extra_locs[key]:
                extra_locs[key].append(r.location)

    out = []
    for key, r in by_key.items():
        locs = extra_locs[key]
        if len(locs) > 1:
            # join up to 3, then "(+N more)"
            shown = "; ".join(locs[:3])
            if len(locs) > 3:
                shown += f" (+{len(locs)-3} more)"
            r.location = shown
        out.append(r)

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="run a single company by name")
    ap.add_argument("--only-adapter", help="run only companies using this adapter")
    ap.add_argument("--only-new", action="store_true",
                    help="run only companies that have ZERO rows in tracker.db "
                         "(never-crawled employers) — fast targeted harvest of "
                         "newly-added companies.yaml entries without a full crawl")
    ap.add_argument("--names-file",
                    help="path to a JSON list of company names to restrict to")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    companies = load_companies()
    if args.only:
        companies = [c for c in companies if c["name"].lower() == args.only.lower()]
    if args.only_adapter:
        companies = [c for c in companies if c.get("adapter") == args.only_adapter]
    if args.names_file:
        import json as _json
        wanted = {n.strip().lower() for n in _json.load(open(args.names_file))}
        companies = [c for c in companies if c["name"].strip().lower() in wanted]
    if args.only_new:
        import sqlite3 as _sql
        _db = HERE.parent / "tracker.db"
        _con = _sql.connect(str(_db))
        _have = {r[0].strip().lower() for r in _con.execute(
            "SELECT DISTINCT company FROM roles WHERE company IS NOT NULL"
        ).fetchall() if r[0]}
        _con.close()
        companies = [c for c in companies
                     if c["name"].strip().lower() not in _have]
        print(f"--only-new: {len(companies)} never-crawled employers")
    if not companies:
        print("No companies match.")
        return

    print(f"Running {len(companies)} companies with {args.workers} workers...")
    t0 = time.time()

    all_roles: list[Role] = []
    successes, failures, skips = [], [], []

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(run_one, c): c for c in companies}
        for fut in cf.as_completed(futures):
            c, roles, err = fut.result()
            name = c["name"]
            if err == "skip":
                skips.append((name, c.get("reason", "")))
                continue
            if err:
                failures.append((name, err))
                print(f"  FAIL  {name:25} {err}")
                continue
            kept = filter_roles(roles)
            successes.append((name, len(roles), len(kept)))
            all_roles.extend(kept)
            print(f"  OK    {name:25} fetched={len(roles):4}  kept={len(kept):3}")

    dt = time.time() - t0
    print(f"\nDone in {dt:.1f}s. {len(successes)} ok, {len(failures)} failed, {len(skips)} skipped.")
    print(f"Total qualifying roles: {len(all_roles)}")

    if args.dry_run:
        return

    OUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out_json = OUT_DIR / f"{stamp}-roles.json"
    out_meta = OUT_DIR / f"{stamp}-meta.json"
    out_log = OUT_DIR / f"{stamp}-run.log"

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in all_roles], f, indent=2)
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": stamp,
            "duration_sec": round(dt, 1),
            "successes": [{"company": n, "fetched": fe, "kept": k} for n, fe, k in successes],
            "failures": [{"company": n, "error": e} for n, e in failures],
            "skips": [{"company": n, "reason": r} for n, r in skips],
        }, f, indent=2)
    with open(out_log, "w", encoding="utf-8") as f:
        f.write(f"Run timestamp: {stamp}\n")
        f.write(f"Duration: {dt:.1f}s\n\n")
        f.write(f"=== SUCCESS ({len(successes)}) ===\n")
        for n, fetched, kept in sorted(successes, key=lambda x: -x[2]):
            f.write(f"  {n:25} fetched={fetched:4}  kept={kept:3}\n")
        f.write(f"\n=== FAILURES ({len(failures)}) ===\n")
        for n, err in sorted(failures):
            f.write(f"  {n:25} {err}\n")
        f.write(f"\n=== SKIPPED ({len(skips)}) ===\n")
        for n, reason in sorted(skips):
            f.write(f"  {n:25} {reason}\n")

    print(f"\nWrote: {out_json}")
    print(f"Wrote: {out_log}")
    return out_json


if __name__ == "__main__":
    main()
    # A few adapters (apple/linkedin) can leave an orphaned worker thread
    # blocked on a network call after we hit the per-company timeout. Those
    # non-daemon threads would otherwise keep the interpreter alive long after
    # the output JSON is written. Output is already flushed above, so force a
    # clean exit past any orphaned threads.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
