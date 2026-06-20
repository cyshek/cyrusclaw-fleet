# Overnight work queue — Cyrus AFK 2026-05-19 20:14 → ~2026-05-20 20:14 UTC

Standing autonomy order applies. Work the queue top-down. If blocked, document in memory/2026-05-19.md (or 05-20), skip, continue. No Cyrus pings unless something genuinely catastrophic (account locked, payment requested, etc.).

## Queue

- [ ] **#1 Greenhouse v2 hardening** (Formik refactor + multi_value_multi_select + email verify + smoke probe). Validate with ≥1 real Stripe submit before declaring done.
- [ ] **#2 HPE Workday tenant** validation (1 real submit)
- [ ] **#3 IMC eu.greenhouse subdomain fix** + retry IMC role 697
- [ ] **#4 Jane Street graduation-date label rules** + retry role 702
- [ ] **#5 SpaceX employment-history + citizenship handlers** + retry role 872
- [ ] **#6 Vercel React/Next essay** (LLM cover gen) + retry role 910
- [ ] **#7 Stripe full batch submit** (drain remaining GH iframe roles)
- [ ] **#8 CapSolver wiring** for Ashby (24) + Lever (4) — write up cost + setup plan, ask Cyrus before paying anything
- [ ] **#9 The Trade Desk** role 1229 — fresh probe
- [ ] **#10 Smartsheet** role 867 — should be unblocked by #1
- [ ] Daily summary message to Discord at the end of the run

## Rules

- Browser-driving subagents serial only
- Quality gate: 1-page PDF, no AI-disclosure, work auth US citizen / no sponsorship
- ONE retry per failure, then skip + log
- Append findings to memory/YYYY-MM-DD.md
- Render xlsx after every successful submit
- Do not ask Cyrus for per-role approval
- Do not pay for anything without Cyrus's signoff
