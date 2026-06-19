# job-search — Automated Job Application Pipeline

> **🚀 Just want the job search agent?**
> You only need this folder. Fork the repo (or download `agents/job-search/`) and follow the [Standalone Setup](#standalone-setup) steps below — no other part of the fleet required.

An AI-powered job application automation system that discovers open roles, scores them against your profile, and submits applications across multiple ATS platforms end-to-end.

---

## What It Does

| Feature | Description |
|---------|-------------|
| **Role discovery** | Scrapes LinkedIn, Himalayas, Jobright, and direct company career pages for open roles |
| **LLM classification** | Scores each role against your profile using Claude/GPT — filters by seniority, YOE match, location, and title fit |
| **Auto-fill & submit** | Fills application forms end-to-end using Playwright — handles multi-step forms, uploads resumes, generates cover letters |
| **ATS coverage** | Ashby, Greenhouse, Lever, Workday, ADP, BambooHR, Rippling, iCIMS, Eightfold, and more |
| **Tracker DB** | SQLite database tracks every role: status, ATS type, submission date, block reasons, and your notes |
| **LinkedIn resolver** | Resolves LinkedIn job postings to their actual ATS URLs for direct headless submission |
| **Gmail integration** | Parses OTP/confirmation emails to clear auth gates and verify successful submissions |
| **CAPTCHA handling** | Optional CapSolver integration for hCaptcha/reCAPTCHA walls |
| **Cover letter gen** | LLM-generated cover letters, output as PDF via ReportLab |

---

## Folder Structure

```
job-search/
├── role-discovery/              # Core pipeline: ATS runners, scrapers, utilities
│   ├── core.py                  # Shared types (Role, RoleDB) and helpers
│   ├── tracker_db.py            # SQLite tracker schema and query helpers
│   ├── jd_llm_classifier.py     # LLM-based role scoring and filtering
│   ├── ashby_filler.py          # Ashby ATS auto-fill runner
│   ├── greenhouse_filler.py     # Greenhouse ATS auto-fill runner
│   ├── lever_filler.py          # Lever ATS auto-fill runner
│   ├── _workday_runner.py       # Workday ATS runner (per-company account mgmt)
│   ├── bamboohr_filler.py       # BambooHR ATS runner
│   ├── rippling_filler.py       # Rippling ATS runner
│   ├── _icims_runner.py         # iCIMS ATS runner
│   ├── _eightfold_runner.py     # Eightfold ATS runner
│   ├── cover_letter_pdf.py      # LLM cover letter → PDF generator
│   ├── linkedin_authed_resolver.py  # LinkedIn → ATS URL resolver
│   ├── gmail_imap.py            # Gmail IMAP helper (OTP, confirmation parsing)
│   ├── companies.yaml           # Company list with ATS metadata
│   ├── weekly_run.sh            # Main weekly grind script
│   └── ...
├── personal-info.template.json  # Template — copy to personal-info.json and fill in
├── requirements.txt             # Python dependencies
├── probe_apply.py               # Smoke test: apply to a single role by ID
├── probe_state.py               # Check tracker DB status
├── build_combined.py            # Build/combine application artifacts
├── archive/                     # One-off debug scripts (safe to ignore)
└── README.md                    # This file
```

---

## Standalone Setup

### Prerequisites

- Python 3.11+
- `pip`
- A Gmail account (for OTP parsing and application confirmations)
- An Anthropic API key (for LLM classification + cover letter generation)

### Step 1: Get the code

```bash
# Clone the full repo and enter the folder:
git clone https://github.com/cyshek/cyrusclaw-fleet
cd cyrusclaw-fleet/agents/job-search

# Or download just this folder:
# svn export https://github.com/cyshek/cyrusclaw-fleet/trunk/agents/job-search
```

### Step 2: Create a virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### Step 3: Configure your personal info (interactive wizard)

The fastest way is the onboarding wizard — it asks you questions and writes everything for you:

```bash
python onboard.py
```

The wizard covers: identity, address, work authorization, job preferences, and Gmail App Password setup. It also runs a quick IMAP connectivity test so you know the credential works before the first run.

If you prefer to configure manually:

```bash
cp personal-info.template.json personal-info.json
```

Edit `personal-info.json` with your actual details. Key fields:

| Section | What to fill in |
|---------|----------------|
| `identity` | Full name, email, phone, LinkedIn/GitHub URLs |
| `address` | Your current mailing address |
| `work_authorization` | Work auth status, sponsorship requirement |
| `work_experience` | Array of past jobs (title, company, dates, bullets) |
| `education` | Degrees and schools |
| `preferences` | Target roles, salary range, remote/hybrid/onsite |
| `files.resume_pdf` | Path to your resume PDF |
| `cover_letter_policy` | `"generate"` (LLM-written) or `"default"` (use `cover_letter_default`) |

> **⚠️ Never commit `personal-info.json`** — it contains your PII. It's gitignored.

### Step 4: Set up environment variables

Create a `.env` file in the `agents/job-search/` folder:

```bash
# LLM keys (at least one required for classification + cover letters)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...           # optional, alternate provider

# Optional: CAPTCHA solving
CAPSOLVER_API_KEY=...

# Optional: Discord notifications on submissions
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### Step 5: Set up Gmail App Password (for OTP and confirmation parsing)

Many ATS platforms send a one-time code to your email. The pipeline can fetch it automatically via IMAP.

1. Enable 2FA on your Gmail account
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords) and generate a password for "Mail"
3. Store it:

```bash
echo "your-16-char-app-password" > .gmail-app-password
chmod 600 .gmail-app-password
```

Then set your Gmail address in `.env`:

```bash
GMAIL_USER=you@gmail.com
```

> The `gmail_imap.py` module reads `GMAIL_USER` from env and `GMAIL_APP_PASSWORD` from the `.gmail-app-password` file.

### Step 6: Initialize the tracker database

```bash
cd role-discovery
python3 core.py   # creates tracker.db in the parent folder
```

### Step 7: Run a smoke test

```bash
# Check tracker state (should show an empty DB):
cd role-discovery
python3 ../probe_state.py

# Apply to a single role by role ID (from your tracker DB):
python3 ../probe_apply.py --id <role_id>
```

---

## How to Run

### Discover and classify new roles

```bash
cd role-discovery
python3 jd_llm_classifier.py
```

### Run a full weekly sweep

```bash
cd role-discovery
bash weekly_run.sh
```

### Batch-submit to Ashby companies

```bash
cd role-discovery
python3 _ashbydrain_driver.py
```

### Check tracker status

```bash
cd role-discovery
python3 ../probe_state.py
```

### Resolve LinkedIn job URLs to their ATS

```bash
cd role-discovery
python3 linkedin_authed_resolver.py
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | Claude for cover letter generation and role classification |
| `OPENAI_API_KEY` | Optional | Alternate LLM provider |
| `GMAIL_USER` | Recommended | Gmail address for OTP/confirmation fetching |
| `CAPSOLVER_API_KEY` | Optional | CAPTCHA solving service ([capsolver.com](https://capsolver.com)) |
| `DISCORD_WEBHOOK_URL` | Optional | Notifications when applications are submitted |

---

## What Not to Commit

| File/Path | Why |
|-----------|-----|
| `personal-info.json` | Contains your PII |
| `.env` | Contains API keys |
| `.gmail-app-password` | Gmail credential |
| `tracker.db` | Your live application database |
| `.workday-browser-data/` | Playwright browser session data |
| `applications/` | Downloaded JDs and application packets |
| `resume/` | Your resume files |

All of the above are already in `.gitignore`.

---

## Known Limitations

- **Workday**: Requires creating a per-company Workday account. The runner manages fresh Gmail aliases to avoid account-reuse blocks, but some tenants still require manual completion.
- **ADP**: Complex multi-step forms with frequent UI changes; the runner handles common flows but may need tuning for specific companies.
- **LinkedIn Easy Apply**: Partial — the resolver identifies ATS URLs from LinkedIn, but Easy Apply itself (fully in-LinkedIn) is only partially automated.
- **CAPTCHA walls**: The CapSolver integration handles most hCaptcha/reCAPTCHA cases, but some ATS platforms (TikTok Careers, some Eightfold tenants) have aggressive bot detection that requires a residential proxy or manual intervention.
- **Auth-walled ATS**: A few niche ATS platforms (e.g. Phenom, some internal portals) require a pre-existing account — the pipeline creates one on first run where possible, but some require manual account creation.
- **Resume tailoring**: Cover letters are LLM-generated per role. Resume tailoring per-role is supported but requires a pre-generated DOCX template.

---

## Contributing

PRs welcome! See [CONTRIBUTING.md](../../CONTRIBUTING.md) for the guide on adding new ATS runners, testing, and submitting changes.

Quick pointer: each ATS runner lives in `role-discovery/` and follows a standard interface — see `ashby_filler.py` or `greenhouse_filler.py` as reference implementations.

---

## License

MIT. Fork freely — just don't commit your personal info. 😄
