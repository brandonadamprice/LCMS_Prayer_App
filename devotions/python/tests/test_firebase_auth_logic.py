"""Tests for firebase_auth_logic (pure, stdlib-only -- see CLAUDE.md)."""

import unittest

import firebase_auth_logic


def google_claims(**overrides):
  """Decoded-token claims as produced by a Google sign-in through Firebase."""
  claims = {
      "uid": "fb-uid-123",
      "sub": "fb-uid-123",
      "email": "Pray.Always@Example.com",
      "email_verified": True,
      "name": "Martin Luther",
      "picture": "https://example.com/pic.jpg",
      "firebase": {
          "sign_in_provider": "google.com",
          "identities": {
              "google.com": ["google-sub-456"],
              "email": ["pray.always@example.com"],
          },
      },
  }
  claims.update(overrides)
  return claims


def password_claims(**overrides):
  """Decoded-token claims as produced by an email/password Firebase user."""
  claims = {
      "uid": "fb-uid-789",
      "sub": "fb-uid-789",
      "email": "simple@example.com",
      "email_verified": False,
      "firebase": {
          "sign_in_provider": "password",
          "identities": {"email": ["simple@example.com"]},
      },
  }
  claims.update(overrides)
  return claims


def apple_claims(**overrides):
  """Decoded-token claims as produced by Sign in with Apple through Firebase.

  Defaults model the common case: hide-my-email relay address, verified
  (Firebase asserts Apple emails verified), and NO name claim -- Apple only
  shares the name on the very first authorization, and even that first
  token routinely lacks it.
  """
  claims = {
      "uid": "fb-uid-apple-1",
      "sub": "fb-uid-apple-1",
      "email": "k3jd92xq7f@privaterelay.appleid.com",
      "email_verified": True,
      "firebase": {
          "sign_in_provider": "apple.com",
          "identities": {
              "apple.com": ["001234.abcdef1234567890.1234"],
              "email": ["k3jd92xq7f@privaterelay.appleid.com"],
          },
      },
  }
  claims.update(overrides)
  return claims


class ExtractIdentityTest(unittest.TestCase):

  def test_google_sign_in(self):
    identity = firebase_auth_logic.extract_identity(google_claims())
    self.assertEqual(identity.firebase_uid, "fb-uid-123")
    self.assertEqual(identity.provider, "google.com")
    self.assertEqual(identity.google_sub, "google-sub-456")
    self.assertEqual(identity.name, "Martin Luther")
    self.assertEqual(identity.picture, "https://example.com/pic.jpg")
    self.assertTrue(identity.email_verified)

  def test_email_is_normalized_to_lowercase(self):
    identity = firebase_auth_logic.extract_identity(google_claims())
    self.assertEqual(identity.email, "pray.always@example.com")

  def test_password_sign_in_has_no_google_sub(self):
    identity = firebase_auth_logic.extract_identity(password_claims())
    self.assertEqual(identity.provider, "password")
    self.assertIsNone(identity.google_sub)
    self.assertFalse(identity.email_verified)

  def test_falls_back_to_sub_when_uid_missing(self):
    claims = google_claims()
    del claims["uid"]
    identity = firebase_auth_logic.extract_identity(claims)
    self.assertEqual(identity.firebase_uid, "fb-uid-123")

  def test_rejects_claims_without_uid_or_sub(self):
    claims = google_claims()
    del claims["uid"]
    del claims["sub"]
    self.assertIsNone(firebase_auth_logic.extract_identity(claims))

  def test_rejects_non_dict_claims(self):
    self.assertIsNone(firebase_auth_logic.extract_identity(None))
    self.assertIsNone(firebase_auth_logic.extract_identity("token"))

  def test_tolerates_missing_optional_fields(self):
    identity = firebase_auth_logic.extract_identity({"uid": "fb-uid-1"})
    self.assertEqual(identity.firebase_uid, "fb-uid-1")
    self.assertIsNone(identity.email)
    self.assertIsNone(identity.google_sub)
    self.assertIsNone(identity.provider)
    self.assertFalse(identity.email_verified)

  def test_blank_email_becomes_none(self):
    identity = firebase_auth_logic.extract_identity(
        {"uid": "fb-uid-1", "email": "   "}
    )
    self.assertIsNone(identity.email)


