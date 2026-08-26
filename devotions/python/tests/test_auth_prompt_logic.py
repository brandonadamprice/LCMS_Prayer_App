"""Tests for the "you need an account" prompt's pure logic."""

import unittest

import auth_prompt_logic


class WantsJsonResponseTest(unittest.TestCase):
  """A script's fetch gets JSON; a browser navigation gets a redirect."""

  def test_plain_navigation_gets_a_redirect(self):
    self.assertFalse(
        auth_prompt_logic.wants_json_response(
            path="/prayer_requests",
            accept="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            sec_fetch_mode="navigate",
            sec_fetch_dest="document",
        )
    )

  def test_navigation_reissued_by_the_service_worker_gets_a_redirect(self):
    # The exact headers sw.js's fetch(event.request) produces: Accept and
    # Sec-Fetch-Mode survive, Sec-Fetch-Dest is rewritten to "empty". Reading
    # Dest first served returning visitors raw JSON as their page.
    self.assertFalse(
        auth_prompt_logic.wants_json_response(
            path="/prayer_requests",
            accept="text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,*/*;q=0.8",
            sec_fetch_mode="navigate",
            sec_fetch_dest="empty",
        )
    )

  def test_html_form_post_gets_a_redirect(self):
    # A form POST is still a navigation: answering it with JSON would dump
    # raw JSON into the address bar.
    self.assertFalse(
        auth_prompt_logic.wants_json_response(
            path="/add_personal_prayer",
            accept="text/html,*/*;q=0.8",
            sec_fetch_mode="navigate",
            sec_fetch_dest="document",
            content_type="application/x-www-form-urlencoded",
        )
    )

  def test_api_path_gets_json(self):
    self.assertTrue(
        auth_prompt_logic.wants_json_response(path="/api/complete_prayer")
    )

  def test_xhr_header_gets_json(self):
    self.assertTrue(
        auth_prompt_logic.wants_json_response(
            path="/toggle_favorite", requested_with="XMLHttpRequest"
        )
    )

  def test_xhr_header_is_case_insensitive(self):
    self.assertTrue(
        auth_prompt_logic.wants_json_response(
            path="/toggle_favorite", requested_with="xmlhttprequest"
        )
    )

  def test_json_body_gets_json(self):
    self.assertTrue(
        auth_prompt_logic.wants_json_response(
            path="/toggle_favorite",
            content_type="application/json; charset=utf-8",
        )
    )

  def test_fetch_gets_json_even_with_a_wildcard_accept(self):
    # fetch() sends Accept: */* by default, which looks HTML-ish; Sec-Fetch-Dest
    # is what actually separates it from a navigation.
    self.assertTrue(
        auth_prompt_logic.wants_json_response(
            path="/save_dark_mode",
            accept="*/*",
            sec_fetch_mode="cors",
            sec_fetch_dest="empty",
        )
    )

  def test_accept_json_without_html_gets_json(self):
    # Fallback for clients that send no Sec-Fetch-Dest.
    self.assertTrue(
        auth_prompt_logic.wants_json_response(
            path="/get_reminders", accept="application/json"
        )
    )

  def test_accept_html_and_json_gets_a_redirect(self):
    self.assertFalse(
        auth_prompt_logic.wants_json_response(
            path="/streaks", accept="text/html,application/json;q=0.9"
        )
    )

  def test_api_path_wins_over_a_navigation_accept(self):
    # /api/ is JSON-only; nothing navigates to it.
    self.assertTrue(
        auth_prompt_logic.wants_json_response(
            path="/api/complete_prayer",
            accept="text/html",
            sec_fetch_mode="navigate",
        )
    )

  def test_no_headers_at_all_gets_a_redirect(self):
    self.assertFalse(auth_prompt_logic.wants_json_response(path="/streaks"))


class SafeNextUrlTest(unittest.TestCase):
  """Only same-site paths survive; everything else falls back."""

  def test_keeps_a_relative_path(self):
    self.assertEqual(
        auth_prompt_logic.safe_next_url("/prayer_requests"), "/prayer_requests"
    )

  def test_keeps_a_query_string(self):
    self.assertEqual(
        auth_prompt_logic.safe_next_url("/liturgical_calendar?year=2026"),
        "/liturgical_calendar?year=2026",
    )

  def test_rejects_an_absolute_url(self):
    self.assertEqual(
        auth_prompt_logic.safe_next_url("https://evil.example/steal"), "/"
    )

  def test_rejects_a_protocol_relative_url(self):
    self.assertEqual(auth_prompt_logic.safe_next_url("//evil.example"), "/")

  def test_rejects_a_backslash_url(self):
    # Some browsers normalize /\evil.example into //evil.example.
    self.assertEqual(auth_prompt_logic.safe_next_url("/\\evil.example"), "/")

  def test_rejects_header_splitting(self):
    self.assertEqual(
        auth_prompt_logic.safe_next_url("/ok\r\nSet-Cookie: a=b"), "/"
    )

  def test_rejects_none_and_empty(self):
    self.assertEqual(auth_prompt_logic.safe_next_url(None), "/")
    self.assertEqual(auth_prompt_logic.safe_next_url(""), "/")

  def test_rejects_non_string(self):
    self.assertEqual(auth_prompt_logic.safe_next_url(42), "/")

  def test_uses_the_given_default(self):
    self.assertEqual(
        auth_prompt_logic.safe_next_url(None, "/settings"), "/settings"
    )


class ShouldRememberNextTest(unittest.TestCase):
  """Remember a page worth returning to, and nothing else."""

  def test_remembers_a_feature_page(self):
    self.assertTrue(auth_prompt_logic.should_remember_next("/prayer_requests"))

  def test_ignores_non_get(self):
    # Replaying a POST after sign-in would repeat an unconfirmed action.
    self.assertFalse(
        auth_prompt_logic.should_remember_next("/add_reminder", "POST")
    )

  def test_ignores_auth_pages(self):
    for path in ("/login", "/login/google", "/register", "/logout",
                 "/authorize", "/auth/firebase"):
      with self.subTest(path=path):
        self.assertFalse(auth_prompt_logic.should_remember_next(path))

  def test_does_not_confuse_a_prefix_match(self):
    # "/registered_users" merely starts with "/register"; it is a page.
    self.assertTrue(
        auth_prompt_logic.should_remember_next("/registered_users")
    )
    self.assertTrue(auth_prompt_logic.should_remember_next("/authorized_only"))


if __name__ == "__main__":
  unittest.main()
