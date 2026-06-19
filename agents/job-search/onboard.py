#!/usr/bin/env python3
"""
onboard.py — Interactive setup wizard for the job-search agent.

Walks you through:
  1. Personal info → personal-info.json
  2. Gmail App Password → .gmail-app-password  +  .env (GMAIL_USER)
  3. IMAP connectivity test

Run from agents/job-search/:
    python onboard.py

No external dependencies — stdlib only.
"""

from __future__ import annotations

import imaplib
import json
import os
import re
import ssl
import sys
from pathlib import Path

HERE = Path(__file__).parent.resolve()
PERSONAL_INFO_FILE = HERE / "personal-info.json"
TEMPLATE_FILE = HERE / "personal-info.template.json"
APP_PW_FILE = HERE / ".gmail-app-password"
ENV_FILE = HERE / ".env"

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

BOLD  = "\033[1m"
GREEN = "\033[32m"
CYAN  = "\033[36m"
YELLOW = "\033[33m"
RESET = "\033[0m"

def banner(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}\n")

def ask(prompt: str, default: str = "", required: bool = True) -> str:
    """Prompt user for input. Returns stripped string (or default on empty)."""
    suffix = f" [{default}]" if default else " (optional, press Enter to skip)" if not required else ""
    while True:
        val = input(f"  {prompt}{suffix}: ").strip()
        if val:
            return val
        if default:
            return default
        if not required:
            return ""
        print("  ⚠️  This field is required.")

def ask_yn(prompt: str, default_yes: bool = False) -> bool:
    suffix = "[Y/n]" if default_yes else "[y/N]"
    while True:
        val = input(f"  {prompt} {suffix}: ").strip().lower()
        if not val:
            return default_yes
        if val in ("y", "yes"):
            return True
        if val in ("n", "no"):
            return False
        print("  Please enter y or n.")

def ask_list(prompt: str, default: list[str] | None = None) -> list[str]:
    """Ask for a comma-separated list; returns list of stripped strings."""
    default_str = ", ".join(default) if default else ""
    raw = ask(prompt, default=default_str, required=False)
    if not raw:
        return default or []
    return [x.strip() for x in raw.split(",") if x.strip()]

def load_env_file(path: Path) -> dict[str, str]:
    """Parse an existing .env file into a dict."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result

def write_env_file(path: Path, data: dict[str, str]) -> None:
    """Merge new keys into an existing .env file (preserves existing entries)."""
    existing = load_env_file(path)
    existing.update(data)
    lines = []
    for k, v in existing.items():
        lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o600)

# ──────────────────────────────────────────────
# IMAP test
# ──────────────────────────────────────────────

def test_imap(gmail_user: str, app_password: str) -> bool:
    """Return True if IMAP login succeeds."""
    try:
        ctx = ssl.create_default_context()
        print(f"\n  🔌 Connecting to imap.gmail.com:993 …", end=" ", flush=True)
        with imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx) as imap:
            imap.login(gmail_user, app_password.replace(" ", ""))
            imap.select("INBOX")
        print(f"{GREEN}✓ connected{RESET}")
        return True
    except imaplib.IMAP4.error as e:
        print(f"\n  {YELLOW}⚠️  IMAP login failed: {e}{RESET}")
        print("  Check that 2FA is on and the app password is correct.")
        print("  You can fix this later — the rest of the config was saved.\n")
        return False
    except OSError as e:
        print(f"\n  {YELLOW}⚠️  Network error: {e}{RESET}")
        return False

# ──────────────────────────────────────────────
# Main wizard
# ──────────────────────────────────────────────

def run_wizard() -> None:
    print(f"""
{BOLD}╔══════════════════════════════════════════════════════════╗
║       job-search agent — interactive setup wizard        ║
╚══════════════════════════════════════════════════════════╝{RESET}

