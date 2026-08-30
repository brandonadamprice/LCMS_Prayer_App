"""Pure validation logic for prayer-wall reports and account deletion.

Dependency-free (stdlib only) so it stays unit-testable without Firestore,
following the streak_logic.py / rate_limit_logic.py pattern.
"""

# Firestore auto-ids are 20 chars; leave generous headroom while still
# rejecting obviously bogus payloads.
REQUEST_ID_MAX_LENGTH = 128
REASON_MAX_LENGTH = 500

# The exact text the danger-zone dialog asks the user to type. Compared
# case-sensitively: the friction is the point.
DELETION_CONFIRMATION_TEXT = "DELETE"


def normalize_reason(raw):
  """Normalizes a free-text report reason.

  Accepts None (reason is optional), strips surrounding whitespace, and
  truncates to REASON_MAX_LENGTH. Always returns a str.
  """
  if not isinstance(raw, str):
    return ""
  return raw.strip()[:REASON_MAX_LENGTH]


def validate_report(request_id, reason):
  """Validates a report payload.

  Args:
    request_id: the prayer-request document id being reported.
    reason: an already-normalized reason string (see normalize_reason).

  Returns:
    tuple[bool, str | None]: (True, None) if valid, else (False, error).
  """
  if not isinstance(request_id, str) or not request_id.strip():
    return False, "Missing request id."
  if len(request_id) > REQUEST_ID_MAX_LENGTH:
    return False, "Invalid request id."
  if not isinstance(reason, str) or len(reason) > REASON_MAX_LENGTH:
    return False, "Reason is too long."
  return True, None


def deletion_confirmed(confirm_text):
  """True when the typed confirmation matches exactly (whitespace ignored)."""
  if not isinstance(confirm_text, str):
    return False
  return confirm_text.strip() == DELETION_CONFIRMATION_TEXT
