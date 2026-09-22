"""Input and output guardrails for the chat CLI. Both are simple regex
pattern matching -- no model call -- so they're fast and their behavior
is fully explainable by reading the pattern list."""

import re

# --- Input guardrail: block common direct prompt injection / jailbreak phrasing ---

_INJECTION_PATTERNS = [
    ("ignore_instructions", r"ignore\s+(all\s+|your\s+)?(previous|prior|above)\s+instructions"),
    ("disregard_rules", r"disregard\s+(your|all|previous)\s+(rules|instructions)"),
    ("you_are_now", r"\byou\s+are\s+now\b"),
    ("pretend_role", r"pretend\s+(that\s+)?you\s+(are|have)\b"),
    ("act_as", r"\bact\s+as\s+(if|though)\b"),
    ("new_instructions", r"new\s+instructions\s*:"),
    ("reveal_system_prompt", r"(reveal|show|print|repeat)\s+your\s+(system\s+)?prompt"),
    ("developer_mode", r"developer\s+mode"),
    ("admin_access", r"admin\s+(access|mode|privileges)"),
    ("bypass_restrictions", r"bypass\s+(your\s+|the\s+)?(restrictions|filters?|rules)"),
    ("jailbreak", r"\bjailbreak\b"),
    ("dan_mode", r"\bDAN\s+mode\b"),
    ("override_instructions", r"override\s+(your\s+)?(instructions|programming|rules)"),
]

INJECTION_PATTERNS = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in _INJECTION_PATTERNS]

BLOCKED_RESPONSE = (
    "I can't process that request. Please ask a direct question about the "
    "company documents I have access to."
)


def check_input(message):
    """Return the name of the first injection pattern matched in `message`,
    or None if it looks clean. Pure regex -- no model call."""
    for name, pattern in INJECTION_PATTERNS:
        if pattern.search(message):
            return name
    return None


# --- Output guardrail: redact PII from the final answer before it's shown ---

ALLOWED_EMAIL_DOMAIN = "solsticeanalytics.com"

_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_PATTERN = re.compile(
    r"(?<!\d)(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)"
)
_SSN_PATTERN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")

PII_PATTERNS = [
    ("email", _EMAIL_PATTERN),
    ("phone", _PHONE_PATTERN),
    ("ssn", _SSN_PATTERN),
]


def _is_allowed_email(value):
    return value.lower().endswith("@" + ALLOWED_EMAIL_DOMAIN)


def redact_output(text):
    """Scan `text` for PII and replace matches with a placeholder. Emails
    on ALLOWED_EMAIL_DOMAIN are left untouched (legitimate company contact
    addresses, not leaks). Returns (redacted_text, findings) where findings
    is a list of {type, value} for everything actually redacted."""
    findings = []

    def replace_email(match):
        value = match.group(0)
        if _is_allowed_email(value):
            return value
        findings.append({"type": "email", "value": value})
        return "[REDACTED-EMAIL]"

    redacted = _EMAIL_PATTERN.sub(replace_email, text)

    def make_replacer(pii_type, placeholder):
        def replacer(match):
            findings.append({"type": pii_type, "value": match.group(0)})
            return placeholder
        return replacer

    redacted = _PHONE_PATTERN.sub(make_replacer("phone", "[REDACTED-PHONE]"), redacted)
    redacted = _SSN_PATTERN.sub(make_replacer("ssn", "[REDACTED-SSN]"), redacted)

    return redacted, findings


def redact_search_log(search_log):
    """Apply redact_output to every retrieved chunk's content in a
    search_log (the same structure ask.py prints to the console and
    writes to the debug trace) -- the output guardrail on the final
    answer alone doesn't cover chunk previews shown before the model
    even produces an answer. Returns (redacted_search_log, all_findings)."""
    redacted_log = []
    all_findings = []

    for entry in search_log:
        redacted_chunks = []
        for chunk in entry["chunks"]:
            redacted_content, findings = redact_output(chunk["content"])
            all_findings.extend(findings)
            redacted_chunks.append({**chunk, "content": redacted_content})
        redacted_log.append({"query": entry["query"], "chunks": redacted_chunks})

    return redacted_log, all_findings
