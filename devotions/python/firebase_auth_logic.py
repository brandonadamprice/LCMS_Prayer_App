"""Pure logic for mapping Firebase Authentication sign-ins to user docs.

Like streak_logic.py, this module is dependency-free (stdlib only; no
Flask/Firestore/firebase-admin imports) so it stays unit-testable.

Context: the app is adding Firebase Authentication as a session bridge
(/auth/firebase in main.py) alongside the legacy Google-OAuth and
email/password flows. Firebase issues its own uid, which is NOT the same as
either the Google OAuth "sub" (used as the doc ID for legacy Google users) or
the uuid4 doc IDs of legacy email users. Rather than re-keying documents, an
existing user doc gains a "firebase_uid" field the first time its owner signs
in through Firebase, and lookups go through that field.

Matching precedence (resolve_login):
  1. firebase_uid  -- user has signed in through Firebase before.
  2. google_id     -- legacy Google-OAuth account; the Google "sub" appears in
                      the token under firebase.identities["google.com"].
  3. verified email -- legacy email/password account. Linking by email is only
                      safe when Firebase asserts the email is verified;
                      otherwise anyone could claim an existing account by
                      creating an unverified Firebase user with that email.
"""

import dataclasses

# Actions returned by resolve_login.
LOGIN = "login"  # Existing Firebase-linked user; just refresh and sign in.
LINK = "link"  # Legacy account found; attach firebase_uid, then sign in.
CREATE = "create"  # No match; create a new user document.
REJECT_UNVERIFIED_EMAIL = "reject_unverified_email"  # Possible takeover.


@dataclasses.dataclass
class FirebaseIdentity:
  """The fields of a decoded Firebase ID token that the app cares about."""

  firebase_uid: str
  provider: str = None
  email: str = None
  email_verified: bool = False
  name: str = None
  picture: str = None
  google_sub: str = None


def extract_identity(claims):
  """Builds a FirebaseIdentity from decoded, already-verified token claims.

  Returns None if the claims do not carry a usable uid. Signature
  verification is the caller's job (firebase_admin.auth.verify_id_token);
  this only normalizes the shape.
  """
  if not isinstance(claims, dict):
    return None
  uid = claims.get("uid") or claims.get("sub")
  if not uid or not isinstance(uid, str):
    return None

  firebase_info = claims.get("firebase") or {}
  identities = firebase_info.get("identities") or {}
  google_subs = identities.get("google.com") or []
  google_sub = str(google_subs[0]) if google_subs else None

  email = (claims.get("email") or "").strip().lower() or None

  return FirebaseIdentity(
      firebase_uid=uid,
      provider=firebase_info.get("sign_in_provider"),
      email=email,
      email_verified=bool(claims.get("email_verified")),
      name=claims.get("name"),
      picture=claims.get("picture"),
      google_sub=google_sub,
  )


def needs_email_verification(identity):
  """True when a password-provider sign-in must be blocked until verified.

  Preserves the legacy guarantee that an email/password account does not
  exist (no session, no user doc) until its address is verified -- the old
  /register flow enforced this with a code email before creating the doc.
  Google sign-ins always carry verified emails, and batch-imported legacy
  users were imported with email_verified=True, so only fresh Firebase
  password registrations hit this.
  """
  return identity.provider == "password" and not identity.email_verified


def choose_doc_id(identity):
  """Picks the document ID for a brand-new user.

  Google-backed identities keep the legacy convention of using the Google
  "sub" as the doc ID, so a user who first appears via Firebase and later
  uses the legacy web OAuth flow resolves to the same document either way.
  """
  return identity.google_sub or identity.firebase_uid


def resolve_login(
    identity, uid_match_id=None, google_match_id=None, email_match_id=None
):
  """Decides how a Firebase sign-in maps onto existing user documents.

  Args:
    identity: FirebaseIdentity from extract_identity.
    uid_match_id: doc ID of the user whose firebase_uid matches, if any.
    google_match_id: doc ID of the user whose google_id matches, if any.
    email_match_id: doc ID of the user whose email matches, if any. Callers
      must pass this whenever the identity has an email -- even an unverified
      one -- so an unverified collision is rejected instead of silently
      creating a duplicate account.

  Returns:
    (action, doc_id) where action is one of LOGIN/LINK/CREATE/
    REJECT_UNVERIFIED_EMAIL. doc_id is None for the reject action.
  """
  if uid_match_id:
    return LOGIN, uid_match_id
  if google_match_id:
    return LINK, google_match_id
  if email_match_id:
    if identity.email_verified:
      return LINK, email_match_id
    return REJECT_UNVERIFIED_EMAIL, None
  return CREATE, choose_doc_id(identity)


def build_link_data(identity):
  """Fields to merge onto an existing user doc when linking/logging in.

  Deliberately minimal: never touches name, email, or profile_pic, so a
  legacy account keeps its own data and only gains the Firebase linkage
  (plus Google linkage when the sign-in came through Google, which keeps the
  legacy web OAuth flow working for that user as well).
  """
  data = {"firebase_uid": identity.firebase_uid}
  if identity.google_sub:
    data["google_id"] = identity.google_sub
    if identity.picture:
      data["google_profile_pic"] = identity.picture
  return data


def build_new_user_data(identity):
  """Fields for a brand-new user document (mirrors the legacy OAuth shape)."""
  data = {
      "firebase_uid": identity.firebase_uid,
      "email": identity.email,
      "name": identity.name,
      "profile_pic": identity.picture,
  }
  if identity.google_sub:
    data["google_id"] = identity.google_sub
    data["google_profile_pic"] = identity.picture
  return {k: v for k, v in data.items() if v is not None}
