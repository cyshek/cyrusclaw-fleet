# job-search — Automated Job Application Pipeline

An agent-powered job application automation system that discovers open roles, scores them against your profile, and submits applications across multiple ATS platforms (Ashby, Greenhouse, Lever, Workday, ADP, and more).

## What It Does

- **Role discovery**: Scrapes job boards (LinkedIn, Himalayas, Jobright) and direct company career pages
- **LLM classification**: Scores each role against your profile using Claude/GPT — filters for seniority, YOE match, location, etc.
- **Auto-fill & submit**: Fills application forms end-to-end using Playwright — handles multi-step forms, uploads resumes, generates cover letters
- **Tracker DB**: SQLite database tracks every role: status, application date, ATS type, block reasons
- **LinkedIn resolver**: Resolves LinkedIn job postings to their actual ATS URLs for direct submission
- **CAPTCHA handling**: Integrates CapSolver for hCaptcha/reCAPTCHA (optional)
- **Gmail integration**: Parses confirmation emails to verify successful submissions

## Folder Structure

```
job-search/
├── role-discovery/          # Core pipeline: ATS runners, scrapers, utilities
│   ├── core.py              # Shared types (Role, RoleDB) and helpers
│   ├── jd_llm_classifier.py # LLM-based role scoring
│   ├── greenhouse_filler.py # Greenhouse ATS auto-fill runner
│   ├── ashby_filler.py      # Ashby ATS auto-fill runner  
│   ├── lever_filler.py      # Lever ATS auto-fill runner
│   ├── _workday_runner.py   # Workday ATS runner
│   ├── linkedin_authed_resolver.py  # LinkedIn → ATS URL resolver
│   ├── companies.yaml       # Company list with ATS metadata
│   ├── weekly_run.sh        # Main weekly grind script
│   └── ...                  # 400+ other runners and utilities
├── personal-info.template.json  # Template — copy to personal-info.json
├── requirements.txt         # Python dependencies
├── build_combined.py        # Combine/build artifacts
└── probe_*.py               # Ad-hoc diagnostic scripts
```

## Standalone Setup (Fork Just This Folder)

### Prerequisites
- Python 3.11+
- pip
- Playwright (for browser automation)
- (Optional) CapSolver API key for CAPTCHA solving

### Step 1: Clone and enter the folder
```bash
git clone https://github.com/cyshek/cyrusclaw-fleet
cd cyrusclaw-fleet/agents/job-search
```

### Step 2: Create a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Step 3: Configure personal-info.json
```bash
cp personal-info.template.json personal-info.json
```

Edit `personal-info.json` with your actual details:
- `identity`: your name, email, phone, LinkedIn/GitHub URLs
- `address`: your current address
- `work_experience`: your job history (array of objects)
- `education`: your degrees
- `preferences`: target roles, salary range, work type
- `files.resume_pdf`: path to your resume PDF

### Step 4: Set up Gmail app password (for OTP/confirmation parsing)
```bash
# Create a .gmail-app-password file (NOT committed to git)
echo "your-gmail-app-password" > .gmail-app-password
```

Get a Gmail App Password at: https://myaccount.google.com/apppasswords

### Step 5: Set up .env
```bash
cp ../../.env.example .env
# Edit .env and fill in:
# ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...
# CAPSOLVER_API_KEY=...   (optional, for CAPTCHA)
```

### Step 6: Initialize the tracker database
```bash
cd role-discovery
python3 core.py  # Creates tracker.db
```

## How to Run

### Classify and discover new roles
```bash
cd role-discovery
python3 jd_llm_classifier.py
```

### Run a full weekly sweep
```bash
cd role-discovery
bash weekly_run.sh
```

### Submit to Ashby companies in batch
```bash
cd role-discovery
python3 _ashbydrain_driver.py
```

### Check your tracker status
```bash
cd role-discovery
python3 ../probe_state.py
```

### Resolve LinkedIn job URLs to ATS
```bash
cd role-discovery
python3 linkedin_authed_resolver.py
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | For Claude-powered cover letter generation and classification |
| `OPENAI_API_KEY` | Optional | Alternate LLM provider |
| `CAPSOLVER_API_KEY` | Optional | CAPTCHA solving service |
| `DISCORD_WEBHOOK_URL` | Optional | Notifications on submissions |

## Notes

- `tracker.db` is your live database — **do not commit it** (gitignored)
- `personal-info.json` contains your PII — **do not commit it** (gitignored)  
- `.gmail-app-password` — **do not commit it** (gitignored)
- The `applications/` folder contains downloaded JDs and packets — large, gitignored
- Playwright browser data is stored in `.workday-browser-data/` — gitignored
