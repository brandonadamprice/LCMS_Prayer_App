"""Tests for the pure sliding-window rate limiter."""

import unittest

import rate_limit_logic


class FakeClock:
  """Deterministic, manually-advanced clock."""

  def __init__(self):
    self.now = 1000.0

  def __call__(self):
    return self.now

  def advance(self, seconds):
    self.now += seconds


def make_limiter(limit, window):
  clock = FakeClock()
  limiter = rate_limit_logic.SlidingWindowLimiter(limit, window, clock=clock)
  return limiter, clock


class SlidingWindowLimiterTest(unittest.TestCase):

  def test_allows_up_to_limit(self):
    limiter, _ = make_limiter(3, 60)
    self.assertTrue(limiter.allow("ip1"))
    self.assertTrue(limiter.allow("ip1"))
    self.assertTrue(limiter.allow("ip1"))

  def test_blocks_over_limit(self):
    limiter, _ = make_limiter(3, 60)
    for _ in range(3):
      limiter.allow("ip1")
    self.assertFalse(limiter.allow("ip1"))

  def test_keys_are_independent(self):
    limiter, _ = make_limiter(1, 60)
    self.assertTrue(limiter.allow("ip1"))
    self.assertFalse(limiter.allow("ip1"))
    self.assertTrue(limiter.allow("ip2"))

  def test_window_slides(self):
    limiter, clock = make_limiter(2, 60)
    self.assertTrue(limiter.allow("ip1"))
    clock.advance(30)
    self.assertTrue(limiter.allow("ip1"))
    self.assertFalse(limiter.allow("ip1"))
    # First event (t=0) leaves the window at t=61; the t=30 one remains.
    clock.advance(31)
    self.assertTrue(limiter.allow("ip1"))
    self.assertFalse(limiter.allow("ip1"))

  def test_full_window_elapsed_resets(self):
    limiter, clock = make_limiter(2, 60)
    limiter.allow("ip1")
    limiter.allow("ip1")
    self.assertFalse(limiter.allow("ip1"))
    clock.advance(61)
    self.assertTrue(limiter.allow("ip1"))

  def test_denied_attempts_do_not_consume_slots(self):
    """A blocked client regains exactly `limit` slots once events expire."""
    limiter, clock = make_limiter(2, 60)
    limiter.allow("ip1")
    limiter.allow("ip1")
    for _ in range(10):  # Hammering while blocked records nothing.
      self.assertFalse(limiter.allow("ip1"))
    clock.advance(61)
    self.assertTrue(limiter.allow("ip1"))
    self.assertTrue(limiter.allow("ip1"))
    self.assertFalse(limiter.allow("ip1"))

  def test_purge_drops_expired_keys(self):
    limiter, clock = make_limiter(1, 60)
    # Grow past the purge threshold with distinct keys.
    for i in range(rate_limit_logic._PURGE_THRESHOLD + 1):
      limiter.allow(f"ip{i}")
    self.assertGreater(len(limiter._events), rate_limit_logic._PURGE_THRESHOLD)
    # After the window passes, one more call sweeps the dead keys.
    clock.advance(61)
    limiter.allow("fresh")
    self.assertLessEqual(len(limiter._events), 2)

  def test_rejects_bad_construction(self):
    with self.assertRaises(ValueError):
      rate_limit_logic.SlidingWindowLimiter(0, 60)
    with self.assertRaises(ValueError):
      rate_limit_logic.SlidingWindowLimiter(5, 0)


if __name__ == "__main__":
  unittest.main()
