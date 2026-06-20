STATUS: SUBMITTED (verified)
Verified: 2026-06-02 by workday-proof subagent

role_id: 1456
ats: workday (tenant: nordstrom)
company: Nordstrom
role: Product Manager 2 - Payments Experience (Hybrid - Seattle)
req: R-834234

=====================================================================
VERIFICATION (server-authoritative):

Signed into Cyrus's Nordstrom Workday account (cyshekari@gmail.com) and:
1. The apply page for R-834234 returns: "You've already applied for this job."
2. Candidate Home > My Applications lists:
     Product Manager 2 - Payments Experience (Hybrid - Seattle)
     Job Req: R-834234
     My Application Status: No Longer Under Consideration
     Date Submitted: May 2, 2026

So this application was SUBMITTED on 2026-05-02 (prior session). The tracker
DB previously had status='blocked' (stale) and has been corrected to
status='applied', applied_on='2026-05-02'.

Screenshots: ../.workday-debug/nordstrom-force-signin.png (already-applied msg),
             ../.workday-debug/nordstrom-myapps-insession.png (My Applications list)

NOTE: The Nordstrom account also has 2 other submitted apps:
  R-797696 (Product Manager 2, Digital Assets Mgmt) - submitted Dec 30 2025
  R-804864 (Product Manager 2, iOS) - submitted Dec 16 2025
All three show "No Longer Under Consideration".
=====================================================================