This wizard creates two files in agents/job-search/:
  • {BOLD}personal-info.json{RESET}   — your profile (gitignored, never committed)
  • {BOLD}.gmail-app-password{RESET}  — 16-char Gmail App Password (gitignored)
  • {BOLD}.env{RESET}                 — GMAIL_USER and any other keys (gitignored)

It takes about 3 minutes. Press Ctrl-C at any time to abort.
""")

    # ── Already set up? ──────────────────────────────────────────
    if PERSONAL_INFO_FILE.exists():
        print(f"  {YELLOW}⚠️  personal-info.json already exists.{RESET}")
        if not ask_yn("Re-run setup and overwrite it?", default_yes=False):
            print("\n  Nothing changed. Goodbye! 👋\n")
            sys.exit(0)

    # Load template as the base structure
    template = json.loads(TEMPLATE_FILE.read_text())

    # ── Section 1: Identity ──────────────────────────────────────
    banner("Section 1 / 5 — Your Identity")
    print("  Basic personal details that go on every application.\n")

    first = ask("First name")
    last  = ask("Last name")
    email = ask("Email address")
    phone = ask("Phone number (e.g. +1-555-123-4567)")
    linkedin = ask("LinkedIn URL", required=False)
    github   = ask("GitHub URL", required=False)
    portfolio = ask("Portfolio / personal site URL", required=False)

    template["identity"]["first_name"]    = first
    template["identity"]["last_name"]     = last
    template["identity"]["full_name"]     = f"{first} {last}"
    template["identity"]["email"]         = email
    template["identity"]["phone"]         = phone
    template["identity"]["linkedin_url"]  = linkedin or ""
    template["identity"]["github_url"]    = github or ""
    template["identity"]["portfolio_url"] = portfolio or ""
    template["contact"]["email"]          = email
    template["contact"]["phone"]          = phone

    # ── Section 2: Address ───────────────────────────────────────
    banner("Section 2 / 5 — Address")
    print("  Used on forms that require a mailing address.\n")

    city    = ask("City")
    state   = ask("State (2-letter, e.g. CA)")
    zipcode = ask("ZIP code")
    street  = ask("Street address", required=False)

    template["address"]["city"]   = city
    template["address"]["state"]  = state.upper()
    template["address"]["zip"]    = zipcode
    template["address"]["street"] = street or ""

    # ── Section 3: Work Authorization ────────────────────────────
    banner("Section 3 / 5 — Work Authorization")
    print("  Required for EEO compliance fields on most applications.\n")

    print("  Common values: US Citizen, Green Card, H-1B, OPT, TN, Other")
    auth_status = ask("Work authorization status", default="US Citizen")
    requires_sponsorship = ask_yn("Do you require visa sponsorship?", default_yes=False)

    template["work_authorization"]["status"]              = auth_status
    template["work_authorization"]["requires_sponsorship"] = requires_sponsorship

    # ── Section 4: Job Preferences ───────────────────────────────
    banner("Section 4 / 5 — Job Preferences")
    print("  What kinds of roles the agent should target.\n")

    roles = ask_list(
        "Target job titles (comma-separated)",
        default=["Software Engineer", "Senior Software Engineer"]
    )
    work_types = ask_list(
        "Work types (remote / hybrid / onsite, comma-separated)",
        default=["remote", "hybrid"]
    )
    cities = ask_list(
        "Target cities or 'Remote' (comma-separated)",
        default=["Remote", f"{city}, {state.upper()}"]
    )

    print()
    min_sal_raw  = ask("Minimum salary expectation (number, or press Enter to skip)", required=False)
    pref_sal_raw = ask("Preferred/target salary (number, or press Enter to skip)", required=False)

    template["preferences"]["roles"]     = roles
    template["preferences"]["work_type"] = work_types
    if min_sal_raw:
        try:
            template["preferences"]["min_salary"] = int(min_sal_raw.replace(",", "").replace("$", ""))
        except ValueError:
            pass
    if pref_sal_raw:
        try:
            template["preferences"]["preferred_salary"] = int(pref_sal_raw.replace(",", "").replace("$", ""))
            template["common_form_answers"]["salary_expectation"] = pref_sal_raw.replace(",", "").replace("$", "")
        except ValueError:
            pass

    template["cities_available_to_work"] = cities

    # ── Section 5: Gmail App Password ───────────────────────────
    banner("Section 5 / 5 — Gmail App Password")
    print("  The agent uses IMAP to fetch OTP codes and verify submissions.")
    print("  You need a Gmail App Password (not your regular password).")
    print()
    print("  How to get one:")
    print("    1. Go to https://myaccount.google.com/apppasswords")
    print("    2. Click 'Create app password', name it 'job-search'")
    print("    3. Copy the 16-character password shown (spaces don't matter)")
    print()

    gmail_user  = ask("Gmail address (the one with the App Password)")
    gmail_pw    = ask("Gmail App Password (16 chars)", required=False)

    # ── Write files ──────────────────────────────────────────────
    print()
    print("  💾 Saving personal-info.json …", end=" ", flush=True)
    # Strip all _comment keys before writing
    def strip_comments(obj):
        if isinstance(obj, dict):
            return {k: strip_comments(v) for k, v in obj.items() if k != "_comment"}
        if isinstance(obj, list):
            return [strip_comments(i) for i in obj]
        return obj

    cleaned = strip_comments(template)
    PERSONAL_INFO_FILE.write_text(json.dumps(cleaned, indent=2))
    PERSONAL_INFO_FILE.chmod(0o600)
    print(f"{GREEN}✓{RESET}")

    if gmail_pw:
        print("  💾 Saving .gmail-app-password …", end=" ", flush=True)
        APP_PW_FILE.write_text(gmail_pw.replace(" ", "") + "\n")
        APP_PW_FILE.chmod(0o600)
        print(f"{GREEN}✓{RESET}")

    print("  💾 Updating .env …", end=" ", flush=True)
    env_data: dict[str, str] = {"GMAIL_USER": gmail_user}
    write_env_file(ENV_FILE, env_data)
    print(f"{GREEN}✓{RESET}")

    # ── IMAP connectivity test ───────────────────────────────────
    imap_ok = False
    if gmail_pw:
        imap_ok = test_imap(gmail_user, gmail_pw)
    else:
        print(f"\n  {YELLOW}ℹ️  Skipping IMAP test (no app password provided).{RESET}")

    # ── Success banner ───────────────────────────────────────────
    print(f"""
{GREEN}{BOLD}╔══════════════════════════════════════════════════════════╗
║   ✅  Setup complete!                                     ║
╚══════════════════════════════════════════════════════════╝{RESET}

Files written:
  ✓ agents/job-search/personal-info.json
  {"✓" if gmail_pw else "–"} agents/job-search/.gmail-app-password
  ✓ agents/job-search/.env  (GMAIL_USER={gmail_user})

Next steps:
  1. Add your resume PDF to agents/job-search/resume/resume.pdf
  2. Edit personal-info.json to fill in work_experience + education
     (the wizard skips those for brevity)
  3. Add your LLM API key to agents/job-search/.env:
         ANTHROPIC_API_KEY=sk-ant-...
  4. Install dependencies:
         python3 -m venv .venv && source .venv/bin/activate
         pip install -r requirements.txt
         playwright install chromium
  5. Initialize the tracker DB:
         cd role-discovery && python3 core.py
  6. Run a smoke test:
         python3 probe_state.py

Then kick off a discovery run:
  cd role-discovery && bash weekly_run.sh

Happy job hunting! 🚀
""")

    if not imap_ok and gmail_pw:
        sys.exit(1)

# ──────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────

if __name__ == "__main__":
    try:
        run_wizard()
    except KeyboardInterrupt:
        print("\n\n  Aborted. No files were written (partial writes may exist).\n")
        sys.exit(130)
