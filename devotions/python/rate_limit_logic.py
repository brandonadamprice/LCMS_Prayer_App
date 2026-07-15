"""Pure, dependency-free sliding-window rate limiting.

Stdlib-only (no Flask/Firestore imports) so it stays unit-testable like
streak_logic.py; the Flask integration lives in main.py.

The store is in-process memory, which is deliberate: with N gunicorn
workers/instances the effective ceiling becomes N x limit, which is still
low enough to blunt scripted abuse of the public endpoints (token guessing,
Firestore-write spam, tying up threads via the auth-helper proxy). This is
abuse protection, not fair-use accounting and not volumetric-DDoS defense,
so shared storage (Redis/Firestore) would be complexity without a
threat-model win.
"""

import collections
import threading
import time

# Above this many distinct keys, expired keys are swept on the next call so
# an attacker rotating IPs can't grow the store without bound.
_PURGE_THRESHOLD = 10_000


class SlidingWindowLimiter:
  """Allows at most `limit` events per `window_seconds` per key."""

  def __init__(self, limit, window_seconds, clock=time.monotonic):
    if limit < 1 or window_seconds <= 0:
      raise ValueError("limit must be >= 1 and window_seconds > 0")
    self._limit = limit
    self._window = window_seconds
    self._clock = clock  # Injectable for tests.
    self._events = {}  # key -> deque of event timestamps
    self._lock = threading.Lock()

  def allow(self, key):
    """Records an attempt for `key`; returns True if it is under the limit.

    Denied attempts are not recorded, so a blocked client regains exactly
    `limit` slots once its earlier events leave the window.
    """
    now = self._clock()
    cutoff = now - self._window
    with self._lock:
      queue = self._events.get(key)
      if queue is None:
        queue = collections.deque()
        self._events[key] = queue
      while queue and queue[0] <= cutoff:
        queue.popleft()
      allowed = len(queue) < self._limit
      if allowed:
        queue.append(now)
      if len(self._events) > _PURGE_THRESHOLD:
        self._purge_locked(cutoff)
      return allowed

  def _purge_locked(self, cutoff):
    """Drops keys whose events have all left the window. Caller holds lock."""
    dead = [
        key for key, queue in self._events.items()
        if not queue or queue[-1] <= cutoff
    ]
    for key in dead:
      del self._events[key]
