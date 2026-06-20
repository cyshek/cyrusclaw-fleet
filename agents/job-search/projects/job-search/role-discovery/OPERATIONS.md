# role-discovery — operations

Migrated from Cyrus's Windows box to this VM on 2026-05-06.
**As of 2026-05-06, the VM is the sole source of truth.** The Windows
scheduled task has been disabled.

## Layout

```
role-discovery/
├── .venv/                      # python3 + requests + pyyaml + openpyxl
├── adapters/                   # one .py per ATS
├── output/                     # crawl outputs (gitignored if/when this is a repo)
│   ├── {stamp}-roles.json      # main role data from each crawl
│   ├── {stamp}-meta.json       # failures, skips, timing
│   ├── {stamp}-run.log         # verbose log
│   ├── {stamp}-delta.md        # daily NEW-roles diff
│   └── daily_runs.log          # rolling cron log
├── companies.yaml              # source of truth — 261 companies
├── run.py                      # main crawl entry
├── tracker_merger.py           # merges fresh roles into ../tracker.md
├── strip_non_us.py             # strips non-US rows from ../tracker.md
├── rank_roles.py               # writes ../Cyrus_Top_Roles.md
├── tracker_to_xlsx.py          # writes ../Cyrus_Job_Tracker.xlsx
├── delta_digest.py             # diff latest two -roles.json
├── daily_run.sh                # cron wrapper (full pipeline)
├── slug_sweep.py               # dev tool — re-discover broken slugs
├── bulk_discover_slugs.py      # dev tool — probe new candidate companies
└── playwright_slug_probe.py    # dev tool — JS-rendered careers (NOT installed)
```

## Outputs (in the parent project dir, `projects/job-search/`)

- `tracker.md` — canonical job-search tracker, updated in place daily
- `tracker.md.{stamp}.bak` — last 14 backups of tracker.md (auto-rotated)
- `Cyrus_Top_Roles.md` — top 50 queued roles, ranked by fit score
- `Cyrus_Job_Tracker.xlsx` — full tracker as XLSX with classification + summary sheets
- `new_roles_since_last_run.md` — new-only diff for the latest run

## Daily cron

- Schedule: `0 14 * * *` UTC = **07:00 PDT** (06:00 PST)
- Installed via `crontab -e` for `azureuser`
- Verify with `crontab -l`
- Wrapper: `daily_run.sh` runs the full 7-step pipeline and appends to `output/daily_runs.log`

## Pipeline steps (in order)

1. **Crawl** — `run.py --workers 12` hits all ATS adapters, writes `output/{stamp}-roles.json` + `-meta.json` + `-run.log`
2. **Backup** — copies current `tracker.md` to `tracker.md.{stamp}.bak`, prunes to 14 latest
3. **Merge** — `tracker_merger.py` adds brand-new roles, auto-closes vanished queued rows, preserves submitted/interview rows
4. **Strip non-US** — `strip_non_us.py` removes rows whose location fails `is_us_location()` (preserves submitted/applied)
5. **Rank** — `rank_roles.py` scores queued roles by title fit / comp tier / ATS friendliness / location, writes top 50
6. **XLSX** — `tracker_to_xlsx.py` exports the full tracker with row classification (real / stub / placeholder) and per-company sheet
7. **Delta digest** — `delta_digest.py` diffs the latest two `-roles.json` files and writes `output/{stamp}-delta.md`

## Manual invocation

```bash
cd ~/.openclaw/agents/job-search/workspace/projects/job-search/role-discovery
./daily_run.sh                      # full daily flow
.venv/bin/python run.py --workers 12      # crawl only
.venv/bin/python delta_digest.py          # diff only
.venv/bin/python rank_roles.py            # re-rank from current tracker.md
.venv/bin/python tracker_to_xlsx.py       # re-export XLSX
```

## Tools NOT installed on the VM (intentional)

- **Playwright** — only used by the dev-only `playwright_slug_probe.py`. Install with `pip install playwright && playwright install chromium` if needed (~150 MB).

## Drift watch

`companies.yaml` exists in two places (Windows + this VM) with no sync mechanism.
**Treat the VM copy as source of truth.** If you edit Windows, scp it back to the VM, not the other way around.

## Rollback

If a daily run produces a bad tracker:
```bash
cd ~/.openclaw/agents/job-search/workspace/projects/job-search
ls -t tracker.md.*.bak | head        # pick the right backup
cp tracker.md.20260506-2042.bak tracker.md
```

## Access from the VM directly

`~/.bashrc` has these aliases for SSH sessions on the VM:

| Alias | What it does |
|---|---|
| `ocj "message"` | One-shot turn to the job-search agent |
| `ocj-tail` | Tail `output/daily_runs.log` |
| `ocj-cd` | `cd` into role-discovery dir |
| `ocj-run` | Run the full daily pipeline manually |

For interactive chat: `openclaw chat` (defaults to `main` agent — use `ocj` for job-search).

Web UI on the VM: `http://127.0.0.1:18789/webchat` (loopback only — needs SSH tunnel from Windows). Token in `~/.openclaw/openclaw.json` → `gateway.auth.token`.

