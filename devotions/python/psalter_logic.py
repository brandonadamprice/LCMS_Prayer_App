"""Pure, dependency-free Psalter reading-plan math.

Builds balanced Psalter reading plans: the 150 psalms are split, in canonical
order, into a fixed number of days so that every day carries roughly the same
number of verses rather than the same number of psalms (Psalm 119 alone is
longer than several average days put together, while Psalms 120-134 are tiny).
The "psalms per day" a user picks is therefore an average: it fixes the plan's
length, and the verses are then distributed evenly across those days.

Deliberately free of firebase/google-cloud imports so it stays unit-testable
(see tests/test_psalter_logic.py).
"""

import functools
import math

# Verse counts for Psalms 1-150 (English/ESV versification). Index 0 = Psalm 1.
PSALM_VERSE_COUNTS = (
    6, 12, 8, 8, 12, 10, 17, 9, 20, 18,
    7, 8, 6, 7, 5, 11, 15, 50, 14, 9,
    13, 31, 6, 10, 22, 12, 14, 9, 11, 12,
    24, 11, 22, 22, 28, 12, 40, 22, 13, 17,
    13, 11, 5, 26, 17, 11, 9, 14, 20, 23,
    19, 9, 6, 7, 23, 13, 11, 11, 17, 12,
    8, 12, 11, 10, 13, 20, 7, 35, 36, 5,
    24, 20, 28, 23, 10, 12, 20, 72, 13, 19,
    16, 8, 18, 12, 13, 17, 7, 18, 52, 17,
    16, 15, 5, 23, 11, 13, 12, 9, 9, 5,
    8, 28, 22, 35, 45, 48, 43, 13, 31, 7,
    10, 10, 9, 8, 18, 19, 2, 29, 176, 7,
    8, 9, 4, 8, 5, 6, 5, 6, 8, 8,
    3, 18, 3, 3, 21, 26, 9, 8, 24, 13,
    10, 7, 12, 15, 21, 10, 20, 14, 9, 6,
)

NUM_PSALMS = len(PSALM_VERSE_COUNTS)
TOTAL_VERSES = sum(PSALM_VERSE_COUNTS)

# Supported "psalms per day" choices (each an average; see module docstring).
PLAN_CHOICES = (1, 2, 3, 4, 5)


def is_valid_choice(psalms_per_day):
  """Whether the value is a supported psalms-per-day choice.

  Rejects bools explicitly: JSON true would otherwise pass as 1.
  """
  return (
      not isinstance(psalms_per_day, bool)
      and psalms_per_day in PLAN_CHOICES
  )


def plan_length(psalms_per_day):
  """Returns the number of days in the plan for a psalms-per-day choice."""
  if not is_valid_choice(psalms_per_day):
    raise ValueError(f"Unsupported psalms per day: {psalms_per_day!r}")
  return math.ceil(NUM_PSALMS / psalms_per_day)


@functools.lru_cache(maxsize=None)
def build_plan(psalms_per_day):
  """Splits Psalms 1-150, in order, into verse-balanced days.

  Returns a tuple of days; each day is a tuple of consecutive psalm numbers.
  The partition minimizes the sum of squared per-day verse counts (least
  squares), which drives every day toward the mean verse load -- the fairest
  spread achievable with whole psalms kept in canonical order. The result is
  deterministic for a given choice.
  """
  num_days = plan_length(psalms_per_day)

  prefix = [0] * (NUM_PSALMS + 1)
  for i, count in enumerate(PSALM_VERSE_COUNTS):
    prefix[i + 1] = prefix[i] + count

  # best[d][i]: minimal sum of squared day-verse-counts splitting the first i
  # psalms into d non-empty days; split[d][i]: the j achieving it (day d is
  # psalms j+1..i).
  inf = float("inf")
  best = [[inf] * (NUM_PSALMS + 1) for _ in range(num_days + 1)]
  split = [[0] * (NUM_PSALMS + 1) for _ in range(num_days + 1)]
  best[0][0] = 0
  for d in range(1, num_days + 1):
    # Splitting the first i psalms into d non-empty days needs i >= d, and
    # must leave at least one psalm for each of the remaining days.
    for i in range(d, NUM_PSALMS - (num_days - d) + 1):
      for j in range(d - 1, i):
        if best[d - 1][j] == inf:
          continue
        day_verses = prefix[i] - prefix[j]
        cand = best[d - 1][j] + day_verses * day_verses
        if cand < best[d][i]:
          best[d][i] = cand
          split[d][i] = j

  days = []
  i = NUM_PSALMS
  for d in range(num_days, 0, -1):
    j = split[d][i]
    days.append(tuple(range(j + 1, i + 1)))
    i = j
  days.reverse()
  return tuple(days)


def day_verse_count(psalms):
  """Returns the total verse count for a day's psalm numbers."""
  return sum(PSALM_VERSE_COUNTS[p - 1] for p in psalms)


def day_label(psalms):
  """Returns a display label like "Psalm 23" or "Psalms 120-127"."""
  if len(psalms) == 1:
    return f"Psalm {psalms[0]}"
  return f"Psalms {psalms[0]}–{psalms[-1]}"


def day_refs(psalms):
  """Returns one ESV-fetchable reference per psalm, e.g. ["Psalm 120", ...]."""
  return [f"Psalm {p}" for p in psalms]


def plan_schedule(psalms_per_day):
  """Returns the plan as JSON-friendly dicts, one per day, for templates."""
  return [
      {
          "day": day_number,
          "label": day_label(psalms),
          "refs": day_refs(psalms),
          "verses": day_verse_count(psalms),
      }
      for day_number, psalms in enumerate(build_plan(psalms_per_day), start=1)
  ]
