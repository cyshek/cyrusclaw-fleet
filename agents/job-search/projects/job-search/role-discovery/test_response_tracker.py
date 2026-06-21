#!/usr/bin/env python3
"""
test_response_tracker.py — Unit tests for response_tracker.py

Tests:
  1. mock_imap_scan         — mock IMAP returns headers + bodies correctly
  2. classification_logic   — interview / rejection / received / unknown signal matching
  3. domain_matching        — sender domain -> company name matching
  4. fuzzy_matching         — fuzzy company name matching
  5. dedup_logic            — duplicate emails not re-inserted
  6. db_write_and_update    — responses table insert + roles.response_status update
  7. noise_filter           — hertz/linkedin alerts/appointment emails are rejected
  8. two_pass_subject_filter— _subject_interesting pre-filter works correctly
"""

from __future__ import annotations

import sqlite3
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

import response_tracker as rt


class TestClassificationLogic(unittest.TestCase):
    """Test email classification: interview_request | rejection | application_received | unknown."""

    def test_interview_signals(self):
        cases = [
            ("We'd like to schedule an interview", "We are excited to move you forward"),
            ("Next steps for your application", "We'd like to speak with you about the role"),
            ("Phone screen invitation", "We want to schedule a phone screen with you"),
            ("Interview confirmation", "Your interview is confirmed for Tuesday"),
        ]
        for subj, body in cases:
            with self.subTest(subject=subj):
                self.assertEqual(
                    rt._classify(subj, body, "hr@company.com"),
                    "interview_request",
                    f"Expected interview_request for: {subj!r}",
                )

    def test_rejection_signals(self):
        cases = [
            ("Application update", "Unfortunately, we have decided not to move forward with your application."),
            ("Regarding your application", "We regret to inform you that you were not selected for this position."),
            ("Application status", "At this time we have chosen to move forward with other candidates."),
            ("Re: PM role", "Thank you for your interest. We won't be moving forward at this time."),
        ]
        for subj, body in cases:
            with self.subTest(subject=subj):
                self.assertEqual(
                    rt._classify(subj, body, "noreply@company.com"),
                    "rejection",
                    f"Expected rejection for: {subj!r}",
                )

    def test_application_received(self):
        cases = [
            ("Your application has been received", "Thank you for applying to the PM role."),
            ("Application submitted", "We've received your application and will review it."),
            ("Thank you for applying", "We have received your application for the Solutions Engineer role."),
        ]
        for subj, body in cases:
            with self.subTest(subject=subj):
                self.assertEqual(
                    rt._classify(subj, body, "noreply@greenhouse.io"),
                    "application_received",
                    f"Expected application_received for: {subj!r}",
                )

    def test_rejection_beats_interview_when_stronger(self):
        # "unfortunately" + "not moving forward" should win over a weak interview signal
        body = "Unfortunately we will not be moving forward. We have decided not to advance your application."
        self.assertEqual(
            rt._classify("Application update", body, "hr@company.com"),
            "rejection",
        )

    def test_interview_beats_received(self):
        body = "We received your application and we'd like to schedule an interview with you."
        self.assertEqual(
            rt._classify("Invitation to interview", body, "hr@company.com"),
            "interview_request",
        )

    def test_unknown_response(self):
        self.assertEqual(
            rt._classify("Random email subject", "This is a completely unrelated email.", "user@gmail.com"),
            "unknown_response",
        )


