# FILESTACK-DESIGN.md — Greenhouse resume-upload sidecar

**Status:** Phase 1 design (Phase 1.5 diagnostic skipped — needed evidence was obtainable via static HTML + curl of the public JS bundle + presigned endpoint).

## TL;DR — the original "Filestack" hypothesis was WRONG

The chain_007 STATUS.md hypothesis was: "Lyft uses Filestack; we need to intercept Filestack's XHR response to capture a token". After reverse-engineering the Greenhouse embed JS bundle (`https://job-boards.cdn.greenhouse.io/assets/entry.client-BpcnGcgS.js`, 158 KB) and the Lyft form HTML, **there is no Filestack involvement**. The actual upload flow is:

1. **Page load:** React calls
   `GET ${window.ENV.JBEN_URL}/uncacheable_attributes/presigned_fields?fields[]=resume`
   → `JBEN_URL = "https://boards.greenhouse.io"`. Response is a standard
   AWS S3 presigned-POST envelope.

   **Live response sample (curl-verified 2026-05-27, Lyft form irrelevant — endpoint is global):**
   ```json
   {
     "url": "https://grnhse-prod-jben-us-east-1.s3.amazonaws.com",
     "resume": {
       "fields": {
         "x-amz-server-side-encryption": "AES256",
         "success_action_status": "201",
         "policy": "eyJleH...",          // base64 JSON policy w/ 30-day expiration
         "x-amz-credential": "AKIA.../20260527/us-east-1/s3/aws4_request",
         "x-amz-algorithm": "AWS4-HMAC-SHA256",
         "x-amz-date": "20260527T003109Z",
         "x-amz-signature": "7e30..."
       },
       "key": "stash/applications/resumes/{timestamp}-{unique_id}-ebe785c78337d70d9813443a95c79a1f"
     }
   }
   ```

2. **User picks file** → React's UploadField calls `uploader.uploadFile(file, onProgress)`:
   - Substitutes `{timestamp}` → `Date.now()`, `{unique_id}` → random 14-char hex in the `key`.
   - Builds multipart FormData:
     - `utf8` = `✓`
     - all `formFields` (policy, credential, signature, etc.)
     - `key` (substituted)
     - `authenticity_token` = `1234`
     - `Content-Type` = `application/octet-stream`
     - `file` = the binary blob
   - `POST {url}` with body=FormData (no `Content-Type` header — let browser
     set multipart boundary). S3 returns **201 Created**.
   - On success the React component sets state:
     `resume = { url: `${baseUrl}/${substituted_key}`, name: filename }`.

3. **On submit:** `Ua({application, submitPath, ...})` is called. The mapper
   `fa(application)` does:
   ```js
   t.resume_url = application.resume.url;
   t.resume_url_filename = application.resume.name;
   ```
   Then `fetch(submitPath, {method:"POST", body: JSON.stringify({job_application: t, fingerprint, ...})})`.

## Why chain_005/007's "set #resume.files via DataTransfer" never worked

The runner injects a `File` object into `#resume.files` and either does or doesn't dispatch `change`. **Neither path triggers the S3 upload.**

- Without `change`: React's UploadField's onChange handler never fires →
  `uploader.uploadFile()` never called → no S3 PUT → no `resume.url` in
  state → submit sends `{resume_url: undefined}` → server rejects with
  "Resume/CV is required" (because GH only validates `resume_url`/`resume_text`,
  never reads multipart `file` from the JSON submit body — submit IS JSON,
  not multipart).
- With `change`: the change event DOES fire React's handler. But: the
  Playwright-injected `File` may not pass React's typeof checks (the
  `File` class in the page context vs the one DataTransfer made may differ
  across realms in some cases). Even if it does, the upload then takes
  several seconds — and the chain_007 author observed `#resume` getting
  "swapped" (which is actually just React re-rendering the upload widget
  to show a progress chip) and decided to skip dispatching change. This
  was a wrong attribution.

There's no Filestack swap. The runner just never initiates the upload.

## The fix — replicate the upload, then patch fetch

We have two viable strategies. We're going with **Strategy A** (FETCH PATCH)
because it is robust against React-internal changes.

### Strategy A — pre-fetch presigned + S3-upload + fetch interception (CHOSEN)

Inside the iframe, after our existing `_resume_bound()` check **but before
Submit**, we:

1. **Fetch presigned fields ourselves** using JBEN_URL from `window.ENV`.
2. **Generate the final S3 key** by substituting `{timestamp}` (Date.now())
   and `{unique_id}` (random 14-char base36).
3. **POST the file to S3** with the FormData envelope. Read 201.
4. **Compute `resume_url`** = `${base_url}/${substituted_key}` and `resume_url_filename` = file basename.
5. **Patch `window.fetch`** to look for any subsequent `POST` to a path
   matching `/.*\/applications/` or to the known `submitPath` (whichever
   matches first) with `Content-Type: application/json`. When matched,
   parse `init.body`, mutate `job_application.resume_url` and
   `job_application.resume_url_filename`, re-serialize, pass through.

This makes the submit consistent regardless of whether React knows about
the file. The mapper that normally builds these fields is bypassed; we
inject them directly into the request body.

### Strategy B (REJECTED) — trigger React onChange properly

Would require us to find the right `File` constructor (page realm),
fire `change`, and AWAIT React's internal upload promise (no obvious
observability hook). More fragile across GH JS bundle revisions. Keep
in our back pocket if A turns out to have a quirk we can't get around.

## Response-interceptor (the brief's explicit ask)

