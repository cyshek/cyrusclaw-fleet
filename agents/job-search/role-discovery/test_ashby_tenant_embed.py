"""Tests for the Ashby tenant-embed fallback (chain ashby-tenant-embed-2026-05-30).

Covers:
  * load_ashby_tenant_embed_registry: malformed/missing file safety.
  * _ashby_tenant_embed_fallback: registry hit/miss, captcha_clean guard,
    role_slug vs job_id vs override modes, case-insensitive tenant match,
    publicWebsite-only entries without override.
  * Decision matrix integration: emit_browser_plan rewrites plan["url"] when
    the registry resolves, and falls through cleanly when it doesn't.
"""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import inline_submit as IS  # noqa: E402


CURSOR_ENTRY = {
    "tenant": "cursor",
    "publicWebsite": "https://www.cursor.com",
    "customJobsPageUrl": "https://cursor.com/careers",
    "embed_url_template": "https://cursor.com/careers/{role_slug}",
    "slug_mode": "role_slug",
    "captcha_clean": True,
    "verified_at": "2026-05-30",
}

ACME_JOBID_ENTRY = {
    "tenant": "acme",
    "publicWebsite": "https://acme.example",
    "embed_url_template": "https://acme.example/jobs/{job_id}",
    "slug_mode": "job_id",
    "captcha_clean": True,
    "verified_at": "2026-05-30",
}

WALLED_ENTRY = {
    "tenant": "walled",
    "publicWebsite": "https://walled.example",
    "embed_url_template": "https://walled.example/careers/{role_slug}",
    "slug_mode": "role_slug",
    "captcha_clean": False,
    "verified_at": "2026-05-30",
}

CUSTOM_SLUG_ENTRY = {
    "tenant": "kustom",
    "publicWebsite": "https://kustom.example",
    "embed_url_template": "https://kustom.example/work/{slug}",
    "slug_mode": "custom",
    "captcha_clean": True,
    "verified_at": "2026-05-30",
}

REG = {
    "Cursor": CURSOR_ENTRY,  # mixed-case key to exercise normalization
    "acme": ACME_JOBID_ENTRY,
    "walled": WALLED_ENTRY,
    "kustom": CUSTOM_SLUG_ENTRY,
}


class LoadRegistryTests(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        with mock.patch.object(IS, "ASHBY_TENANT_EMBED_REGISTRY_PATH",
                               Path("/tmp/__nonexistent_ashby_registry__.json")):
            self.assertEqual(IS.load_ashby_tenant_embed_registry(), {})

    def test_malformed_json_returns_empty(self, tmp_path=None):
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{ not json")
            p = Path(fh.name)
        try:
            with mock.patch.object(IS, "ASHBY_TENANT_EMBED_REGISTRY_PATH", p):
                self.assertEqual(IS.load_ashby_tenant_embed_registry(), {})
        finally:
            p.unlink(missing_ok=True)

    def test_loads_tenants_key(self):
        from tempfile import NamedTemporaryFile
        with NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"tenants": {"cursor": CURSOR_ENTRY}}, fh)
            p = Path(fh.name)
        try:
            with mock.patch.object(IS, "ASHBY_TENANT_EMBED_REGISTRY_PATH", p):
                got = IS.load_ashby_tenant_embed_registry()
                self.assertIn("cursor", got)
                self.assertEqual(got["cursor"]["embed_url_template"],
                                 "https://cursor.com/careers/{role_slug}")
        finally:
            p.unlink(missing_ok=True)


