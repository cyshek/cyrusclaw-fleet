"""Tests for Workday FIX3: resume-upload re-verify on My-Experience revisit.

Root cause (EXFO-2121): `handle_experience()` previously returned `already=True`
when any work-exp block had a jobTitle value. On drop-on-revisit tenants, after
`populate_work_history()` fills those blocks the jobTitle clause fired → re-upload
permanently skipped even though the file was dropped → EXIT-5 loop-cap.

FIX: separate file_present (widget/text) from profile_prefill_skip (only when
no upload input is visible), so re-upload fires whenever the file actually dropped.
"""
import importlib.util
import pathlib
import unittest
from unittest.mock import MagicMock, patch

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "_workday_runner", HERE / "_workday_runner.py"
)
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)


# ---------------------------------------------------------------------------
# Minimal FakePage that lets us control evaluate() and locator() responses
# ---------------------------------------------------------------------------
class FakeLocator:
    def __init__(self, count=0):
        self._count = count
        self.first = self
        self._set_input_calls = []

    def count(self):
        return self._count

    def set_input_files(self, path):
        self._set_input_calls.append(path)


class FakePage:
    """Controllable page stub for handle_experience tests."""

    def __init__(self, evaluate_seq, file_input_count=1):
        self._evals = list(evaluate_seq)
        self._eval_idx = 0
        self._file_input_count = file_input_count
        self.wait_for_timeout = MagicMock()
        # Track the set_input_files locator so we can count calls
        self._inp_locator = FakeLocator(count=file_input_count)

    def evaluate(self, expr, *args, **kwargs):
        if self._eval_idx < len(self._evals):
            val = self._evals[self._eval_idx]
        else:
            val = False
        self._eval_idx += 1
        return val

    def locator(self, sel):
        return self._inp_locator

    @property
    def set_input_call_count(self):
        return len(self._inp_locator._set_input_calls)


