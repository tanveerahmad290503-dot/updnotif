from django.test import TestCase

from django.test import SimpleTestCase

from gmail_sync.services import strip_quoted_content


class StripQuotedContentTests(SimpleTestCase):

    def test_removes_angle_bracket_quoted_lines(self):
        raw = "Hi there\n> previous message line\n> another old line\nThanks"
        cleaned = strip_quoted_content(raw)

        self.assertEqual(cleaned, "Hi there\nThanks")

    def test_cuts_common_on_wrote_marker(self):
        raw = (
            "Latest recruiter update\n\n"
            "On Tue, Jan 1, 2026 at 10:00 AM Recruiter <r@example.com> wrote:\n"
            "Older thread body"
        )

        cleaned = strip_quoted_content(raw)

        self.assertEqual(cleaned, "Latest recruiter update")