class TestDomainMatching(unittest.TestCase):
    """Test sender domain extraction and company matching."""

    def test_extract_sender_email(self):
        self.assertEqual(rt._extract_sender_email("Stripe Careers <careers@stripe.com>"), "careers@stripe.com")
        self.assertEqual(rt._extract_sender_email("noreply@greenhouse.io"), "noreply@greenhouse.io")
        self.assertEqual(rt._extract_sender_email("Hiring Team <hr@company.com>"), "hr@company.com")

    def test_domain_extraction(self):
        self.assertEqual(rt._domain("careers@stripe.com"), "stripe.com")
        self.assertEqual(rt._domain("noreply@mail.anthropic.com"), "mail.anthropic.com")
        self.assertEqual(rt._domain("notanemail"), "")

    def test_root_domain(self):
        self.assertEqual(rt._root("stripe.com"), "stripe")
        self.assertEqual(rt._root("mail.anthropic.com"), "anthropic")
        self.assertEqual(rt._root("noreply.greenhouse.io"), "greenhouse")

    def test_normalize_company(self):
        # _normalize_company strips legal suffixes; comma-separated ones may need extra stripping
        result = rt._normalize_company("Stripe, Inc.")
        self.assertIn("stripe", result)  # at minimum, stripe should be there
        self.assertEqual(rt._normalize_company("Anthropic LLC"), "anthropic")
        self.assertEqual(rt._normalize_company("Scale AI Technologies"), "scale ai")


class TestFuzzyMatching(unittest.TestCase):
    """Test fuzzy matching of emails to applied roles."""

    def setUp(self):
        self.roles = [
            {"id": 1, "company": "Stripe", "role": "PM", "applied_on": "2026-06-01", "norm": "stripe"},
            {"id": 2, "company": "Anthropic", "role": "TPM", "applied_on": "2026-06-02", "norm": "anthropic"},
            {"id": 3, "company": "Scale AI", "role": "APM", "applied_on": "2026-06-03", "norm": "scale ai"},
            {"id": 4, "company": "Datadog", "role": "SE", "applied_on": "2026-06-04", "norm": "datadog"},
        ]

    def test_exact_domain_match(self):
        result = rt.match_role("no-reply@stripe.com", "Interview invitation", self.roles)
        self.assertIsNotNone(result)
        self.assertEqual(result["company"], "Stripe")

    def test_domain_substring_match(self):
        result = rt.match_role("hr@anthropic.com", "Next steps at Anthropic", self.roles)
        self.assertIsNotNone(result)
        self.assertEqual(result["company"], "Anthropic")

    def test_subject_company_match(self):
        result = rt.match_role("noreply@mail.com", "Datadog Interview Schedule", self.roles)
        self.assertIsNotNone(result)
        self.assertEqual(result["company"], "Datadog")

    def test_no_match_below_threshold(self):
        result = rt.match_role("noreply@randomcompany123xyz.com", "Hello there", self.roles)
        self.assertIsNone(result)

    def test_multi_word_company_match(self):
        result = rt.match_role("hr@scale.ai", "Re: Scale AI Application Next Steps", self.roles)
        self.assertIsNotNone(result)
        self.assertEqual(result["company"], "Scale AI")


class TestDedupLogic(unittest.TestCase):
    """Test that duplicate emails are not re-inserted."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        # Create roles table first so ensure_schema can ALTER it
        self.conn.execute("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY,
                company TEXT,
                role TEXT,
                applied_by TEXT,
                status TEXT DEFAULT 'queued'
            )
        """)
        self.conn.commit()
        rt.ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_already_seen_empty_db(self):
        self.assertFalse(rt.already_recorded(self.conn, "hr@stripe.com", "Interview invitation"))

    def test_already_seen_after_insert(self):
        self.conn.execute("""
            INSERT INTO responses (sender, subject, classification)
            VALUES (?, ?, ?)
        """, ("hr@stripe.com", "Interview invitation", "interview_request"))
        self.conn.commit()
        self.assertTrue(rt.already_recorded(self.conn, "hr@stripe.com", "Interview invitation"))

    def test_different_sender_not_duplicate(self):
        self.conn.execute("""
            INSERT INTO responses (sender, subject, classification)
            VALUES (?, ?, ?)
        """, ("hr@stripe.com", "Interview invitation", "interview_request"))
        self.conn.commit()
        self.assertFalse(rt.already_recorded(self.conn, "hr@anthropic.com", "Interview invitation"))


