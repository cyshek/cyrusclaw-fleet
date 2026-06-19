# STATUS: Eightfold / Filestack Resume-Upload Diagnosis

**Started:** 2026-06-12  
**Phase:** COMPLETE — FULL PROBE RESULTS  
**Test target:** Netflix id=2880 (HR Program Manager, Partnerships and Ads)  
URL: https://explore.jobs.netflix.net/careers/job/790316069889

---

## Context gathered (pre-probe)

- Eightfold discovery adapter (`adapters/eightfold.py`) already exists — no runner.
- 12 rows blocked: 11 Netflix + 1 Starbucks (2044) all `block_reason=need-runner-eightfold-RESUMEWALL`
- Prior diagnosis (memory/2026-06-02.md): "Filestack/react-dropzone rejects set_input_files+file_chooser+synthetic-drop"
- FILESTACK-DESIGN.md reveals the Lyft/Hume "Filestack" was actually a **GH S3 upload** — NOT Filestack.
  → Eightfold's mechanism probed fresh below.

---

## NETWORK PROBE FINDINGS (2026-06-12)

### Upload Endpoint — NOT Filestack, NOT S3

**Eightfold uses its own REST API for resume upload.**

```
POST /api/application/v2/resume_upload?domain=netflix.com&user_mode=logged_out_candidate
Host: explore.jobs.netflix.net
X-CSRF-Token: <token from meta[name=_csrf]>
Content-Type: multipart/form-data
body: FormData { resume: <file blob, application/pdf> }
```

### Auth Requirements
- **X-CSRF-Token**: Scraped from `document.querySelector('meta[name=_csrf]').content`
  - Example: `IjkyNDZlNzFlNDIzNzU3MWZkNWJhNjEwMDE5YTE1NGQ5NTg5OTYzZDMi.HQ3jtQ.tEWlYisrSreJC86Yt-HTuWWstus`
  - Flask-WTF style ITSDANGEROUS token — changes per page load
  - Sent as header, NOT query parameter
- **Cookies**: Standard session cookies (obtained by simply visiting the page, no login required)
  - The endpoint uses `user_mode=logged_out_candidate` — no account needed
- **No Filestack API key / policy / signature** — none at all
- **No AWS S3 presigned URL** — none
- **No external auth** — purely internal Eightfold API

### Successful Response (HTTP 200)

```json
{
  "status": 200,
  "error": {"message": "", "body": ""},
  "data": {
    "profile": {
      "encId": "L6zNkJ9Zv",
      "resumeFilename": "test.pdf",
      "resumeUrl": "/profile/L6zNkJ9Zv?export=applied/netflix.com/f26570546547cfd014a47c0f4e32e59c48c0f7c9b3671e4b84c6b277-790834066603.pdf",
      "hasResume": true,
      "resumeUrlsTs": [{...}]
    },
    "filename": "test_probe.pdf"
  }
}
```

**Key response field**: `data.profile.encId` (= `enc_id` in Redux store) — this is the profile identifier that must be present for submit.

### JS State After Upload
- `window.EF_REDUX_STORE.getState().profile.enc_id` becomes the encId from upload response
- `window.EF_REDUX_STORE.getState().isResumeUploaded` → `true`
- Prior upload from this session: `enc_id = "pbO14J5yl"`, filename `Cyrus_Shekari_Resume.pdf`

### Submit Endpoint
```
POST /api/application/v2/submit?domain=netflix.com&hl=en
X-CSRF-Token: <same token>
body: FormData
```
- Mandatory fields: `enc_id`, `firstname`, `lastname`, `phone`, `email`, `location`
- reCAPTCHA v3 token also included in submit body
- Returns 400 if enc_id missing/invalid or fields incomplete
- Returns 429 on rate-limiting (seen during probe)

### No Filestack Anywhere
- Zero Filestack CDN scripts loaded
- Zero Filestack API calls in network
- Confirmed: pure Eightfold proprietary API

---

## GO/NO-GO VERDICT: **GO ✅**

### Why GO
1. **Upload is a simple POST with FormData** — no Filestack, no S3 presigned URL, no external auth required
2. **CSRF token is on the page** in `<meta name="_csrf">` — easily scraped
3. **No login required** — `user_mode=logged_out_candidate` works as guest
4. **LIVE PROOF**: During probe, successfully POSTed a test PDF and received HTTP 200 with `encId: "L6zNkJ9Zv"` — upload confirmed working
5. **Automation path**: Navigate to apply URL → scrape CSRF from meta tag → POST FormData with resume file → get `encId` from response → fill contact fields → submit

### Automation Recipe
```python
# Step 1: Get CSRF token
page.goto(f"https://explore.jobs.netflix.net/careers/apply?pid={job_pid}")
csrf = await page.evaluate("document.querySelector('meta[name=_csrf]').content")

# Step 2: Upload resume via fetch (inside page context or via requests with session cookies)
# Option A: In-browser fetch (avoids CORS):
enc_id = await page.evaluate("""async (args) => {
    const [csrf, pdfBase64] = args;
    const binaryStr = atob(pdfBase64);
    const bytes = new Uint8Array(binaryStr.length);
    for(let i = 0; i < binaryStr.length; i++) bytes[i] = binaryStr.charCodeAt(i);
    const blob = new Blob([bytes], {type: 'application/pdf'});
    const form = new FormData();
    form.append('resume', blob, 'Cyrus_Shekari_Resume.pdf');
    const resp = await fetch('/api/application/v2/resume_upload?domain=DOMAIN&user_mode=logged_out_candidate',
        {method: 'POST', headers: {'X-CSRF-Token': csrf}, body: form, credentials: 'include'});
    const data = await resp.json();
    return data.data.profile.encId;
}""", [csrf, pdf_base64])

# Step 3: Fill form fields and submit
# Fill: email, firstname, lastname, phone, location
# POST to /api/application/v2/submit?domain=DOMAIN&hl=en
```

### Domain Parameter
- Netflix: `domain=netflix.com`
- Starbucks: `domain=starbucks.com` (to verify)
- Derived from the careers subdomain hostname

---

## Remaining Questions (Minor)
1. Submit body shape (all FormData fields for the full submit) — need one more probe
2. reCAPTCHA handling — submit returns 400 without valid token; need to determine if v3 is enforce-checked server-side or just logged
3. Starbucks domain parameter confirmation

---

## NEXT STEPS
- Build `_eightfold_runner.py` using in-browser fetch approach
- Resume upload: use base64-encode PDF → Blob → FormData POST in page.evaluate
- Test submit flow with real enc_id from upload response
- Handle 12 blocked rows (11 Netflix + 1 Starbucks)