class FallbackResolveTests(unittest.TestCase):
    def test_unknown_tenant_returns_none(self):
        r = IS._ashby_tenant_embed_fallback("unknown", "uuid", role_title="X", registry=REG)
        self.assertIsNone(r)

    def test_role_slug_mode_resolves(self):
        r = IS._ashby_tenant_embed_fallback(
            "cursor", "uuid-1234", role_title="Forward Deployed Engineer", registry=REG)
        self.assertIsNotNone(r)
        self.assertEqual(r["embed_url"],
                         "https://cursor.com/careers/forward-deployed-engineer")
        self.assertEqual(r["slug_mode"], "role_slug")

    def test_case_insensitive_tenant_key(self):
        # registry has "Cursor"; lookup uses lowercase "cursor".
        r = IS._ashby_tenant_embed_fallback(
            "cursor", "uuid", role_title="Solutions Engineer", registry=REG)
        self.assertIsNotNone(r)
        self.assertIn("solutions-engineer", r["embed_url"])

    def test_job_id_mode_resolves(self):
        r = IS._ashby_tenant_embed_fallback(
            "acme", "abc-123", role_title=None, registry=REG)
        self.assertIsNotNone(r)
        self.assertEqual(r["embed_url"], "https://acme.example/jobs/abc-123")
        self.assertEqual(r["slug_mode"], "job_id")

    def test_role_slug_mode_requires_title(self):
        r = IS._ashby_tenant_embed_fallback(
            "cursor", "uuid", role_title=None, registry=REG)
        self.assertIsNone(r)

    def test_captcha_walled_entry_skipped(self):
        r = IS._ashby_tenant_embed_fallback(
            "walled", "uuid", role_title="Eng", registry=REG)
        self.assertIsNone(r)

    def test_custom_mode_needs_override(self):
        # No override → custom mode returns None.
        r = IS._ashby_tenant_embed_fallback(
            "kustom", "uuid", role_title="Eng", registry=REG)
        self.assertIsNone(r)
        # With override → resolves.
        r2 = IS._ashby_tenant_embed_fallback(
            "kustom", "uuid", role_title="Eng",
            embed_slug_override="my-custom-slug", registry=REG)
        self.assertIsNotNone(r2)
        self.assertEqual(r2["embed_url"], "https://kustom.example/work/my-custom-slug")
        self.assertEqual(r2["slug_mode"], "override")

    def test_override_wins_over_role_slug_mode(self):
        r = IS._ashby_tenant_embed_fallback(
            "cursor", "uuid", role_title="Forward Deployed Engineer",
            embed_slug_override="custom-slug", registry=REG)
        self.assertIsNotNone(r)
        self.assertIn("custom-slug", r["embed_url"])
        self.assertEqual(r["slug_mode"], "override")

    def test_empty_registry_returns_none(self):
        self.assertIsNone(IS._ashby_tenant_embed_fallback("cursor", "uuid",
                                                         role_title="X", registry={}))

    def test_missing_template_returns_none(self):
        bad = {"cursor": {"captcha_clean": True, "slug_mode": "role_slug"}}
        self.assertIsNone(IS._ashby_tenant_embed_fallback(
            "cursor", "uuid", role_title="X", registry=bad))


class ProductionRegistryFileTests(unittest.TestCase):
    """The shipped registry file must (a) parse, (b) include Cursor as a clean
    entry, (c) resolve correctly for a known role title."""

    def test_registry_file_loads(self):
        reg = IS.load_ashby_tenant_embed_registry()
        self.assertIn("cursor", reg, msg="Cursor must remain the row-1 entry")
        self.assertTrue(reg["cursor"]["captcha_clean"])
        self.assertEqual(reg["cursor"]["slug_mode"], "role_slug")

    def test_cursor_resolves_against_shipped_registry(self):
        r = IS._ashby_tenant_embed_fallback(
            "cursor", "uuid-xyz", role_title="Forward Deployed Engineer")
        self.assertIsNotNone(r)
        self.assertEqual(r["embed_url"],
                         "https://cursor.com/careers/forward-deployed-engineer")


