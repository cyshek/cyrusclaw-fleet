"""
Base harness for ATS-specific apply adapters.

Every adapter inherits from BaseApplier and implements `apply(page, profile)`.
The harness handles:
  - Loading personal-info.json
  - Launching Playwright
  - Dry-run vs live mode
  - Screenshots before/after
  - Run logging to runs/<timestamp>-<company>-<role>.json
"""
from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import sync_playwright, Page, BrowserContext

try:
    from playwright_stealth import Stealth
    _HAS_STEALTH = True
except ImportError:
    _HAS_STEALTH = False

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
RUNS = ROOT / "runs"
PROFILE = ASSETS / "personal-info.json"
RESUME = ASSETS / "Cyrus_Shekari_Resume.pdf"


@dataclass
class FieldFill:
    """One filled form field, captured for the run log."""
    selector: str
    label: str
    value: str
    method: str  # "fill" / "select" / "click" / "upload"
    success: bool = True
    error: Optional[str] = None


@dataclass
class RunResult:
    company: str
    role: str
    url: str
    ats: str
    started_at: str
    finished_at: Optional[str] = None
    mode: str = "dry-run"  # dry-run | live
    submitted: bool = False
    fields: List[FieldFill] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    error: Optional[str] = None


def load_profile() -> Dict[str, Any]:
    return json.loads(PROFILE.read_text(encoding="utf-8"))


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:60] or "x"


class BaseApplier(ABC):
    ATS_NAME = "base"

    def __init__(self, url: str, company: str, role: str,
                 dry_run: bool = True, headless: bool = False):
        self.url = url
        self.company = company
        self.role = role
        self.dry_run = dry_run
        self.headless = headless
        self.prep_mode = False  # if True, fill but don't auto-submit; pause for human
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_id = f"{ts}-{slugify(company)}-{slugify(role)}"
        self.run_dir = RUNS / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.result = RunResult(
            company=company, role=role, url=url, ats=self.ATS_NAME,
            started_at=ts, mode="dry-run" if dry_run else "live",
        )

    def screenshot(self, page: Page, label: str) -> None:
        path = self.run_dir / f"{label}.png"
        try:
            page.screenshot(path=str(path), full_page=True)
            self.result.screenshots.append(str(path))
        except Exception as e:
            self.result.notes.append(f"screenshot-{label}-failed: {e}")

    def note(self, msg: str) -> None:
        print(f"  [note] {msg}")
        self.result.notes.append(msg)

    def record_fill(self, selector: str, label: str, value: str,
                    method: str = "fill", success: bool = True, error: str = None):
        self.result.fields.append(FieldFill(
            selector=selector, label=label, value=str(value),
            method=method, success=success, error=error,
        ))

    def save_result(self) -> Path:
        self.result.finished_at = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = self.run_dir / "result.json"
        out.write_text(json.dumps(asdict(self.result), indent=2), encoding="utf-8")
        return out

    @abstractmethod
    def apply(self, page: Page, profile: Dict[str, Any]) -> None:
        """Subclass must implement: navigate, fill form, optionally submit."""

    def run(self) -> RunResult:
        profile = load_profile()
        print(f"\n=== {self.ATS_NAME.upper()} APPLY ({'DRY-RUN' if self.dry_run else 'LIVE'}) ===")
        print(f"Company: {self.company}")
        print(f"Role:    {self.role}")
        print(f"URL:     {self.url}")
        print(f"Run dir: {self.run_dir}")
        with sync_playwright() as p:
            launch_args = {
                "headless": self.headless,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ],
            }
            # Prefer real Chrome over bundled Chromium (much higher reCAPTCHA score).
            try:
                browser = p.chromium.launch(channel="chrome", **launch_args)
                self.note("launched real Chrome (channel=chrome)")
            except Exception:
                browser = p.chromium.launch(**launch_args)
                self.note("real Chrome unavailable, fell back to bundled Chromium")
            context = browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Safari/537.36"),
                viewport={"width": 1400, "height": 900},
                locale="en-US",
                timezone_id="America/Los_Angeles",
            )
            if _HAS_STEALTH:
                try:
                    Stealth().apply_stealth_sync(context)
                    self.note("stealth patches applied")
                except Exception as e:
                    self.note(f"stealth apply failed: {e}")
            page = context.new_page()
            try:
                self.apply(page, profile)
            except Exception as e:
                self.result.error = f"{type(e).__name__}: {e}"
                self.note(f"FATAL: {self.result.error}")
                self.screenshot(page, "fatal")
            finally:
                # In prep mode, hold the browser open so the human can review
                # and click Submit themselves (defeats reCAPTCHA Enterprise v3).
                if self.prep_mode and not self.result.error:
                    print("\n" + "=" * 60)
                    print("PREP MODE: Form is filled. Browser is open.")
                    print("Review the form, click Submit yourself, then press Enter here.")
                    print("=" * 60)
                    try:
                        input("Press Enter after you've submitted (or want to close): ")
                    except EOFError:
                        time.sleep(60)
                self.save_result()
                browser.close()
        # Summary
        print(f"\n--- Summary ---")
        print(f"  Fields filled: {sum(1 for f in self.result.fields if f.success)}/{len(self.result.fields)}")
        print(f"  Screenshots:   {len(self.result.screenshots)}")
        print(f"  Submitted:     {self.result.submitted}")
        if self.result.error:
            print(f"  Error:         {self.result.error}")
        print(f"  Result:        {self.run_dir / 'result.json'}")
        return self.result


def safe_fill(page: Page, applier: BaseApplier, selector: str, value: str, label: str) -> bool:
    """Try to fill a selector; record success/failure in run log. Returns success."""
    try:
        loc = page.locator(selector).first
        if loc.count() == 0:
            applier.record_fill(selector, label, value, "fill", success=False, error="not-found")
            return False
        loc.scroll_into_view_if_needed(timeout=3000)
        loc.fill(value, timeout=5000)
        applier.record_fill(selector, label, value, "fill", success=True)
        return True
    except Exception as e:
        applier.record_fill(selector, label, value, "fill", success=False, error=str(e)[:200])
        return False


def safe_select(page: Page, applier: BaseApplier, selector: str, value: str, label: str) -> bool:
    try:
        loc = page.locator(selector).first
        if loc.count() == 0:
            applier.record_fill(selector, label, value, "select", success=False, error="not-found")
            return False
        loc.scroll_into_view_if_needed(timeout=3000)
        loc.select_option(value=value, timeout=5000)
        applier.record_fill(selector, label, value, "select", success=True)
        return True
    except Exception as e:
        applier.record_fill(selector, label, value, "select", success=False, error=str(e)[:200])
        return False


def safe_upload(page: Page, applier: BaseApplier, selector: str, file_path: Path, label: str) -> bool:
    try:
        loc = page.locator(selector).first
        if loc.count() == 0:
            applier.record_fill(selector, label, str(file_path), "upload", success=False, error="not-found")
            return False
        loc.set_input_files(str(file_path), timeout=10000)
        applier.record_fill(selector, label, str(file_path), "upload", success=True)
        return True
    except Exception as e:
        applier.record_fill(selector, label, str(file_path), "upload", success=False, error=str(e)[:200])
        return False