The brief asked for `page.on("response")` interception. **We don't need
it for the upload itself** (we generate the URL ourselves from the key
substitution; S3 PUT response body is empty XML). But we'll still add
`page.on("response")` for **observability**: capture and log
`uncacheable_attributes/presigned_fields` response + the S3 201
response. This data goes into the report under
`report['gh_s3_upload']` so future workers see what happened.

## Target inputs / payload field reference

- **Server-side required field name (JSON body):** `job_application.resume_url`
- **Companion field:** `job_application.resume_url_filename`
- **Path in body:** top-level key is `job_application`. Other fields
  (`first_name`, `last_name`, `answers_attributes`, `employments`,
  `educations`, `attachments`, `data_compliance`, etc.) coexist; we ONLY
  add/overwrite `resume_url` and `resume_url_filename`.
- **NO hidden DOM input** exists or needs to be filled. Form submission
  is `fetch(POST, JSON)`, not classical form POST.

## Timeout + fallback behavior

- Presigned fetch: 8s timeout. On failure → log + BLOCKED with
  `gh_s3_upload.presigned_fetch_failed: <err>`.
- S3 PUT: 30s timeout (generous for large PDFs). On non-201 → log
  response body + BLOCKED with `gh_s3_upload.s3_put_failed`.
- Fetch-patch installation happens during page setup (right after
  `frame.wait_for_selector("form")`). If the patch hasn't fired by
  the time we observe the submit XHR, we still proceed; honest-verify
  catches field errors normally.

## Kill switch

New constant near top of `greenhouse_iframe_runner.py`:
```python
USE_GH_S3_UPLOADER = True   # set False to fall back to legacy DataTransfer-only path
```

When False: behavior is unchanged from chain_007 (DataTransfer-first,
attempts 0/A/B/C). When True: we additionally install the fetch patch
and pre-upload to S3 before submit.

## Phase 2 implementation outline

Files to modify:

1. **`greenhouse_iframe_runner.py`** —
   - Add `USE_GH_S3_UPLOADER` flag.
   - Add `--debug-filestack` CLI flag (the brief used this name; kept
     for consistency even though no Filestack involvement) → forces
     verbose stderr dump of the upload events.
   - In `run()`, after `frame.wait_for_selector("form", ...)`:
     install `JS_INSTALL_FETCH_PATCH` (defined in greenhouse_filler.py)
     into the frame. The patch sets `window.__gh_resume_inject = null`
     and wraps `window.fetch`.
   - After resume `attempt_0` (and after `_resume_bound()` is True), AND
     `USE_GH_S3_UPLOADER` is True, perform the S3 upload sequence:
     - `evalfn(JS_FETCH_PRESIGNED_FIELDS, {"jbenUrl": "..."})` → fields
     - Python computes substituted key + reads file bytes (already
       loaded for attempt_0). Build base64.
     - `evalfn(JS_S3_UPLOAD, {presigned, b64, filename, mime})` → 201
       response check + final URL string.
     - `evalfn(JS_INSTALL_RESUME_INJECT, {url, filename})` → sets the
       inject payload.
   - Record everything under `report["gh_s3_upload"] = {...}`.

2. **`greenhouse_filler.py`** —
   - Add 3 JS constants:
     - `JS_INSTALL_FETCH_PATCH` (wraps fetch, mutates JSON submit body)
     - `JS_FETCH_PRESIGNED_FIELDS` (calls JBEN endpoint, returns
       `{url, fields, key}`)
     - `JS_S3_UPLOAD` (substitutes key, builds FormData, POSTs file,
       returns `{ok, status, fileUrl}`)
     - `JS_INSTALL_RESUME_INJECT` (sets `window.__gh_resume_inject =
       {resume_url, resume_url_filename}`)

3. **Tests** (`test_greenhouse_s3_uploader.py`) — 6+ cases:
   - Substituted key generation (timestamp+unique_id replacement).
   - Fetch-patch wraps non-JSON requests transparently.
   - Fetch-patch leaves non-application JSON requests untouched.
   - Fetch-patch mutates `job_application.resume_url` when inject set.
   - Fetch-patch leaves request body unchanged when inject is null.
   - Kill-switch off → no S3 upload step is recorded.

## Live verification plan (Phase 3)

- Single run: `.venv/bin/python role-discovery/greenhouse_iframe_runner.py --slug lyft-8550252002 --debug-filestack`
- Expected: `outcome=SUBMITTED`, post_submit `conf=true` (confirmation
  page), `gh_s3_upload.s3_status=201`.
- On success, immediately run Lyft 716 (`lyft-8525086002`).
- Update tracker.db for both with backups
  `tracker.db.bak.20260526-r1343-filestack-sidecar` and
  `-r716-filestack-sidecar`.

## Risk + rollback

If live submit STILL fails with "Resume/CV is required" despite the patch
firing (= fetch wrapper logs show injection BUT server still rejects):
- Likely cause: GH server-side validates against an additional field
  (e.g. `attachments[]` with the actual upload). Mitigation: inspect
  the submit response body for additional field hints. May also need
  to add `attachments: [{ name: resume_url_filename, url: resume_url, type: "resume" }]`.
- Add as Attempt B if needed.

If submit succeeds in our test but yields a CORRUPTED resume in
Greenhouse's downstream pipeline (we can't verify this from the agent):
- Cyrus can spot-check from the Lyft confirmation email + Greenhouse
  recruiter view.
- Worst case rollback: flip `USE_GH_S3_UPLOADER=False`, role goes back
  to BLOCKED (same as today).
