"""Tests for discover_companies.py"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))
from discover_companies import name_to_slugs, probe_gh, probe_ashby, probe_company, load_existing


# ============================================================
# 1. Slug derivation tests
# ============================================================

class TestNameToSlugs:
    def test_simple_name(self):
        slugs = name_to_slugs("Anthropic")
        assert slugs[0] == "anthropic"

    def test_name_with_spaces_becomes_hyphens(self):
        slugs = name_to_slugs("Culture Amp")
        assert "culture-amp" in slugs

    def test_name_with_ampersand(self):
        # Weights & Biases has special map entry
        slugs = name_to_slugs("Weights & Biases")
        assert "wandb" in slugs

    def test_special_map_skip(self):
        # Y Combinator should return empty (skip)
        slugs = name_to_slugs("Y Combinator")
        assert slugs == []

    def test_suffix_removal_ai(self):
        # "Mistral AI" -> should include "mistral" (suffix -ai removed)
        slugs = name_to_slugs("Mistral AI")
        assert "mistral" in slugs
        assert "mistral-ai" in slugs

    def test_suffix_removal_labs(self):
        slugs = name_to_slugs("Lambda Labs")
        assert "lambda-labs" in slugs
        assert "lambda" in slugs

    def test_no_hyphens_variant(self):
        slugs = name_to_slugs("Fly.io")
        assert "flyio" in slugs
        assert "fly-io" in slugs

    def test_deduplication(self):
        # No duplicate slugs in output
        slugs = name_to_slugs("Scale AI")
        assert len(slugs) == len(set(slugs))

    def test_numeric_in_name(self):
        slugs = name_to_slugs("1Password")
        assert "1password" in slugs

    def test_special_chars_stripped(self):
        slugs = name_to_slugs("Trigger.dev")
        assert "trigger-dev" in slugs or "triggerdev" in slugs


# ============================================================
# 2. Dedup logic tests
# ============================================================

class TestDedup:
    def test_probe_company_already_in_gh(self):
        """If a slug is already in gh_slugs, returns 'already' immediately."""
        result = probe_company(
            "Stripe",
            ["stripe"],
            gh_slugs={"stripe"},
            ashby_slugs=set(),
        )
        assert result == ("Stripe", "greenhouse", "stripe", "already")

    def test_probe_company_already_in_ashby(self):
        result = probe_company(
            "Linear",
            ["linear"],
            gh_slugs=set(),
            ashby_slugs={"linear"},
        )
        assert result == ("Linear", "ashby", "linear", "already")

    def test_probe_company_already_checked_before_http(self):
        """already-check must happen before any HTTP call."""
        with patch("discover_companies.probe_gh") as mock_gh, \
             patch("discover_companies.probe_ashby") as mock_ash:
            probe_company("Stripe", ["stripe"], gh_slugs={"stripe"}, ashby_slugs=set(), sleep=0)
            mock_gh.assert_not_called()
            mock_ash.assert_not_called()


# ============================================================
# 3. Mock-probe flow tests
# ============================================================

class TestMockProbe:
    def test_probe_company_gh_found(self):
        with patch("discover_companies.probe_gh", return_value=True), \
             patch("discover_companies.probe_ashby", return_value=False):
            result = probe_company("NewCo", ["newco"], set(), set(), sleep=0)
            assert result == ("NewCo", "greenhouse", "newco", "new")

    def test_probe_company_ashby_found_when_gh_fails(self):
        with patch("discover_companies.probe_gh", return_value=False), \
             patch("discover_companies.probe_ashby", return_value=True):
            result = probe_company("NewCo", ["newco"], set(), set(), sleep=0)
            assert result == ("NewCo", "ashby", "newco", "new")

    def test_probe_company_miss(self):
        with patch("discover_companies.probe_gh", return_value=False), \
             patch("discover_companies.probe_ashby", return_value=False):
            result = probe_company("NoBoard", ["noboard"], set(), set(), sleep=0)
            assert result == ("NoBoard", None, None, "miss")

    def test_probe_company_first_slug_wins(self):
        """First GH hit wins; don't probe remaining slugs."""
        calls = []
        def mock_gh(slug):
            calls.append(slug)
            return slug == "first-slug"
        with patch("discover_companies.probe_gh", side_effect=mock_gh), \
             patch("discover_companies.probe_ashby", return_value=False):
            result = probe_company("Multi", ["first-slug", "second-slug"], set(), set(), sleep=0)
            assert result[3] == "new"
            assert result[2] == "first-slug"
            assert "second-slug" not in calls  # stopped after first hit

    def test_probe_gh_http_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("discover_companies.requests.get", return_value=mock_resp):
            assert probe_gh("testslug") is True

    def test_probe_gh_http_404(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("discover_companies.requests.get", return_value=mock_resp):
            assert probe_gh("badslug") is False

    def test_probe_ashby_http_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("discover_companies.requests.get", return_value=mock_resp):
            assert probe_ashby("testslug") is True

    def test_probe_ashby_network_error(self):
        with patch("discover_companies.requests.get", side_effect=Exception("timeout")):
            assert probe_ashby("badslug") is False