class ResolveLoginTest(unittest.TestCase):

  def setUp(self):
    self.identity = firebase_auth_logic.extract_identity(google_claims())

  def test_firebase_uid_match_wins_over_everything(self):
    action, doc_id = firebase_auth_logic.resolve_login(
        self.identity,
        uid_match_id="doc-by-uid",
        google_match_id="doc-by-google",
        email_match_id="doc-by-email",
    )
    self.assertEqual(action, firebase_auth_logic.LOGIN)
    self.assertEqual(doc_id, "doc-by-uid")

  def test_google_match_links_legacy_oauth_account(self):
    action, doc_id = firebase_auth_logic.resolve_login(
        self.identity,
        google_match_id="doc-by-google",
        email_match_id="doc-by-email",
    )
    self.assertEqual(action, firebase_auth_logic.LINK)
    self.assertEqual(doc_id, "doc-by-google")

  def test_verified_email_match_links_legacy_email_account(self):
    action, doc_id = firebase_auth_logic.resolve_login(
        self.identity, email_match_id="doc-by-email"
    )
    self.assertEqual(action, firebase_auth_logic.LINK)
    self.assertEqual(doc_id, "doc-by-email")

  def test_unverified_email_match_is_rejected_not_linked(self):
    # Account-takeover guard: an attacker who creates an unverified Firebase
    # user with a victim's email must NOT be linked to the victim's account.
    identity = firebase_auth_logic.extract_identity(password_claims())
    action, doc_id = firebase_auth_logic.resolve_login(
        identity, email_match_id="victims-doc"
    )
    self.assertEqual(action, firebase_auth_logic.REJECT_UNVERIFIED_EMAIL)
    self.assertIsNone(doc_id)

  def test_no_match_creates_with_google_sub_as_doc_id(self):
    # Keeps the legacy convention: Google users are keyed by their Google sub.
    action, doc_id = firebase_auth_logic.resolve_login(self.identity)
    self.assertEqual(action, firebase_auth_logic.CREATE)
    self.assertEqual(doc_id, "google-sub-456")

  def test_no_match_creates_with_firebase_uid_for_non_google(self):
    identity = firebase_auth_logic.extract_identity(
        password_claims(email_verified=True)
    )
    action, doc_id = firebase_auth_logic.resolve_login(identity)
    self.assertEqual(action, firebase_auth_logic.CREATE)
    self.assertEqual(doc_id, "fb-uid-789")

  def test_unverified_email_with_no_match_still_creates(self):
    # No existing account to take over, so a new one is fine.
    identity = firebase_auth_logic.extract_identity(password_claims())
    action, _ = firebase_auth_logic.resolve_login(identity)
    self.assertEqual(action, firebase_auth_logic.CREATE)


class NeedsEmailVerificationTest(unittest.TestCase):

  def test_unverified_password_sign_in_is_blocked(self):
    identity = firebase_auth_logic.extract_identity(password_claims())
    self.assertTrue(firebase_auth_logic.needs_email_verification(identity))

  def test_verified_password_sign_in_passes(self):
    identity = firebase_auth_logic.extract_identity(
        password_claims(email_verified=True)
    )
    self.assertFalse(firebase_auth_logic.needs_email_verification(identity))

  def test_google_sign_in_is_never_blocked(self):
    identity = firebase_auth_logic.extract_identity(google_claims())
    self.assertFalse(firebase_auth_logic.needs_email_verification(identity))
    # Even a (hypothetical) unverified Google token isn't this gate's job;
    # the unverified-email-collision rule in resolve_login covers it.
    identity = firebase_auth_logic.extract_identity(
        google_claims(email_verified=False)
    )
    self.assertFalse(firebase_auth_logic.needs_email_verification(identity))


class BuildLinkDataTest(unittest.TestCase):

  def test_google_identity_links_google_fields_too(self):
    identity = firebase_auth_logic.extract_identity(google_claims())
    data = firebase_auth_logic.build_link_data(identity)
    self.assertEqual(
        data,
        {
            "firebase_uid": "fb-uid-123",
            "google_id": "google-sub-456",
            "google_profile_pic": "https://example.com/pic.jpg",
        },
    )

  def test_never_touches_existing_profile_fields(self):
    # Linking must not overwrite a legacy account's name/email/profile_pic.
    identity = firebase_auth_logic.extract_identity(google_claims())
    data = firebase_auth_logic.build_link_data(identity)
    self.assertNotIn("name", data)
    self.assertNotIn("email", data)
    self.assertNotIn("profile_pic", data)

  def test_password_identity_links_only_firebase_uid(self):
    identity = firebase_auth_logic.extract_identity(password_claims())
    data = firebase_auth_logic.build_link_data(identity)
    self.assertEqual(data, {"firebase_uid": "fb-uid-789"})


class BuildNewUserDataTest(unittest.TestCase):

  def test_google_identity(self):
    identity = firebase_auth_logic.extract_identity(google_claims())
    data = firebase_auth_logic.build_new_user_data(identity)
    self.assertEqual(
        data,
        {
            "firebase_uid": "fb-uid-123",
            "email": "pray.always@example.com",
            "name": "Martin Luther",
            "profile_pic": "https://example.com/pic.jpg",
            "google_id": "google-sub-456",
            "google_profile_pic": "https://example.com/pic.jpg",
        },
    )

  def test_omits_missing_fields_instead_of_writing_none(self):
    identity = firebase_auth_logic.extract_identity(password_claims())
    data = firebase_auth_logic.build_new_user_data(identity)
    self.assertEqual(
        data,
        {"firebase_uid": "fb-uid-789", "email": "simple@example.com"},
    )


