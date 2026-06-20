# STATUS — lyft-8514382002

**SUBMITTED** 2026-05-24 (PT) via v2-burndown auto-submit (subagent).

- Role: Lyft — Product Manager, Premium Modes (role-id 717, est_tc $343K)
- Apply URL (canonical wrapper): https://app.careerpuck.com/job-board/lyft/job/8514382002?gh_jid=8514382002
- Submit path used: https://job-boards.greenhouse.io/embed/job_app?for=lyft&token=8514382002
- Confirmation URL: https://job-boards.greenhouse.io/embed/job_app/confirmation?for=lyft&token=8514382002 (Title: "Thank you for applying")
- Resume: Cyrus_Shekari_Resume_lyft_8514382002_v2.pdf (1 page)
- Cover answers: cover_answers.md (only optional accommodation field, gracefully blank)

## How the careerpuck wrapper was bypassed

MEMORY note from earlier today (sibling 716) claimed careerpuck was a custom SPA needing a separate adapter. That was based on navigating to `app.careerpuck.com/...` and looking for an iframe. The real story: **the underlying Greenhouse `embed/job_app` endpoint (`https://job-boards.greenhouse.io/embed/job_app?for=lyft&token=<gh_jid>`) returns the full real GH application form for Lyft and accepts submissions normally** — no careerpuck adapter needed. The `inline_submit.py` pipeline already constructs that URL via the greenhouse_iframe shim, so the existing runner path works once dryrun blockers are cleared.

## Pipeline fixes shipped in `role-discovery/greenhouse_dryrun.py` during this run

1. **`r_willing_to_relocate` resolver**: was hardcoded to return "Yes". Lyft (and likely other tenants) ship the question as a multi_value_single_select with options like `"I am willing to relocate before starting employment."` Now matches by content ("willing to relocate" minus negation) before falling back to plain Yes.

2. **`r_work_authorized` resolver**: was hardcoded to return "Yes"/"No". Lyft ships options like `"I am authorized to work for any employer in the country in which this position is based."` Now matches by content ("authorized to work for any employer") for the affirmative case.

3. **`LABEL_RULES`**: added `("may we contact your current employer", "answer_no")` BEFORE the generic `("current employer", "current_employer")` rule. Lyft's "May we contact your current employer?" is a Yes/No, not a free-text employer name field. Cyrus answers No (don't tip off Microsoft).

4. **`("commutable proximity", ...)` rule** re-routed from `answer_yes` to `willing_to_relocate` so the new resolver can pick the proper option.

These are all permanent pipeline improvements — they'll help any future Lyft / similar GH tenant role.

## Browser-flow quirks (left as in-band tactics — could be promoted to filler if pattern repeats)

- **Lyft employment widget**: `company-name-0`, `title-0`, `start-date-month-0`, `start-date-year-0`, `end-date-month-0`, `end-date-year-0`, `current-role-0_1` are NOT in the dryrun (boards API doesn't expose them). Filled in-band with Microsoft / Technical Program Manager / March 2024 → May 2026 + Current=true. Lyft's widget does NOT auto-hide end-date when Current=true; both are required.
- **Pronouns dropdown** (`question_36217897002[]`): no decline option, but not required (legend lacks `*`). Left blank.
- **Email verification gate**: after first Submit click, Lyft (Greenhouse-managed) shows 8 `security-input-N` boxes and emails an 8-char code (subject "Security code for your application to Lyft", from `no-reply@us.greenhouse-mail.io`). `role-discovery/fetch_company_code.py "Lyft" <since_epoch>` returned the code in seconds. Filled, clicked Submit again → confirmation page.

## Recommend follow-up for the pipeline (not done in this run)

- The Lyft employment widget + email-verify gate are predictable patterns. Worth adding to `greenhouse_filler.emit_steps` as an iframe-mode addition (auto-fill from `experience_summary.current_*`, run `fetch_company_code` after first Submit, fill `security-input-*`, click Submit again). That would make Lyft fully hands-off in the weekly run.
- The same 8-digit verify gate may be on other Greenhouse tenants that have heightened anti-bot — codify the post-submit verify-loop step regardless of tenant.