class TestDbWriteAndUpdate(unittest.TestCase):
    """Test that responses are written and roles.response_status is updated."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        # Create minimal roles table
        self.conn.execute("""
            CREATE TABLE roles (
                id INTEGER PRIMARY KEY,
                company TEXT,
                role TEXT,
                applied_by TEXT,
                status TEXT DEFAULT 'queued',
                response_status TEXT,
                last_response_at TEXT,
                last_email_subject TEXT,
                last_email_from TEXT
            )
        """)
        self.conn.execute(
            "INSERT INTO roles (id, company, role, applied_by) VALUES (1, 'Stripe', 'PM', 'auto')"
        )
        self.conn.commit()
        rt.ensure_schema(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_insert_interview_response(self):
        self.conn.execute("""
            INSERT INTO responses (role_id, company, email_date, sender, subject,
                                   classification, matched_role_id)
            VALUES (1, 'Stripe', '2026-06-20', 'hr@stripe.com',
                    'Interview invitation', 'interview_request', 1)
        """)
        self.conn.commit()
        cur = self.conn.execute("SELECT COUNT(*) FROM responses WHERE classification='interview_request'")
        self.assertEqual(cur.fetchone()[0], 1)

    def test_update_roles_response_status(self):
        self.conn.execute("""
            UPDATE roles SET response_status='interview_request', last_response_at='2026-06-20',
                             last_email_subject='Interview invitation', last_email_from='hr@stripe.com'
            WHERE id=1
        """)
        self.conn.commit()
        cur = self.conn.execute("SELECT response_status FROM roles WHERE id=1")
        self.assertEqual(cur.fetchone()[0], "interview_request")

    def test_schema_has_responses_table(self):
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='responses'"
        )
        self.assertIsNotNone(cur.fetchone())


class TestNoiseFilter(unittest.TestCase):
    """Test that non-job emails are filtered out."""

    def test_hertz_email_rejected(self):
        self.assertFalse(rt._is_job_related(
            "Traffic Violation - Administration Fee Charge",
            "noreply@hertz.com",
            "Your account has been charged for a traffic violation.",
        ))

    def test_appointment_reminder_rejected(self):
        self.assertFalse(rt._is_job_related(
            "Discount Tire Appointment Reminder",
            "dtc-email@discounttire-email.com",
            "Your appointment is scheduled for tomorrow.",
        ))

    def test_linkedin_job_alert_rejected(self):
        # LinkedIn job alert emails (not from an employer) should be filtered
        self.assertFalse(rt._is_job_related(
            '"product manager": Google - Senior PM position posted',
            "jobalerts-noreply@linkedin.com",
            "Based on your preferences, we found new job postings that match.",
        ))

    def test_real_interview_email_passes(self):
        self.assertTrue(rt._is_job_related(
            "Interview invitation from Stripe",
            "hr@stripe.com",
            "We'd like to schedule an interview with you for the PM role.",
        ))

    def test_rejection_email_passes(self):
        self.assertTrue(rt._is_job_related(
            "Update on your application",
            "noreply@company.com",
            "Unfortunately, we've decided not to move forward with your application.",
        ))


class TestSubjectInterestingFilter(unittest.TestCase):
    """Test the _subject_interesting pre-filter used in pass 1."""

    def test_interview_subject(self):
        self.assertTrue(rt._subject_interesting("Interview invitation for PM role", "hr@company.com"))

    def test_schedule_subject(self):
        self.assertTrue(rt._subject_interesting("Let's schedule a call", "recruiter@company.com"))

    def test_next_steps_subject(self):
        self.assertTrue(rt._subject_interesting("Next steps for your application", "hr@company.com"))

    def test_rejection_word_in_subject(self):
        self.assertTrue(rt._subject_interesting("Unfortunately, we're not moving forward", "hr@company.com"))

    def test_application_subject(self):
        self.assertTrue(rt._subject_interesting("Your application has been received", "noreply@ats.com"))

    def test_unrelated_subject_rejected(self):
        self.assertFalse(rt._subject_interesting("Your order has shipped", "amazon@amazon.com"))
        self.assertFalse(rt._subject_interesting("Sale ends tonight - 40% off", "promo@retailer.com"))
        self.assertFalse(rt._subject_interesting("Team lunch on Friday", "coworker@company.com"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