class EmitPlanIntegrationTests(unittest.TestCase):
    """Verify emit_browser_plan rewrites the Ashby plan URL when the registry
    resolves. Uses heavy mocking to avoid touching greenhouse/ashby filler
    imports + cover-answer file IO."""

    def _common_spec(self, org, jid, title):
        return {
            "ats": "ashby",
            "org": org,
            "job_id": jid,
            "title": title,
            "url": f"https://jobs.ashbyhq.com/{org}/{jid}/application",
        }

    def _patch_filler(self, ashby_url, override_steps=None):
        """Returns a mock module that mimics ashby_filler.{build_plan,emit_steps}."""
        m = mock.MagicMock()
        m.build_plan.return_value = {
            "url": ashby_url,
            "text_fields": [],
            "radios": [],
            "checkboxes": [],
            "resume_path": None,
            "skipped": [],
            "needs_review": [],
        }
        def _emit(plan, label):
            # Echo plan["url"] so the test can observe rewrite happened pre-emit.
            return [{"tool": "browser.navigate", "args": {"url": plan["url"]}}]
        m.emit_steps.side_effect = _emit
        return m

    def _run_emit(self, spec, registry):
        """Run emit_browser_plan with all heavy filesystem/import deps mocked."""
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as td:
            tdp = Path(td)
            spec_path = tdp / "spec.json"
            spec_path.write_text(json.dumps(spec))
            pdf_path = tdp / "resume.pdf"
            pdf_path.write_bytes(b"%PDF-fake")
            workdir = tdp / "wd"; workdir.mkdir()
            # cover_answers.md absent → merge_cover_answers_into_plan should
            # be a no-op for this test (we'll mock it).

            fake_af = self._patch_filler(spec["url"])
            import importlib as _importlib
            real_import_module = _importlib.import_module

            def fake_import_module(name, *a, **k):
                if name == "ashby_filler":
                    return fake_af
                if name == "greenhouse_filler":
                    return mock.MagicMock()
                return real_import_module(name, *a, **k)

            with mock.patch.object(IS, "load_ashby_tenant_embed_registry",
                                   return_value=registry), \
                 mock.patch.object(IS, "merge_cover_answers_into_plan",
                                   side_effect=lambda p, s, c: p), \
                 mock.patch.object(IS, "UPLOADS_DIR", tdp / "uploads"), \
                 mock.patch.object(IS, "OUTPUT_DIR", tdp / "out"), \
                 mock.patch("importlib.import_module", side_effect=fake_import_module):
                out_path = IS.emit_browser_plan(
                    slug="acme-test", spec_path=spec_path,
                    pdf_path=pdf_path, workdir=workdir)
            return json.loads(Path(out_path).read_text())

    def test_registry_hit_rewrites_url_and_tags_ats(self):
        spec = self._common_spec("cursor", "uuid-1",
                                 "Forward Deployed Engineer")
        plan = self._run_emit(spec, REG)
        self.assertEqual(plan["url"],
                         "https://cursor.com/careers/forward-deployed-engineer")
        self.assertEqual(plan["ats"], "ashby_tenant_embed")
        self.assertIsNotNone(plan["tenant_embed"])
        self.assertEqual(plan["tenant_embed"]["slug_mode"], "role_slug")

    def test_registry_miss_keeps_original_ashby_url(self):
        spec = self._common_spec("unknown-tenant", "uuid-2", "Some Role")
        plan = self._run_emit(spec, REG)
        self.assertEqual(plan["url"],
                         "https://jobs.ashbyhq.com/unknown-tenant/uuid-2/application")
        self.assertEqual(plan["ats"], "ashby")
        self.assertIsNone(plan["tenant_embed"])

    def test_walled_entry_does_not_rewrite(self):
        spec = self._common_spec("walled", "uuid-3", "Eng")
        plan = self._run_emit(spec, REG)
        self.assertIn("ashbyhq.com", plan["url"])
        self.assertIsNone(plan["tenant_embed"])

    def test_spec_embed_slug_override_threads_through(self):
        spec = self._common_spec("kustom", "uuid-4", "Eng")
        spec["embed_slug"] = "weirdly-spelled-role"
        plan = self._run_emit(spec, REG)
        self.assertEqual(plan["url"],
                         "https://kustom.example/work/weirdly-spelled-role")
        self.assertEqual(plan["ats"], "ashby_tenant_embed")


if __name__ == "__main__":
    unittest.main()
