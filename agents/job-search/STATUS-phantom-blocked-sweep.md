# Phantom-Blocked Sweep — COMPLETE
**Started:** 2026-06-14 11:52 PDT  
**Completed:** 2026-06-14 ~19:15 PDT  
**Commit:** bb5cb9f

## Summary of Changes

### CLOSED (11 rows)
| ID | Company | Role | Reason |
|----|---------|------|--------|
| 794 | OpenAI | Product Manager, ChatGPT and Codex App Ecosystem | Delisted from Ashby board |
| 802 | OpenAI | GTM Onboarding Program Manager | Delisted from Ashby board |
| 803 | OpenAI | Manager, Solutions Engineering | Delisted from Ashby board |
| 806 | OpenAI | Solutions Engineer, Healthcare & Life Sciences | Delisted from Ashby board |
| 809 | OpenAI | Solutions Engineer, Retail | Delisted from Ashby board |
| 810 | OpenAI | Strategy & Operations, Rapid Response Program Manager | Delisted from Ashby board |
| 1145 | OpenAI | Solutions Engineer, Education | Delisted from Ashby board |
| 1219 | OpenAI | Technical Program Manager, Frontier Evals | Delisted from Ashby board |
| 1344 | OpenAI | Technical Product Manager, GTM Systems | Delisted from Ashby board |
| 1345 | OpenAI | Technical Program Manager, Core Network & WAN Infrastructure | Delisted from Ashby board |
| 2747 | FloQast | Solutions Architect, GRC | HTTP 404 - job removed |

### ALREADY-APPLIED (1 row)
| ID | Company | Role | Note |
|----|---------|------|------|
| 2320 | Vendelux | Technical Product Manager- Data | Duplicate of row 2774 (applied by Cyrus 2026-06-04) |

### Block Reason Labels Cleaned
- Deepgram 970/971: `ashby-hard-score-block: RECAPTCHA...` → `ashby-hard-score-block`
- Tavus 891: `ashby-score-gate-warmed-profile-required...` → `ashby-hard-score-block`
- OpenAI 2549: same → `ashby-hard-score-block`  
- need-runner-* rows: verbose → concise labels

## Remaining Blocked (69 rows)
| Block Class | Count | Notes |
|-------------|-------|-------|
| openai-applimit-180d | 23 | Time-gated; ~23 LIVE rows (some may expire before cooldown) |
| lever-hcaptcha-enterprise-wall | 10 | No hCaptcha vendor; CapSolver discontinued support |
| linkedin-stranded | 8 | No direct ATS URL discoverable from VM |
| proxy-ip-walled | 6 | NYC cityjobs (2) + Ashby moderate (4) |
| lever-hcaptcha-score-wall | 4 | Outreach, Palantir x2, Perforce |
| ashby-hard-score-block | 4 | Deepgram x2, Tavus, OpenAI 2549 |
| hcaptcha-need-key | 2 | Samba TV, Veeva |
| need-runner-* | 4 | SuccessFactors/Paylocity/Oracle/Jobvite/Eightfold |
| icims-* | 3 | AMD internal SSO, Joby hCaptcha, RealPage unresolved |
| misc | 5 | gh-embed-bounce (Stripe), req-expired, senior-title, etc |

## No SUBMITTABLE rows found
All blocks are genuinely categorized. No phantom blocks recovered.
