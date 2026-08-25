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

Sign in with Apple (provider "apple.com") flows through the same precedence
untouched: Firebase asserts Apple emails verified, so a user who shares
their real address links to their legacy account (step 3), while a hidden
address (@privaterelay.appleid.com) matches nothing and creates a fresh
account -- the relay address is unknowable in advance, so that is the only
correct outcome. Two Apple quirks ARE handled here: the name claim is
routinely absent (Apple shares the name only on the very first
authorization, and the token minted right then may already lack it), and a
relay address's local part is an opaque random string, so
build_new_user_data falls back accordingly.
"""

import dataclasses

# Apple's hide-my-email relay domain; its local parts are opaque random
# strings, useless as display names.
APPLE_RELAY_SUFFIX = "@privaterelay.appleid.com"

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
  apple_sub: str = None


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
  apple_subs = identities.get("apple.com") or []
  apple_sub = str(apple_subs[0]) if apple_subs else None

  email = (claims.get("email") or "").strip().lower() or None

  return FirebaseIdentity(
      firebase_uid=uid,
      provider=firebase_info.get("sign_in_provider"),
      email=email,
      email_verified=bool(claims.get("email_verified")),
      name=claims.get("name"),
      picture=claims.get("picture"),
      google_sub=google_sub,
      apple_sub=apple_sub,
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
    identity,
    uid_match_id=None,
    google_match_id=None,
    apple_match_id=None,
    email_match_id=None,
):
  """Decides how a Firebase sign-in maps onto existing user documents.

  Args:
    identity: FirebaseIdentity from extract_identity.
    uid_match_id: doc ID of the user whose firebase_uid matches, if any.
    google_match_id: doc ID of the user whose google_id matches, if any.
    apple_match_id: doc ID of the user whose apple_id matches, if any --
      set when the account was explicitly linked to Apple (settings) or a
      prior Apple sign-in stored the Apple "sub". Lets a hide-my-email
      Apple sign-in find its account even when the relay email and the
      current firebase_uid both fail to match.
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
  if apple_match_id:
    return LINK, apple_match_id
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
  if identity.apple_sub:
    data["apple_id"] = identity.apple_sub
  return data


def apple_fallback_name(email):
  """Display name for an Apple sign-in whose token carries no name claim.

  The email's local part is a reasonable default for a shared real address,
  but a private-relay address's local part is random noise, so those get a
  friendly generic instead.
  """
  if email and not email.endswith(APPLE_RELAY_SUFFIX):
    return email.split("@")[0]
  return "Friend"


def build_new_user_data(identity):
  """Fields for a brand-new user document (mirrors the legacy OAuth shape).

  Missing fields are omitted rather than written as None -- except the name
  of an Apple sign-in, which is routinely absent (see module docstring) and
  would otherwise render as a blank profile; those get apple_fallback_name.
  """
  data = {
      "firebase_uid": identity.firebase_uid,
      "email": identity.email,
      "name": identity.name,
      "profile_pic": identity.picture,
  }
  if identity.provider == "apple.com" and not data["name"]:
    data["name"] = apple_fallback_name(identity.email)
  if identity.google_sub:
    data["google_id"] = identity.google_sub
    data["google_profile_pic"] = identity.picture
  if identity.apple_sub:
    data["apple_id"] = identity.apple_sub
  return {k: v for k, v in data.items() if v is not None}
