"""
test_filestack_upload.py -- Unit tests for filestack_upload.py (Eightfold upload client)

Tests mock requests.post so no real network calls are made.
"""

import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock, mock_open

# Add role-discovery to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from filestack_upload import upload_resume, extract_filestack_handle, get_csrf_from_apply_page


class TestUploadResume(unittest.TestCase):
    """Tests for upload_resume() -- Eightfold /api/application/v2/resume_upload"""

    MOCK_SUCCESS_RESPONSE = {
        "status": 200,
        "error": {"message": "", "body": ""},
        "data": {
            "profile": {
                "encId": "9L5PooLZ8",
                "resumeFilename": "Cyrus_Shekari_Resume.pdf",
                "resumeUrl": "/profile/9L5PooLZ8?export=applied/netflix.com/test.pdf",
                "resumeUrlsTs": [
                    {
                        "url": "/profile/9L5PooLZ8?export=applied/netflix.com/test.pdf",
                        "lastModifiedTs": 1781411224,
                        "info": {"originalFileName": "Cyrus_Shekari_Resume.pdf"},
                    }
                ],
            }
        },
        "metadata": None,
    }

    def _make_mock_response(self, status_code=200, json_data=None, text=None):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data or self.MOCK_SUCCESS_RESPONSE
        mock_resp.text = text or json.dumps(json_data or self.MOCK_SUCCESS_RESPONSE)
        return mock_resp

    def test_successful_upload_returns_enc_id(self):
        """Happy path: upload returns enc_id and resume_filename."""
        mock_resp = self._make_mock_response(200)

        with patch("filestack_upload.requests.post", return_value=mock_resp) as mock_post:
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=b"%PDF-1.4")):
                    result = upload_resume(
                        file_path="/fake/resume.pdf",
                        domain="netflix.com",
                        csrf_token="test-csrf-token",
                        session_cookies={"session": "abc123"},
                    )

        self.assertTrue(result["success"])
        self.assertEqual(result["enc_id"], "9L5PooLZ8")
        self.assertEqual(result["resume_filename"], "Cyrus_Shekari_Resume.pdf")
        self.assertIn("resume_url", result)

    def test_file_bytes_sent_in_multipart(self):
        """The resume file bytes must appear in the multipart body."""
        mock_resp = self._make_mock_response(200)
        fake_content = b"%PDF-1.4 fake resume content"

        with patch("filestack_upload.requests.post", return_value=mock_resp) as mock_post:
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=fake_content)):
                    upload_resume(
                        file_path="/fake/resume.pdf",
                        domain="netflix.com",
                        csrf_token="test-csrf",
                        session_cookies={},
                    )

        call_kwargs = mock_post.call_args
        files_arg = call_kwargs.kwargs.get("files") or call_kwargs[1].get("files") or {}
        # The "resume" key must be in files with the file bytes
        self.assertIn("resume", files_arg)
        fname, fbytes, fmime = files_arg["resume"]
        self.assertEqual(fname, "resume.pdf")
        self.assertEqual(fbytes, fake_content)

    def test_csrf_token_in_both_header_and_body(self):
        """CSRF token must appear in X-CSRFToken header AND _csrf_token form field."""
        mock_resp = self._make_mock_response(200)
        csrf = "IjkyNDZlNzFlNDIzNzU3MWZkNWJhNjEwMDE5YTE1NGQ5NTg5OTYzZDMi"

        with patch("filestack_upload.requests.post", return_value=mock_resp) as mock_post:
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=b"test")):
                    upload_resume(
                        file_path="/fake/resume.pdf",
                        domain="netflix.com",
                        csrf_token=csrf,
                        session_cookies={},
                    )

        call_kwargs = mock_post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers") or {}
        data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data") or {}

        self.assertEqual(headers.get("X-CSRFToken"), csrf, "X-CSRFToken header missing/wrong")
        self.assertEqual(data.get("_csrf_token"), csrf, "_csrf_token form field missing/wrong")

    def test_file_not_found_raises(self):
        """FileNotFoundError if file_path does not exist."""
        with self.assertRaises(FileNotFoundError):
            upload_resume(
                file_path="/nonexistent/resume.pdf",
                domain="netflix.com",
                csrf_token="csrf",
                session_cookies={},
            )

    def test_http_error_returns_failure(self):
        """Non-200 HTTP response returns success=False with error message."""
        mock_resp = self._make_mock_response(
            status_code=400, text="Please reload the page and try again"
        )

        with patch("filestack_upload.requests.post", return_value=mock_resp):
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=b"test")):
                    result = upload_resume(
                        file_path="/fake/resume.pdf",
                        domain="netflix.com",
                        csrf_token="csrf",
                        session_cookies={},
                    )

        self.assertFalse(result["success"])
        self.assertIn("400", result.get("error", ""))

    def test_upload_url_contains_domain_and_user_mode(self):
        """Upload URL must include domain and user_mode query params."""
        mock_resp = self._make_mock_response(200)

        with patch("filestack_upload.requests.post", return_value=mock_resp) as mock_post:
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=b"test")):
                    upload_resume(
                        file_path="/fake/resume.pdf",
                        domain="netflix.com",
                        csrf_token="csrf",
                        session_cookies={},
                    )

        called_url = mock_post.call_args[0][0] if mock_post.call_args[0] else mock_post.call_args.kwargs.get("url", "")
        if not called_url:
            called_url = str(mock_post.call_args)
        self.assertIn("netflix.com", called_url)
        self.assertIn("user_mode", called_url)

    def test_pdf_mime_type(self):
        """PDF files should use application/pdf MIME type."""
        mock_resp = self._make_mock_response(200)

        with patch("filestack_upload.requests.post", return_value=mock_resp) as mock_post:
            with patch("os.path.exists", return_value=True):
                with patch("builtins.open", mock_open(read_data=b"%PDF")):
                    upload_resume(
                        file_path="/fake/resume.pdf",
                        domain="netflix.com",
                        csrf_token="csrf",
                        session_cookies={},
                    )

        files_arg = mock_post.call_args.kwargs.get("files") or mock_post.call_args[1].get("files") or {}
        if "resume" in files_arg:
            _, _, mime = files_arg["resume"]
            self.assertEqual(mime, "application/pdf")


class TestExtractFilestackHandle(unittest.TestCase):
    """Tests for extract_filestack_handle() -- retained for future investigation."""

    def test_handle_from_handle_field(self):
        resp = {"handle": "AbCdEfGhI", "url": "https://cdn.filestackapi.com/AbCdEfGhI"}
        self.assertEqual(extract_filestack_handle(resp), "AbCdEfGhI")

    def test_handle_extracted_from_url(self):
        resp = {"url": "https://cdn.filestackapi.com/AbCdEfGhI"}
        self.assertEqual(extract_filestack_handle(resp), "AbCdEfGhI")

    def test_empty_response_returns_none(self):
        self.assertIsNone(extract_filestack_handle({}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
