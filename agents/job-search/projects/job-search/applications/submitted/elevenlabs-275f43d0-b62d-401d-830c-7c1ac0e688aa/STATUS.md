# 938 ElevenLabs — Enterprise Solutions Engineer, North America

OUTCOME: ALREADY-APPLIED (server-confirmed duplicate within 90 days)
Date: 2026-06-11
submitted_by: auto-residential (already-applied detection)
resume_attached: yes (Cyrus_Shekari_Resume_ashby-elevenlabs_275f43d0_v2.pdf prepped + uploaded)

## Evidence
Ran `_ashby_runner.py` through residential egress (Webshare 82.23.97.223, verified
NOT Azure). chain_p14 location fix loaded; form reached submit. Server returned:

  "We couldn't submit your application. I'm sorry we are limiting applications to
   give everyone a chance. As you have applied for this position in the last 90
   days, you cannot submit an application for this position."

This is a server-side DUPLICATE-APPLICATION block (Ashby ApplicationBlockingRules),
NOT a Missing-Location bounce and NOT RECAPTCHA_SCORE_BELOW_THRESHOLD. The form
SUBMITTED successfully on a prior application within the last 90 days — so the
prior submit was real. (The runner's classify:"submitted"/FormSubmitSuccess-string
count=2 are the JS marker constants, not a fresh success POST; the decisive proof
is the 90-day server message.)

## chain_p14 verdict for this row
Location fix did NOT cause a bounce here — we got PAST location all the way to the
server-side dedup gate. So chain_p14 is not falsified by 938; 938 was simply already
applied. Real live test of the location ladder = rows 1112/1235.

Log: /tmp/ashby-938.log
