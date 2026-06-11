"""Pure analysis of stored password hashes for the Firebase Auth migration.

Like streak_logic.py and firebase_auth_logic.py, this module is
dependency-free (stdlib only) so it stays unit-testable. The Firestore side
is scripts/audit_password_hashes.py (read-only).

Context (docs/firebase-auth-migration.md, Phase 3a): existing email/password
users are to be batch-imported into Firebase Auth via importUsers so they
keep their passwords. Whether a stored werkzeug hash is batch-importable
depends on its scheme and parameters:

  - werkzeug scrypt ("scrypt:n:r:p$salt$hex") is standard scrypt
    (hashlib.scrypt, dkLen=64), which maps onto Firebase's STANDARD_SCRYPT.
  - werkzeug pbkdf2 ("pbkdf2:sha256:rounds$salt$hex") maps onto Firebase's
    PBKDF2_SHA256 -- but Firebase rejects rounds above 120000, and werkzeug's
    historical defaults (150k/260k/600k/1M depending on version) almost all
    exceed it. Those accounts need the lazy-migration fallback instead
    (verify against the legacy hash once, then create the Firebase user).

The audit classifies every account so Phase 3a knows the split up front.
"""

import dataclasses

# Firebase Admin SDK importUsers validation limit for PBKDF2 rounds.
FIREBASE_PBKDF2_MAX_ROUNDS = 120000

SCHEME_SCRYPT = "scrypt"
SCHEME_PBKDF2_SHA256 = "pbkdf2:sha256"
SCHEME_UNKNOWN = "unknown"

# Account categories for classify_account.
ACCOUNT_FIREBASE_LINKED = "firebase_linked"
ACCOUNT_PASSWORD_ONLY = "password_only"
ACCOUNT_GOOGLE_ONLY = "google_only"
ACCOUNT_PASSWORD_AND_GOOGLE = "password_and_google"
ACCOUNT_NO_CREDENTIALS = "no_credentials"  # Anomaly: can never log in.


@dataclasses.dataclass
class HashInfo:
  """Classification of one stored password hash."""

  scheme: str
  params: tuple = ()  # (n, r, p) for scrypt; (rounds,) for pbkdf2.
  importable: bool = False
  reason: str = ""

  @property
  def bucket(self):
    """Stable aggregation key, e.g. "scrypt:32768:8:1 [importable]"."""
    label = self.scheme
    if self.params:
      label += ":" + ":".join(str(p) for p in self.params)
    suffix = "importable" if self.importable else f"NOT importable: {self.reason}"
    return f"{label} [{suffix}]"


def classify_hash(hash_string):
  """Classifies a werkzeug-style password hash string.

  werkzeug format: "<method>$<salt>$<hexdigest>" where method is e.g.
  "scrypt:32768:8:1" or "pbkdf2:sha256:600000".
  """
  if not hash_string or not isinstance(hash_string, str):
    return HashInfo(SCHEME_UNKNOWN, reason="empty or non-string hash")

  parts = hash_string.split("$")
  if len(parts) != 3 or not parts[1] or not parts[2]:
    return HashInfo(SCHEME_UNKNOWN, reason="not in werkzeug method$salt$hash form")
  method = parts[0]

  if method.startswith("scrypt:"):
    try:
      n, r, p = (int(x) for x in method.split(":")[1:4])
    except (ValueError, IndexError):
      return HashInfo(SCHEME_SCRYPT, reason="unparseable scrypt parameters")
    return HashInfo(
        SCHEME_SCRYPT,
        params=(n, r, p),
        importable=True,
        reason="maps to Firebase STANDARD_SCRYPT",
    )

  if method.startswith("pbkdf2:sha256"):
    rest = method[len("pbkdf2:sha256"):]
    if not rest:
      # Very old werkzeug wrote no rounds count; the value it used is not
      # recoverable from the hash, so batch import cannot set it.
      return HashInfo(
          SCHEME_PBKDF2_SHA256, reason="no rounds recorded in hash"
      )
    try:
      rounds = int(rest[1:])  # rest is like ":600000"
    except ValueError:
      return HashInfo(
          SCHEME_PBKDF2_SHA256, reason="unparseable rounds in hash"
      )
    if rounds > FIREBASE_PBKDF2_MAX_ROUNDS:
      return HashInfo(
          SCHEME_PBKDF2_SHA256,
          params=(rounds,),
          reason=(
              f"rounds {rounds} exceed Firebase max"
              f" {FIREBASE_PBKDF2_MAX_ROUNDS}; needs lazy migration"
          ),
      )
    return HashInfo(
        SCHEME_PBKDF2_SHA256,
        params=(rounds,),
        importable=True,
        reason="maps to Firebase PBKDF2_SHA256",
    )

  return HashInfo(SCHEME_UNKNOWN, reason=f"unrecognized method {method!r}")


def classify_account(doc_fields):
  """Buckets a user doc by its sign-in credentials.

  Args:
    doc_fields: dict with (at least) the optional keys password_hash,
      google_id, firebase_uid.

  Returns one of the ACCOUNT_* constants. firebase_linked wins outright:
  those users already sign in through the bridge regardless of legacy
  credentials.
  """
  if doc_fields.get("firebase_uid"):
    return ACCOUNT_FIREBASE_LINKED
  has_password = bool(doc_fields.get("password_hash"))
  has_google = bool(doc_fields.get("google_id"))
  if has_password and has_google:
    return ACCOUNT_PASSWORD_AND_GOOGLE
  if has_password:
    return ACCOUNT_PASSWORD_ONLY
  if has_google:
    return ACCOUNT_GOOGLE_ONLY
  return ACCOUNT_NO_CREDENTIALS
