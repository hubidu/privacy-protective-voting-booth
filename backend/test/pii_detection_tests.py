import backend.main.detection.pii_detection as pii_detection


class TestPIIDetection:
    def test_phonenumber_nationalid_and_email_redaction(self):
        text = """
I (Alex) am so proud to be voting for the first time ever! If there are any problems with my vote please reach out to me at
(345) 553-2335. I'm also available over email at sjenkins@email.co.atlantis.

Best,

Sara Jenkins
ID: 234-23-2342
		"""

        redacted_text = pii_detection.redact_free_text(text, ['Alex'])

        assert "ID: [REDACTED NATIONAL ID]" in redacted_text
        assert "[REDACTED PHONE NUMBER]" in redacted_text
        assert "[REDACTED EMAIL]" in redacted_text
        assert "[REDACTED NAME]" in redacted_text
