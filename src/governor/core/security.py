"""Input guard for a reviewer's own note.

Screen only the text a person typed (a reject note, a corrected
summary, or a correction reason). Never screen tool results or retrieved
passages: a runbook that mentions these phrases is not an attack. Never
raise from a guard.

The patterns are narrow on purpose. A false positive refuses a real note
before the investigation resumes. Refusal text is fixed. It never includes
the reviewer's words.
"""

from __future__ import annotations

import re

# Bounds are on the text as submitted. A short message cannot describe a
# workload; a very long one is where pasted jailbreaks hide. An answer to a
# clarifying question can be short ("EU, small"), so it has its own floor.
MIN_INPUT_CHARS = 15
MIN_ANSWER_CHARS = 2
MAX_INPUT_CHARS = 3000

MSG_TOO_SHORT = (
    "Please write the note in a full sentence so it can be saved with the incident."
)
MSG_TOO_LONG = (
    "That note is too long. Please summarise it in a few paragraphs."
)
MSG_NO_LETTERS = "Please write the note in words."
MSG_INJECTION = (
    "I can only record a note about this dbt incident. "
    "Please describe the correction in plain language."
)
MSG_OUT_OF_SCOPE = (
    "I can only help with this failed dbt run. "
    "Please describe what the investigation should change."
)

# Phrase patterns, case-insensitive. Each name is what regex_screen returns.
# The matched text stays here: a caller that logged it would echo the user.
#
# "ignore" alone is normal ("ignore multi-region for now"). The pattern
# needs "instructions". "system" alone is normal. It has to be "system prompt".
_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"ignore\s+(?:all\s+)?(?:previous\s+|prior\s+)?instructions",
            re.IGNORECASE,
        ),
        "ignore_instructions",
    ),
    (
        re.compile(
            r"disregard\s+(?:all\s+|any\s+|the\s+|your\s+|previous\s+)*(?:instructions|rules|prompt)",
            re.IGNORECASE,
        ),
        "disregard_instructions",
    ),
    (
        re.compile(
            r"forget\s+(?:all\s+|your\s+|the\s+|previous\s+)*(?:instructions|rules|prompt)",
            re.IGNORECASE,
        ),
        "forget_instructions",
    ),
    (
        # The trailing \b matters: "the booking system prompts customers to
        # pay" is a normal sentence about the user's own system.
        re.compile(r"system\s+prompt\b", re.IGNORECASE),
        "system_prompt",
    ),
    (
        re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
        "you_are_now",
    ),
    (
        re.compile(r"developer\s+mode", re.IGNORECASE),
        "developer_mode",
    ),
    (
        re.compile(r"<\|(?:system|user|assistant|developer)\|>", re.IGNORECASE),
        "role_tag",
    ),
    (
        re.compile(r"#{3,}\s*system\b", re.IGNORECASE),
        "markdown_system",
    ),
    (
        # A contiguous base64-alphabet run. Ordinary sentences have spaces,
        # so they do not reach 200 characters inside this class.
        re.compile(r"[A-Za-z0-9+/]{200,}={0,2}"),
        "base64_run",
    ),
    (
        re.compile(
            r"(?:print|reveal|show|repeat)\s+your\s+(?:hidden\s+|system\s+)?(?:instructions|prompt)",
            re.IGNORECASE,
        ),
        "print_instructions",
    ),
    (
        # Only "act as" addressed to the assistant: at the start of a
        # sentence, or after "you" / "please". "We need Redis to act as a
        # cache" is architecture language and must pass.
        re.compile(
            r"(?:^|[.!?]\s+|\b(?:you|please)\s+)act\s+as\b",
            re.IGNORECASE | re.MULTILINE,
        ),
        "act_as",
    ),
    (
        re.compile(r"\bpretend\s+(?:to\s+be|you\s+are)\b", re.IGNORECASE),
        "pretend",
    ),
    (
        re.compile(r"\bjailbreak\b", re.IGNORECASE),
        "jailbreak",
    ),
]


def validate_input(text: str, min_chars: int = MIN_INPUT_CHARS) -> tuple[bool, str]:
    """Length min_chars–3000 and at least one letter. Never raises.

    min_chars is 15 for the problem description and MIN_ANSWER_CHARS for a
    follow-up answer. The message is a fixed refusal. It does not quote text.
    """
    try:
        if not isinstance(text, str):
            return False, MSG_NO_LETTERS
        if len(text.strip()) < min_chars:
            return False, MSG_TOO_SHORT
        if len(text) > MAX_INPUT_CHARS:
            return False, MSG_TOO_LONG
        if not any(char.isalpha() for char in text):
            return False, MSG_NO_LETTERS
    except Exception:
        return False, MSG_TOO_SHORT
    return True, ""


def regex_screen(text: str) -> tuple[bool, list[str]]:
    """Return (flagged, rule names). Never raises.

    A failure inside the screen flags the text. Letting it through because
    the screen crashed would skip the cheap layer.
    """
    try:
        if not isinstance(text, str):
            return True, ["screen_error"]
        matched = [name for pattern, name in _PATTERNS if pattern.search(text)]
        return bool(matched), matched
    except Exception:
        return True, ["screen_error"]
