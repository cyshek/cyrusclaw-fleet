# STATUS: SUBMITTED

- **role_id:** 1943
- **company:** Cursor
- **role:** Marketing Program Manager, Workshops
- **url:** https://cursor.com/careers/marketing-program-manager
- **submitted_by:** auto (_ashby_runner.py)
- **submitted_on:** 2026-06-30
- **confirmation:** `{"success":true,"data":{"success":true,"results":{"submittedFormInstance":{"id":"ad0ed344-ff47-4ac1-bbf5-ff4a5962792e",...}}}}`
- **confirmation_url:** cursor.com/api/careers/jobs/064db0d3-3085-4fa4-8ba6-9c111a2bd329/apply
- **resume_attached:** yes (Cyrus_Shekari_Resume_ashby-cursor_064db0d3_v2.pdf)

## Fixes applied
- chain_046: Cursor uses /api/careers/jobs/<uuid>/apply wrapper (not Ashby GraphQL directly)
- radio_sronly_bool: sr-only radio inputs (value="true/false") now matched by boolMap in ashby_filler.py
- scan_form_submit_success: extended to detect {"success":true} response from Cursor API wrapper
