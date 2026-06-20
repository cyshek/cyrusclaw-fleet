"""Unit tests for chain_010 React-onChange trigger (Option A).

Validates JS payload shape + kill-switch wiring without spinning a browser.
"""
import re
import unittest
from pathlib import Path

import greenhouse_filler as gf
import greenhouse_iframe_runner as gir


class TestReactResumeTriggerJS(unittest.TestCase):
    def test_constant_exists(self):
        self.assertTrue(hasattr(gf, "JS_REACT_RESUME_TRIGGER"))
        self.assertIsInstance(gf.JS_REACT_RESUME_TRIGGER, str)
        self.assertGreater(len(gf.JS_REACT_RESUME_TRIGGER), 100)

    def test_accepts_b64_filename_mime_arg(self):
        # Signature `({ b64, filename, mime }) => { ... }`
        head = gf.JS_REACT_RESUME_TRIGGER.lstrip().splitlines()[0]
        self.assertIn("b64", head)
        self.assertIn("filename", head)
        self.assertIn("mime", head)

    def test_uses_react_native_setter(self):
        js = gf.JS_REACT_RESUME_TRIGGER
        # The bug-fix pattern: prototype descriptor + .set.call(inp, files)
        self.assertIn("Object.getOwnPropertyDescriptor", js)
        self.assertIn("window.HTMLInputElement.prototype", js)
        self.assertIn("'files'", js)
        self.assertIn(".set.call(inp", js)

    def test_dispatches_bubbling_change_event(self):
        js = gf.JS_REACT_RESUME_TRIGGER
        # Must dispatch a real, bubbling change event so React onChange fires
        self.assertIn("dispatchEvent", js)
        self.assertIn("new Event('change'", js)
        self.assertIn("bubbles: true", js)

    def test_constructs_page_realm_file(self):
        js = gf.JS_REACT_RESUME_TRIGGER
        # Page-realm File construction (avoids cross-realm instanceof mismatch)
        self.assertIn("new File(", js)
        self.assertIn("atob(b64)", js)
        self.assertIn("DataTransfer", js)
        self.assertIn("dt.items.add(file)", js)

    def test_selector_fallback_chain(self):
        js = gf.JS_REACT_RESUME_TRIGGER
        # Primary + fallbacks
        self.assertIn("'#resume'", js)
        self.assertIn("input[type=file][name*=\"resume\" i]", js)
        self.assertIn("'input[type=file]'", js)

    def test_returns_observability_fields(self):
        js = gf.JS_REACT_RESUME_TRIGGER
        for key in ("triggered", "input_selector", "input_found",
                    "files_before", "files_after", "native_setter_used",
                    "change_dispatched", "err"):
            self.assertIn(key, js, f"missing observability field: {key}")

    def test_marks_window_after_trigger(self):
        # Runner reads window.__gh_react_resume_triggered post-trigger
        self.assertIn("__gh_react_resume_triggered", gf.JS_REACT_RESUME_TRIGGER)


class TestRunnerWiring(unittest.TestCase):
    def test_use_react_resume_trigger_flag_exists(self):
        self.assertTrue(hasattr(gir, "USE_REACT_RESUME_TRIGGER"))
        # Default ON per the design (we WANT this enabled)
        self.assertTrue(gir.USE_REACT_RESUME_TRIGGER)

    def test_runner_calls_trigger_only_when_flag_true(self):
        # The trigger call must be guarded by `if USE_REACT_RESUME_TRIGGER`
        src = Path(gir.__file__).read_text()
        self.assertIn("USE_REACT_RESUME_TRIGGER", src)
        self.assertIn("JS_REACT_RESUME_TRIGGER", src)
        # The call must be guarded
        idx_call = src.index("JS_REACT_RESUME_TRIGGER")
        # Look 400 chars before the call for the guard
        prefix = src[max(0, idx_call - 600):idx_call]
        self.assertIn("if USE_REACT_RESUME_TRIGGER", prefix)

    def test_trigger_runs_after_inject(self):
        src = Path(gir.__file__).read_text()
        i_inj = src.index("JS_INSTALL_RESUME_INJECT")
        i_trig = src.index("JS_REACT_RESUME_TRIGGER")
        self.assertLess(i_inj, i_trig, "trigger must come after inject in source order")

    def test_trigger_passes_b64_filename_mime(self):
        src = Path(gir.__file__).read_text()
        # Find the evalfn(...JS_REACT_RESUME_TRIGGER...) block
        m = re.search(r"evalfn\(gf\.JS_REACT_RESUME_TRIGGER,\s*\{(.+?)\}\)",
                      src, re.DOTALL)
        self.assertIsNotNone(m, "trigger evalfn call not found")
        args = m.group(1)
        self.assertIn('"b64"', args)
        self.assertIn('"filename"', args)
        self.assertIn('"mime"', args)


class TestNoRegressionOnExistingPath(unittest.TestCase):
    def test_install_resume_inject_unchanged(self):
        # The chain_009 inject payload must still exist and be wired
        self.assertTrue(hasattr(gf, "JS_INSTALL_RESUME_INJECT"))
        self.assertIn("__gh_resume_inject", gf.JS_INSTALL_RESUME_INJECT)

    def test_s3_uploader_flag_still_default_on(self):
        self.assertTrue(gir.USE_GH_S3_UPLOADER)


if __name__ == "__main__":
    unittest.main()