class AppleSignInTest(unittest.TestCase):
  """Sign in with Apple flows through the shared logic; these tests pin the
  Apple-specific behaviors: verified relay emails, absent name claims, and
  the fallback display names."""

  def test_extract_identity_apple_provider(self):
    identity = firebase_auth_logic.extract_identity(apple_claims())
    self.assertEqual(identity.provider, "apple.com")
    self.assertEqual(identity.email, "k3jd92xq7f@privaterelay.appleid.com")
    self.assertTrue(identity.email_verified)
    self.assertIsNone(identity.name)
    self.assertIsNone(identity.google_sub)
    self.assertEqual(identity.apple_sub, "001234.abcdef1234567890.1234")

  def test_apple_sign_in_is_never_blocked_on_verification(self):
    identity = firebase_auth_logic.extract_identity(apple_claims())
    self.assertFalse(firebase_auth_logic.needs_email_verification(identity))

  def test_relay_email_matches_nothing_and_creates_fresh_account(self):
    identity = firebase_auth_logic.extract_identity(apple_claims())
    action, doc_id = firebase_auth_logic.resolve_login(identity)
    self.assertEqual(action, firebase_auth_logic.CREATE)
    self.assertEqual(doc_id, "fb-uid-apple-1")

  def test_shared_real_email_links_legacy_account(self):
    identity = firebase_auth_logic.extract_identity(
        apple_claims(email="pray.always@example.com")
    )
    action, doc_id = firebase_auth_logic.resolve_login(
        identity, email_match_id="legacy-doc-1"
    )
    self.assertEqual(action, firebase_auth_logic.LINK)
    self.assertEqual(doc_id, "legacy-doc-1")

  def test_link_data_carries_the_apple_sub(self):
    identity = firebase_auth_logic.extract_identity(apple_claims())
    self.assertEqual(
        firebase_auth_logic.build_link_data(identity),
        {
            "firebase_uid": "fb-uid-apple-1",
            "apple_id": "001234.abcdef1234567890.1234",
        },
    )

  def test_apple_id_match_links_even_with_relay_email(self):
    # The stored apple_id is how a hide-my-email sign-in finds an account
    # that was linked to Apple from settings: the relay email matches
    # nothing, but the Apple "sub" does.
    identity = firebase_auth_logic.extract_identity(apple_claims())
    action, doc_id = firebase_auth_logic.resolve_login(
        identity, apple_match_id="linked-doc-1"
    )
    self.assertEqual(action, firebase_auth_logic.LINK)
    self.assertEqual(doc_id, "linked-doc-1")

  def test_apple_match_wins_over_email_match(self):
    identity = firebase_auth_logic.extract_identity(
        apple_claims(email="pray.always@example.com")
    )
    action, doc_id = firebase_auth_logic.resolve_login(
        identity, apple_match_id="apple-doc", email_match_id="email-doc"
    )
    self.assertEqual(action, firebase_auth_logic.LINK)
    self.assertEqual(doc_id, "apple-doc")

  def test_new_user_doc_stores_the_apple_sub(self):
    identity = firebase_auth_logic.extract_identity(apple_claims())
    data = firebase_auth_logic.build_new_user_data(identity)
    self.assertEqual(data["apple_id"], "001234.abcdef1234567890.1234")

  def test_new_user_with_relay_email_gets_generic_name(self):
    identity = firebase_auth_logic.extract_identity(apple_claims())
    data = firebase_auth_logic.build_new_user_data(identity)
    self.assertEqual(data["name"], "Friend")
    self.assertEqual(data["email"], "k3jd92xq7f@privaterelay.appleid.com")

  def test_new_user_with_real_email_gets_local_part_name(self):
    identity = firebase_auth_logic.extract_identity(
        apple_claims(email="katie.luther@example.com")
    )
    data = firebase_auth_logic.build_new_user_data(identity)
    self.assertEqual(data["name"], "katie.luther")

  def test_new_user_keeps_name_when_apple_provides_one(self):
    identity = firebase_auth_logic.extract_identity(
        apple_claims(name="Katharina von Bora")
    )
    data = firebase_auth_logic.build_new_user_data(identity)
    self.assertEqual(data["name"], "Katharina von Bora")

  def test_name_fallback_is_apple_only(self):
    # The password flow's omit-missing-fields behavior is pinned by
    # BuildNewUserDataTest; this guards the provider scoping directly.
    identity = firebase_auth_logic.extract_identity(password_claims())
    data = firebase_auth_logic.build_new_user_data(identity)
    self.assertNotIn("name", data)


if __name__ == "__main__":
  unittest.main()
