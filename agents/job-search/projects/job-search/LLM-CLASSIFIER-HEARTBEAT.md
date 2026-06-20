# LLM JD Classifier — subagent heartbeat

- 2026-05-24 11:35 PDT: subagent started.
- 2026-05-24 11:37 PDT: validated openclaw CLI Haiku 4.5 works; built migration + classifier.
- 2026-05-24 11:43 PDT: migration applied (6 new cols, backed up to .bak.20260524-llm-classifier). Smoke-tested 4 ATSes (greenhouse/ashby/lever/workday + apple + linkedin) — all succeed end-to-end. Output sensible.
- 2026-05-24 11:50 PDT: weekly_run.sh wired (Step 3b: LLM JD classifier between merge and xlsx render).
- 2026-05-24 11:54 PDT: backfill started (pid 105228). 14/369 done in 1:47. ETA ~45 min. 5 already flipped llm-overreach.
- Cost note: using `github-copilot/claude-haiku-4-5` via openclaw CLI (no Anthropic API key on disk). This is Copilot-backed so no per-call $$; cost ceiling treated as call-count ceiling (--limit guards).
