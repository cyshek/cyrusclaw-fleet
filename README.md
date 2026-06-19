# cyrusclaw-fleet

**OpenClaw agent fleet monorepo** — a collection of AI agents running on [OpenClaw](https://openclaw.io) that help with job searching, trading research, travel planning, interview prep, and more.

---

## 🔍 Just Want the Job Search Agent?

You don't need the whole fleet. The job search automation pipeline is fully standalone:

```bash
git clone https://github.com/cyshek/cyrusclaw-fleet
cd cyrusclaw-fleet/agents/job-search
```

Then follow **[agents/job-search/README.md](agents/job-search/README.md)** — it covers everything: setup, personal info config, Gmail integration, running the pipeline, and known ATS limitations.

Covers Ashby, Greenhouse, Lever, Workday, ADP, BambooHR, Rippling, iCIMS, Eightfold, and more.

---

## What Is This?

This repo is the source of truth for a personal fleet of OpenClaw agents. Each agent lives in its own directory under `/agents/` and has its own workspace, memory files, and scripts. They coordinate through the OpenClaw gateway running on a cloud VM.

### Agents

| Agent | Purpose |
|-------|---------|
| `main` | Primary assistant — orchestrates others, handles day-to-day tasks |
| `job-search` | Monitors job boards, tracks applications, auto-tailors resumes |
| `trading-bench` | Research and backtesting assistant for trading strategies |
| `making-money` | Side-income tracking and opportunity research |
| `interview-prep` | Scans calendar + email for upcoming interviews, runs prep sessions |
| `travel` | Travel planning, bookings research, itinerary management |
| `resume-tailor` | Auto-tailors resumes/cover letters to specific job descriptions |

---

## Getting Started (Fork & Deploy)

### 1. Fork this repo

```bash
git clone https://github.com/<your-username>/cyrusclaw-fleet.git
cd cyrusclaw-fleet
```

### 2. Set up your environment

Copy the env example and fill in your secrets:

```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Set up `personal-info.json`

Create a `personal-info.json` file at the repo root (it's gitignored). This is used by agents to personalize outreach, tailor resumes, and fill out job applications. Example shape:

```json
{
  "name": "Your Name",
  "email": "you@example.com",
  "phone": "+1-555-000-0000",
  "location": "City, State",
  "linkedin": "https://linkedin.com/in/yourprofile",
  "github": "https://github.com/yourusername",
  "summary": "One-paragraph bio for cover letters",
  "skills": ["Python", "TypeScript", "..."],
  "target_roles": ["Software Engineer", "..."],
  "target_locations": ["Remote", "San Francisco, CA"]
}
```

### 4. Configure OpenClaw

Install [OpenClaw](https://openclaw.io) on your VM, point it at this repo as the workspace, and configure each agent's channel bindings in `openclaw.json`.

### 5. Configure Git on your VM

```bash
git config --global user.name "openclaw-fleet"
git config --global user.email "openclaw@yourhost"
git remote set-url origin https://<GITHUB_TOKEN>@github.com/<your-username>/cyrusclaw-fleet.git
```

---

## Directory Structure

```
/agents/          — one subdir per agent (workspace, memory, scripts)
/bin/             — shared utility scripts
/docs/            — architecture notes, runbooks, how-tos
.env.example      — environment variable template
.gitignore        — excludes secrets, DBs, daily memory logs
README.md         — this file
```

---

## Security Notes

- **Never commit `.env`** — it's in `.gitignore` for a reason
- **Never commit `personal-info.json`** — same
- Daily memory logs (`memory/20*.md`) are gitignored — they may contain sensitive task context
- Resume PDFs and DOCX files are gitignored
- Auth/session state files are gitignored

---

## Contributing

This is a personal fleet. PRs welcome if you've forked it and want to share improvements to the agent scaffolding or shared scripts.

---

*Built on [OpenClaw](https://openclaw.io)*
