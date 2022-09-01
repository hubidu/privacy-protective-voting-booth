import email
import re

from typing import List


def redact_free_text(free_text: str, overlap_names: List[str]) -> str:
    """
    :param: free_text The free text to remove sensitive data from
    :returns: The redacted free text
    """
    email_regex = r"\b\S+@\S+.\S+\b"
    phone_regex = r"\(?\d{3}\)?\-? ?\d{3}\-?\d{4}"
    national_identifier_regex = r"\d{3}[\- ]?\d{2}[\- ]?\d{4}"

    redacted_text = free_text
    redacted_text = re.sub(email_regex, '[REDACTED EMAIL]', redacted_text)
    redacted_text = re.sub(
        phone_regex, '[REDACTED PHONE NUMBER]', redacted_text)
    redacted_text = re.sub(
        national_identifier_regex, '[REDACTED NATIONAL ID]', redacted_text)

    for name in overlap_names:
        redacted_text = redacted_text.replace(name, '[REDACTED NAME]')

    return redacted_text
