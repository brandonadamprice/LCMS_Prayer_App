"""Tests for the pure prayer-wall report / account-deletion validation."""

import unittest

import report_logic


class NormalizeReasonTest(unittest.TestCase):

  def test_none_becomes_empty(self):
    self.assertEqual(report_logic.normalize_reason(None), "")

  def test_non_string_becomes_empty(self):
    self.assertEqual(report_logic.normalize_reason(42), "")
    self.assertEqual(report_logic.normalize_reason(["x"]), "")

  def test_strips_whitespace(self):
    self.assertEqual(report_logic.normalize_reason("  spam  \n"), "spam")

  def test_truncates_to_max(self):
    long = "a" * (report_logic.REASON_MAX_LENGTH + 100)
    self.assertEqual(
        len(report_logic.normalize_reason(long)), report_logic.REASON_MAX_LENGTH
    )

  def test_empty_reason_allowed(self):
    self.assertEqual(report_logic.normalize_reason(""), "")


class ValidateReportTest(unittest.TestCase):

  def test_valid(self):
    ok, error = report_logic.validate_report("abc123", "contains a phone number")
    self.assertTrue(ok)
    self.assertIsNone(error)

  def test_valid_with_empty_reason(self):
    ok, error = report_logic.validate_report("abc123", "")
    self.assertTrue(ok)
    self.assertIsNone(error)

  def test_missing_request_id(self):
    for bad in (None, "", "   ", 7):
      ok, error = report_logic.validate_report(bad, "reason")
      self.assertFalse(ok)
      self.assertTrue(error)

  def test_overlong_request_id(self):
    ok, _ = report_logic.validate_report(
        "x" * (report_logic.REQUEST_ID_MAX_LENGTH + 1), ""
    )
    self.assertFalse(ok)

  def test_overlong_reason_rejected(self):
    # validate_report expects an already-normalized reason; an overlong one
    # means the caller skipped normalize_reason.
    ok, _ = report_logic.validate_report(
        "abc123", "a" * (report_logic.REASON_MAX_LENGTH + 1)
    )
    self.assertFalse(ok)

  def test_non_string_reason_rejected(self):
    ok, _ = report_logic.validate_report("abc123", None)
    self.assertFalse(ok)


class DeletionConfirmedTest(unittest.TestCase):

  def test_exact_match(self):
    self.assertTrue(report_logic.deletion_confirmed("DELETE"))

  def test_surrounding_whitespace_ok(self):
    self.assertTrue(report_logic.deletion_confirmed("  DELETE \n"))

  def test_case_sensitive(self):
    self.assertFalse(report_logic.deletion_confirmed("delete"))
    self.assertFalse(report_logic.deletion_confirmed("Delete"))

  def test_wrong_or_missing_text(self):
    self.assertFalse(report_logic.deletion_confirmed(""))
    self.assertFalse(report_logic.deletion_confirmed(None))
    self.assertFalse(report_logic.deletion_confirmed("DELETE MY ACCOUNT"))
    self.assertFalse(report_logic.deletion_confirmed(123))


if __name__ == "__main__":
  unittest.main()
