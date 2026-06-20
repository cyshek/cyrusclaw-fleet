# Plan: scaling tailored-resume generation to all open roles

_Drafted 2026-05-13 by planning subagent. Read once, decide._

## Current state (the numbers)

- **Open roles in tracker.db** (`status IN (NULL,'',queued)` AND `applied_by=''`): **215**
- **Status distribution**: 455 skip · 224 closed · 39 none · 3 scan-blocked · 1 submitted · 227 empty (queue)
- **`applications/queued/<slug>/` folders**: 49 total (~23% of open queue)
- **Folders with `_v2.pdf` (tailored render)**: **7** (~3% of open queue)
- **Greenhouse rows in DB**: 75 — only ~35% of open roles. Rest are Apple, DeepMind, Lever, Ashby, Workday, etc.

## Cross-cutting findings (read these before picking an option)

### 1. `applications/queued/<slug>/` is **NOT auto-created today**

`weekly_run.sh` does: crawl → backup db → merge → render xlsx → delta digest. **It never touches `applications/queued/`.**

The only stager that exists, `applications/_stage_greenhouse.py`, is **broken** — it still reads the retired `tracker.md` (which doesn't exist; was frozen 2026-05-11 per MEMORY.md). Even when working, it was Greenhouse-only.

**Implication:** the 49 existing queued/ folders were hand-curated or built by historical _stage_greenhouse runs against the old tracker.md. Either Option A or Option B has to solve packet creation FIRST. `bullet_rewriter --render` requires `applications/queued/{org}-{job_id}/JD.md` to already exist.

### 2. Marginal cost per render

- Model: `github-copilot/claude-opus-4.7` via openclaw model CLI.
- Per render: 1 base call + 0–2 page-fit loops × 1–2 retries each → typically **1–4 model calls**, each with a ~3–8K-char prompt and ~2–4K-char JSON response.
- Recent timestamps show full renders completing inside 1–2 minutes wall-clock when the first attempt validates.
- **Token estimate per role**: ~10–25K input + ~5–10K output across all calls. Opus pricing is the priciest in the Copilot lineup, but billing is on the Copilot subscription, not metered per call. **Real cost is wall-clock + LLM rate-limit pressure, not dollars.**
- For 215 roles × ~90s avg = **~5.4 hours serial wall-clock**.

### 3. Where tailoring is wasteful — confirm we skip

- Skip `status IN ('skip','closed','scan-blocked','none')` and any row with `applied_by != ''` (already submitted). The 215 figure already excludes these.
- Don't tailor for roles where the JD can't be fetched (non-Greenhouse with no JD adapter). About 65% of open rows are non-Greenhouse — for those we have no automated JD-fetch path today, so render isn't possible without manual JD copy-paste OR new ATS adapters.

### 4. The 215 are NOT all submittable today

- ~75 Greenhouse rows → can be staged + tailored + auto-submitted (greenhouse_filler exists).
- ~140 are Apple, DeepMind, Lever, Ashby, Workday, etc. — **no auto-submit, no JD-stager**. Tailoring them produces a PDF Cyrus could attach manually, but most of the value chain (auto-submit) doesn't exist for them.

**Realistic addressable pool for full automation today: ~75 Greenhouse roles, of which 49 already have packets and 7 already have v2 PDFs → ~42 fresh renders needed.**

---

## Option A — Hook `bullet_rewriter --render` into `weekly_run.sh`

**Slot in:** new Step 6, AFTER delta digest. Crawl/merge/render-xlsx/digest are all read-only-ish bookkeeping; render is the expensive bit and should fail loudly without polluting the tracker.

**Inputs:** iterate `tracker.db` open Greenhouse rows (status in (NULL,'',queued), applied_by='') that DO NOT have a `Cyrus_Shekari_Resume_*_v2.pdf` in their queued/ folder. New roles only — incremental by construction.

**Sub-step required first:** weekly_run also has to STAGE Greenhouse packets (rewrite `_stage_greenhouse.py` to read tracker.db). Currently broken; without this, render has nothing to operate on.

**Cost per weekly run:**
- Steady state after backfill: ~5–15 new Greenhouse roles/week (delta digest typical) → 5–15 renders → **8–25 minutes added to weekly job**.
- First run after deploy: tries to render the entire 42-role backlog → ~60–90 min wall-clock if serial.

**Failure handling:** wrap each role in try/except, log to `output/weekly-render-failures.md`, **continue**. Never block the weekly run on one bad JD/render. Page-fit "give up after retries" is already built into bullet_rewriter and returns the previous-good rewrite.

**Pros:**
- Self-maintaining. Once shipped, every new Greenhouse role gets a tailored PDF within a week of appearing.
- Aligns with existing weekly cadence Cyrus already trusts.

**Cons:**
- Requires also fixing `_stage_greenhouse.py` (port to tracker.db). That's a real chunk of work.
- Doesn't solve non-Greenhouse roles (140 of 215). They sit in the queue without packets.
- Adds 8–25 min to weekly run; if model CLI flakes, we eat retries inside the cron window.

---

## Option B — Bulk-prep on demand (one-shot subagent)

**Flow:**
1. Walk `tracker.db` open Greenhouse roles.
2. For each: ensure `applications/queued/<slug>/` exists (call a fixed stager for JD.md/meta.json). Skip if folder + JD.md already present.
3. If `_v2.pdf` missing → run `bullet_rewriter --render`.
4. Log success/failure per role to `output/bulk-render-{stamp}.log`.

**Concurrency:**
- LLM calls: model CLI is subprocess-per-call; no documented rate limit visible, but Copilot backend will throttle. Conservative parallelism = **3 concurrent renders**. 8 would risk 429s and possibly noisy validation retries.
- python-docx + pdftotext: CPU-light, no contention concern at N=3.
- Page-fit loop is serialized within a single role anyway.

**Wall-clock estimates (42 fresh Greenhouse renders):**
- Serial (N=1): ~60–90 min
- N=3: ~25–35 min ← **recommended**
- N=8: ~15–20 min, but 429-risk

**Resume-on-restart:** trivially yes — the script's "skip if `_v2.pdf` exists" check makes the operation idempotent. Re-run the subagent and it picks up where it died.

**Pros:**
- One decisive action. Ship the backlog in 30 minutes, then move on.
- Doesn't require touching weekly_run.sh (less surface area to break).
- Easy to gate on Cyrus's review before mass auto-submit.

**Cons:**
- One-shot — new roles next week need either a manual re-run or Option A anyway. **Option B alone is not a long-term solution.**

---

## My recommendation: **Both, in this order — B first, then a trimmed A.**

**Why:**

1. **B is the right next 30 minutes.** 42 Greenhouse renders is a finite, well-bounded job. Knock it out tonight and Cyrus has tailored PDFs ready for a submit sprint tomorrow. Don't let perfect-pipeline-engineering block a quick win.
2. **A is the right long-term posture, but it depends on a stager rewrite.** Doing A first means writing the stager, wiring it in, AND eating the 60-90 min backlog inside a single cron window — too many moving parts to land at once.
3. **Both share the same dependency** (stager that reads tracker.db). Build it once, reuse it for B, then promote the same code into weekly_run.sh for A.
4. **Non-Greenhouse roles (140) are out of scope for both options today** — they need ATS adapters first. Don't pretend either option fixes them.
5. **Option A without the stager fix is dead on arrival.** `bullet_rewriter --render` will crash on missing `applications/queued/<slug>/JD.md`.

---

## Concrete first-step todo list

1. **Rewrite `applications/_stage_greenhouse.py`** to read `tracker.db` instead of `tracker.md`. Filter: `source_key LIKE 'greenhouse:%' OR jd_url LIKE '%greenhouse%'`, status IN (NULL,'',queued), applied_by=''. Skip slugs whose folder already has `JD.md`. Output: `<slug>/JD.md`, `meta.json`, `prefill.json`, `STATUS.md`. ~1 hour of work.
2. **Spawn a one-shot bulk subagent** that:
   - Runs the rewritten stager (creates ~25–30 missing Greenhouse packets).
   - Then walks Greenhouse open rows and runs `bullet_rewriter.py --org <slug> --job-id <jid> --render` for each missing `_v2.pdf`, with N=3 concurrency.
   - Writes `output/bulk-render-{stamp}.log` (per-role status, page_fill, retries).
   - Idempotent — safe to re-run.
   - **Estimate: 25–35 min wall-clock for ~42 renders.**
3. **After B lands clean**, append two steps to `weekly_run.sh`:
   - Step 6: stager (Greenhouse-only, idempotent).
   - Step 7: render-missing loop (serial inside cron is fine for 5–15 weekly deltas; ~10 min).
   - Wrap each in `|| true` + per-failure log so a flaky render never aborts the weekly job.
4. **Defer non-Greenhouse tailoring** until ATS adapters exist for JD fetch. Track this as a separate gap; don't try to solve it inside this plan.

Done.
