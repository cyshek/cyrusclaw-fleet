SUBMITTED — 2026-06-10 (hourly grind)
role_id: 2623 | company: Swayable | role: Product Manager
ats: greenhouse | confirmation_url: https://job-boards.greenhouse.io/swayable/jobs/4829801007/confirmation
confirmed: true | submitted_by: auto | resume_attached: yes
answers: commute/relocate Yes/No ("within commuting distance to SF or NYC OR comfortable relocating at your own expense") -> Yes (Cyrus US-onsite/relocation never a knockout). Python-for-Data-Science proficiency -> Intermediate.
ENGINE FIX: the commute question contains "New York City" -> generic ("city","city") LABEL_RULE stole it -> resolved home city "Kirkland" (needs-review). Added specific commuting-distance/relocating-to-one-of-these/comfortable-relocating answer_yes rules BEFORE ("city","city"). Now auto-resolves Yes. Was banked SWAYABLE-GEO-KNOCKOUT (misdiagnosis; per onsite rule it's a Yes).
