# Phantom Re-probe Status (2026-06-08)

Backup: tracker.db.bak.phantom-reprobe-20260609-045400 (integrity ok before)

| id | company | OLD reason | NEW verdict | DB action |
|----|---------|-----------|-------------|-----------|
| 1384 | Cartesia | OTHER | SPECIFIC-WALL: ashby-required-portfolio-url | keep blocked, relabel |
| 2527 | Snowflake | OTHER | PREP-READY (clobber-risk note) | -> queued |
| 2548 | Drata | HARD-WALL | PREP-READY | -> queued |
| 2557 | Curri | HARD-WALL | PREP-READY | -> queued |
| 2563 | Ambient.ai | OTHER | PREP-READY | -> queued |
| 2593 | Knowtex | OTHER | PREP-READY | -> queued |
| 2605 | Ready | OTHER | PREP-READY | -> queued |
| 2606 | Anara | OTHER | PREP-READY | -> queued |
| 2688 | Pure Storage | label-gap | CLOSED (gh 404, off board) | -> closed |
| 2748 | Nintendo | gh-blank-label-required-uncertain | PREP-READY | -> queued |
| 2781 | Antithesis | OTHER | PREP-READY | -> queued |
| 2799 | Paystand | gh-blank-label-required-uncertain | PREP-READY | -> queued |

Summary: 10 -> queued, 1 relabeled-specific (Cartesia portfolio), 1 closed (Pure Storage).
Evidence: ashby_dryrun ready_to_submit=True+blockers=0 for the 8 ashby; gh dryrun ready_to_submit=true+unresolved=0 for Nintendo/Paystand; Pure Storage boards-api 404 + absent from 329-job board.
ENGINE GAP: none of these are engine bugs; the OTHER/HARD-WALL/label-gap strings were stale (predate final_clobber_guard, needs_review auto-commit, full_address + education-typeahead, _gh_submit needs_review commit). Minor: Cartesia needs a portfolio_url in personal-info OR a resolver that declines optional-portfolio (here portfolio is REQUIRED so it's a genuine data gap, not an engine fix).
