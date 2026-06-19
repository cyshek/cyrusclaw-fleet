#!/usr/bin/env bash
# scripts/setup.sh — cyrusclaw-fleet onboarding setup
# Sets up the job-search agent and common dependencies.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOB_SEARCH="$REPO_ROOT/agents/job-search"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   cyrusclaw-fleet setup                  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ── 1. Check Python 3 ──────────────────────────────────────────────────────
echo "→ Checking Python 3..."
if ! command -v python3 &>/dev/null; then
  echo "✗ Python 3 not found. Install it from https://python.org"
  exit 1
fi
PYTHON_VER=$(python3 --version 2>&1)
echo "  ✓ Found $PYTHON_VER"

# ── 2. Check pip ────────────────────────────────────────────────────────────
echo "→ Checking pip..."
if ! python3 -m pip --version &>/dev/null; then
  echo "✗ pip not found. Install it with: python3 -m ensurepip --upgrade"
  exit 1
fi
echo "  ✓ pip available"

# ── 3. Check playwright ─────────────────────────────────────────────────────
echo "→ Checking Playwright..."
if python3 -c "import playwright" 2>/dev/null; then
  echo "  ✓ Playwright already installed"
else
  echo "  ! Playwright not installed — will install via requirements.txt"
fi

# ── 4. Set up .env ──────────────────────────────────────────────────────────
echo "→ Checking .env..."
if [ ! -f "$REPO_ROOT/.env" ]; then
  if [ -f "$REPO_ROOT/.env.example" ]; then
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
    echo "  ✓ Created .env from .env.example"
    echo "  ⚠  IMPORTANT: Edit $REPO_ROOT/.env and fill in your API keys"
  else
    echo "  ! No .env.example found — create $REPO_ROOT/.env manually"
  fi
else
  echo "  ✓ .env already exists"
fi

# ── 5. Set up personal-info.json ────────────────────────────────────────────
echo "→ Checking personal-info.json..."
if [ ! -f "$JOB_SEARCH/personal-info.json" ]; then
  if [ -f "$JOB_SEARCH/personal-info.template.json" ]; then
    cp "$JOB_SEARCH/personal-info.template.json" "$JOB_SEARCH/personal-info.json"
    echo "  ✓ Created personal-info.json from template"
    echo ""
    echo "  ╔══════════════════════════════════════════════════════════════╗"
    echo "  ║  ACTION REQUIRED: Fill in your personal info                ║"
    echo "  ║  Edit: $JOB_SEARCH/personal-info.json"
    echo "  ║  Fields: name, email, phone, address, work history, etc.    ║"
    echo "  ╚══════════════════════════════════════════════════════════════╝"
    echo ""
  else
    echo "  ! No template found at $JOB_SEARCH/personal-info.template.json"
  fi
else
  echo "  ✓ personal-info.json already exists"
fi

# ── 6. Install job-search deps ───────────────────────────────────────────────
echo "→ Installing job-search dependencies..."
if [ -f "$JOB_SEARCH/requirements.txt" ]; then
  # Create venv if not present
  if [ ! -d "$JOB_SEARCH/.venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv "$JOB_SEARCH/.venv"
  fi
  echo "  Installing packages (this may take a minute)..."
  "$JOB_SEARCH/.venv/bin/pip" install -q -r "$JOB_SEARCH/requirements.txt"
  echo "  ✓ Dependencies installed into $JOB_SEARCH/.venv"

  # Install Playwright browsers
  echo "  Installing Playwright browsers..."
  "$JOB_SEARCH/.venv/bin/playwright" install chromium 2>&1 | tail -3
  echo "  ✓ Playwright chromium installed"
else
  echo "  ! No requirements.txt found at $JOB_SEARCH/requirements.txt"
fi

# ── 7. Summary ───────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Setup complete! Next steps:            ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  1. Fill in your personal info:"
echo "     $JOB_SEARCH/personal-info.json"
echo ""
echo "  2. Add API keys to .env:"
echo "     $REPO_ROOT/.env"
echo "     (ANTHROPIC_API_KEY, optional OPENAI_API_KEY, CAPSOLVER_API_KEY)"
echo ""
echo "  3. Add your Gmail app password:"
echo "     echo 'your-app-password' > $JOB_SEARCH/.gmail-app-password"
echo "     Get one at: https://myaccount.google.com/apppasswords"
echo ""
echo "  4. Add your resume PDF:"
echo "     mkdir -p $JOB_SEARCH/resume"
echo "     cp /path/to/your/resume.pdf $JOB_SEARCH/resume/resume.pdf"
echo ""
echo "  5. Run the pipeline:"
echo "     source $JOB_SEARCH/.venv/bin/activate"
echo "     cd $JOB_SEARCH/role-discovery"
echo "     python3 jd_llm_classifier.py"
echo ""
echo "  See agents/job-search/README.md for full documentation."
echo ""