class TestUploadReverify(unittest.TestCase):
    """Verify handle_experience() re-upload logic after FIX3."""

    def _run(self, evaluate_seq, file_input_count=1):
        page = FakePage(evaluate_seq, file_input_count=file_input_count)
        wd._RESUME_UPLOADED = 0  # reset run-scoped upload counter so it never leaks between tests
        with patch.object(wd, "populate_work_history"), \
             patch.object(wd, "delete_empty_we_blocks"), \
             patch.object(wd, "shot"):
            wd.handle_experience(page, "/tmp/resume.pdf")
        return page.set_input_call_count

    # --- Scenario 1: FIX3 core — file dropped, WE blocks filled, input visible, NO
    #     required-upload error → must re-upload via the standard _MAX_RESUME_UPLOADS path ---
    def test_reuploads_when_file_dropped_but_workexp_filled(self):
        """EXFO-2121 scenario: file_present=False, WE blocks filled, upload input visible,
        no 'required' upload error → must re-upload (old code: already=True via jobTitle →
        skip. New: re-upload). NOTE eval order = [file_present, upload_required_error,
        (profile_prefill_skip skipped because upload input IS visible)]."""
        evaluate_seq = [
            False,  # file_present: no "successfully uploaded" / no DeleteFile widget
            False,  # upload_required_empty error-text check: NO required error (EXFO-class)
        ]
        calls = self._run(evaluate_seq, file_input_count=1)
        self.assertEqual(calls, 1, "Should re-upload when file dropped even if WE blocks filled")

    # --- Scenario 2: file actually present → skip ---
    def test_skips_upload_when_file_present(self):
        """file_present=True → skip re-upload (correct idempotent guard for first-visit)."""
        evaluate_seq = [True]  # file_present=True
        calls = self._run(evaluate_seq, file_input_count=1)
        self.assertEqual(calls, 0, "Should NOT re-upload when file widget already shows file")

    # --- Scenario 3: RBI-class — no upload input widget, WE blocks filled → skip ---
    def test_skips_upload_for_profile_prefill_no_input_widget(self):
        """profile_prefill_skip: no upload input visible + WE blocks filled
        → skip (RBI tenant: file widget suppressed, profile already has resume).
        eval order with NO upload input = [file_present, profile_prefill_skip]
        (upload_required_empty is False without re-evaluating because upload_input_visible
        is False, so its evaluate is short-circuited and consumes NO slot)."""
        evaluate_seq = [
            False,  # file_present=False
            True,   # jobTitle-in-blocks=True (profile_prefill_skip, input widget absent)
        ]
        # file_input_count=0 → no upload input → profile_prefill_skip=True
        calls = self._run(evaluate_seq, file_input_count=0)
        self.assertEqual(calls, 0, "Should skip when profile-prefill suppresses upload widget")

    # --- Scenario 4: clean first visit, nothing uploaded, no blocks ---
    def test_uploads_on_first_visit_nothing_present(self):
        """First visit, clean tenant: file_present=False, no required error → upload."""
        evaluate_seq = [False, False]  # file_present=False, no required-upload error
        calls = self._run(evaluate_seq, file_input_count=1)
        self.assertEqual(calls, 1)

    # --- Scenario 5: delete_empty_we_blocks called on every entry ---
    def test_delete_empty_blocks_called_on_every_entry(self):
        """FIX3: delete_empty_we_blocks() must run on every handle_experience call
        to clear per-revisit regenerated trailing empty blocks."""
        page = FakePage([True], file_input_count=1)
        with patch.object(wd, "populate_work_history"), \
             patch.object(wd, "delete_empty_we_blocks") as mock_del, \
             patch.object(wd, "shot"):
            wd.handle_experience(page, "/tmp/resume.pdf")
        mock_del.assert_called_once()

    # --- Scenario 6: no file AND no blocks AND no input widget → still no upload ---
    def test_no_upload_attempt_when_no_input_widget_or_file(self):
        """If no upload input widget exists and file_present=False and WE blocks empty
        → profile_prefill_skip=False but also no inp to upload to → no set_input_files."""
        evaluate_seq = [False, False]
        # No upload input visible, no WE blocks → profile_prefill_skip=False, already=False
        # but locator count=0 → set_input_files never reached
        calls = self._run(evaluate_seq, file_input_count=0)
        self.assertEqual(calls, 0, "No upload input means no set_input_files call possible")

    # --- Scenario 7: Gates-class upload cap — file_present always False, input always
    #     visible, NO required error, called many times -> uploads CAPPED at
    #     _MAX_RESUME_UPLOADS (not infinite). ---
    def test_reupload_capped_for_gates_class_no_marker(self):
        """Gates-2542 scenario: tenant attaches the file but renders NO 'successfully
        uploaded' marker, so file_present is False on every revisit and the upload input
        stays visible. Without a cap this re-uploads every visit -> a new parser WE block
        each time -> EXIT-5 loop. The cap stops re-upload after _MAX_RESUME_UPLOADS.
        eval order = [file_present=False, upload_required_error=False]."""
        wd._RESUME_UPLOADED = 0  # fresh run
        wd._RESUME_REQ_REUPLOADS = 0
        total_uploads = 0
        # Simulate 6 My-Experience revisits, each: file_present=False, NO required error.
        for _visit in range(6):
            page = FakePage([False, False], file_input_count=1)
            with patch.object(wd, "populate_work_history"), \
                 patch.object(wd, "delete_empty_we_blocks"), \
                 patch.object(wd, "shot"):
                wd.handle_experience(page, "/tmp/resume.pdf")
            total_uploads += page.set_input_call_count
        self.assertEqual(total_uploads, wd._MAX_RESUME_UPLOADS,
                         f"Gates-class re-upload must cap at {wd._MAX_RESUME_UPLOADS}, got {total_uploads}")

    # --- Scenario 8: Boeing-class REQUIRED-upload widget — file dropped on revisit AND an
    #     explicit 'Upload a file ... is required' error -> re-upload EXEMPT from
    #     _MAX_RESUME_UPLOADS, bounded instead by _MAX_REQ_REUPLOADS. ---
    def test_boeing_required_upload_reuploads_past_max_resume_uploads(self):
        """Boeing-2546/PayPal-2891: the resume/CV upload widget is a HARD-REQUIRED field and
        Workday drops the file display on cross-nav revisit, surfacing a 'required' upload
        error. The required-upload override must re-upload, bounded by _MAX_REQ_REUPLOADS=1
        (2026-06-13 cap fix: was 4, caused 4 parser runs = 4 new empty WE blocks = EXIT-5).
        After 1 re-upload we trust the server-side file on further revisits.
        eval order = [file_present=False, required_error=True]."""
        wd._RESUME_UPLOADED = 0
        wd._RESUME_REQ_REUPLOADS = 0
        wd._ACCOUNT_MODE = "signin_fresh"  # fresh path (where the uploaded-once skip lives)
        total_uploads = 0
        for _visit in range(6):
            page = FakePage([False, True], file_input_count=1)  # file dropped + required error
            with patch.object(wd, "populate_work_history"), \
                 patch.object(wd, "delete_empty_we_blocks"), \
                 patch.object(wd, "shot"):
                wd.handle_experience(page, "/tmp/resume.pdf")
            total_uploads += page.set_input_call_count
        # Cap=1: exactly one re-upload allowed on required-empty revisit,
        # then we trust server-side file. Never more than _MAX_REQ_REUPLOADS.
        self.assertEqual(total_uploads, wd._MAX_REQ_REUPLOADS,
                         f"Boeing/PayPal required-upload must re-upload up to {wd._MAX_REQ_REUPLOADS} "
                         f"(cap=1 fix 2026-06-13), got {total_uploads}")
        wd._ACCOUNT_MODE = None  # restore


if __name__ == "__main__":
    unittest.main()
