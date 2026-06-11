"""Tests for password_hash_logic (pure, stdlib-only -- see CLAUDE.md).

The well-formed fixture strings below were generated with the pinned
werkzeug version (3.1.8) via generate_password_hash, so the parser is tested
against real output, not a guessed format.
"""

import unittest

import password_hash_logic

# generate_password_hash('TestPassword1!')  -- werkzeug 3.x default
SCRYPT_HASH = (
    "scrypt:32768:8:1$dLZLT2tLjCXf3Cl6$592e422dd1bc1209691aca6128b59d8db5c9"
    "24d84572f9ddb5a55b9474b628074dff7d1cdfe32fc738b102691670beacf021b34154"
    "470ac51a5d6014ca74b4bd"
)
# generate_password_hash(..., method='pbkdf2:sha256') -- 3.x default rounds
PBKDF2_1M_HASH = (
    "pbkdf2:sha256:1000000$HDQaRApEvwU88B4W$d4f5c38f928713e421d1f65dbae163c"
    "438fc7685329dcd3be84d838d643cd4c3"
)
# generate_password_hash(..., method='pbkdf2:sha256:50000')
PBKDF2_50K_HASH = (
    "pbkdf2:sha256:50000$tPIVQbiqVQ9mZRMH$ad8c41ed0dd93f3c83e28ff897889581"
    "0c84ac8acb716f9ea044aab5ff654a9c"
)


class ClassifyHashTest(unittest.TestCase):

  def test_scrypt_default_is_importable(self):
    info = password_hash_logic.classify_hash(SCRYPT_HASH)
    self.assertEqual(info.scheme, password_hash_logic.SCHEME_SCRYPT)
    self.assertEqual(info.params, (32768, 8, 1))
    self.assertTrue(info.importable)

  def test_pbkdf2_above_firebase_round_cap_is_not_importable(self):
    info = password_hash_logic.classify_hash(PBKDF2_1M_HASH)
    self.assertEqual(info.scheme, password_hash_logic.SCHEME_PBKDF2_SHA256)
    self.assertEqual(info.params, (1000000,))
    self.assertFalse(info.importable)
    self.assertIn("exceed", info.reason)

  def test_pbkdf2_within_round_cap_is_importable(self):
    info = password_hash_logic.classify_hash(PBKDF2_50K_HASH)
    self.assertEqual(info.params, (50000,))
    self.assertTrue(info.importable)

  def test_pbkdf2_at_exact_cap_is_importable(self):
    cap = password_hash_logic.FIREBASE_PBKDF2_MAX_ROUNDS
    info = password_hash_logic.classify_hash(
        f"pbkdf2:sha256:{cap}$somesalt$abcdef0123456789"
    )
    self.assertTrue(info.importable)
    info = password_hash_logic.classify_hash(
        f"pbkdf2:sha256:{cap + 1}$somesalt$abcdef0123456789"
    )
    self.assertFalse(info.importable)

  def test_pbkdf2_without_rounds_is_not_importable(self):
    # Ancient werkzeug omitted the rounds count; it cannot be recovered.
    info = password_hash_logic.classify_hash(
        "pbkdf2:sha256$somesalt$abcdef0123456789"
    )
    self.assertEqual(info.scheme, password_hash_logic.SCHEME_PBKDF2_SHA256)
    self.assertFalse(info.importable)

  def test_unrecognized_method(self):
    info = password_hash_logic.classify_hash("argon2id$salt$digest")
    self.assertEqual(info.scheme, password_hash_logic.SCHEME_UNKNOWN)
    self.assertFalse(info.importable)

  def test_malformed_inputs(self):
    for bad in (None, "", 42, "no-dollars-here", "a$b", "$$", "x$$y"):
      info = password_hash_logic.classify_hash(bad)
      self.assertFalse(info.importable, msg=repr(bad))

  def test_bad_scrypt_params(self):
    info = password_hash_logic.classify_hash("scrypt:abc:8:1$salt$digest")
    self.assertEqual(info.scheme, password_hash_logic.SCHEME_SCRYPT)
    self.assertFalse(info.importable)

  def test_bucket_label_is_stable_and_readable(self):
    info = password_hash_logic.classify_hash(SCRYPT_HASH)
    self.assertEqual(info.bucket, "scrypt:32768:8:1 [importable]")
    info = password_hash_logic.classify_hash(PBKDF2_1M_HASH)
    self.assertTrue(info.bucket.startswith("pbkdf2:sha256:1000000 [NOT importable"))


class ClassifyAccountTest(unittest.TestCase):

  def test_firebase_linked_wins_over_everything(self):
    self.assertEqual(
        password_hash_logic.classify_account({
            "firebase_uid": "fb-1",
            "password_hash": SCRYPT_HASH,
            "google_id": "g-1",
        }),
        password_hash_logic.ACCOUNT_FIREBASE_LINKED,
    )

  def test_password_only(self):
    self.assertEqual(
        password_hash_logic.classify_account({"password_hash": SCRYPT_HASH}),
        password_hash_logic.ACCOUNT_PASSWORD_ONLY,
    )

  def test_google_only(self):
    self.assertEqual(
        password_hash_logic.classify_account({"google_id": "g-1"}),
        password_hash_logic.ACCOUNT_GOOGLE_ONLY,
    )

  def test_password_and_google(self):
    self.assertEqual(
        password_hash_logic.classify_account(
            {"password_hash": SCRYPT_HASH, "google_id": "g-1"}
        ),
        password_hash_logic.ACCOUNT_PASSWORD_AND_GOOGLE,
    )

  def test_no_credentials_anomaly(self):
    self.assertEqual(
        password_hash_logic.classify_account({"email": "x@example.com"}),
        password_hash_logic.ACCOUNT_NO_CREDENTIALS,
    )
    # Empty-string values count as absent, not present.
    self.assertEqual(
        password_hash_logic.classify_account(
            {"password_hash": "", "google_id": None, "firebase_uid": ""}
        ),
        password_hash_logic.ACCOUNT_NO_CREDENTIALS,
    )


if __name__ == "__main__":
  unittest.main()
