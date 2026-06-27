# Delta anomalies — 20260626-1505 UTC

Compared `20260626-1505-roles.json` (current) vs `20260626-0016-roles.json` (previous).
Threshold: any adapter losing >50% of roles week-over-week, baseline >= 5.

| Adapter | Previous | Current | Drop |
| --- | --- | --- | --- |
| microsoft | 19 | 5 | 74% |

Likely causes: adapter shape change, ATS endpoint move, tenant-wide outage, listing churn.
Action: spot-check one company on the affected adapter manually before next crawl.