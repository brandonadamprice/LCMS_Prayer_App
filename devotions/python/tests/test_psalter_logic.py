"""Unit tests for psalter_logic (balanced Psalter reading plans).

psalter_logic imports only the standard library, so this suite runs without
the google-cloud / protobuf stack. Run from the repo root:

    python -m unittest discover -s devotions/python/tests -t devotions/python
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psalter_logic


class VerseCountTests(unittest.TestCase):
  """The embedded verse-count table matches English/ESV versification."""

  def test_covers_all_150_psalms(self):
    self.assertEqual(psalter_logic.NUM_PSALMS, 150)
    self.assertEqual(len(psalter_logic.PSALM_VERSE_COUNTS), 150)

  def test_total_verses(self):
    # 2,461 is the well-known Psalms total in English versification.
    self.assertEqual(psalter_logic.TOTAL_VERSES, 2461)

  def test_spot_checks(self):
    counts = psalter_logic.PSALM_VERSE_COUNTS
    self.assertEqual(counts[23 - 1], 6)  # Psalm 23
    self.assertEqual(counts[117 - 1], 2)  # Psalm 117, shortest
    self.assertEqual(counts[119 - 1], 176)  # Psalm 119, longest
    self.assertEqual(counts[150 - 1], 6)  # Psalm 150

  def test_all_positive(self):
    self.assertTrue(all(c > 0 for c in psalter_logic.PSALM_VERSE_COUNTS))


class PlanShapeTests(unittest.TestCase):
  """Every plan covers all psalms exactly once, in order."""

  def test_plan_lengths(self):
    expected = {1: 150, 2: 75, 3: 50, 4: 38, 5: 30}
    for n, days in expected.items():
      self.assertEqual(psalter_logic.plan_length(n), days)

  def test_invalid_choice_raises(self):
    for bad in (0, 6, -1, None, "3", 2.5, True):
      self.assertFalse(psalter_logic.is_valid_choice(bad))
      with self.assertRaises(ValueError):
        psalter_logic.plan_length(bad)
      with self.assertRaises(ValueError):
        psalter_logic.build_plan(bad)

  def test_valid_choices_accepted(self):
    for n in psalter_logic.PLAN_CHOICES:
      self.assertTrue(psalter_logic.is_valid_choice(n))

  def test_plans_cover_psalter_in_order(self):
    for n in psalter_logic.PLAN_CHOICES:
      plan = psalter_logic.build_plan(n)
      self.assertEqual(len(plan), psalter_logic.plan_length(n))
      flattened = [p for day in plan for p in day]
      self.assertEqual(flattened, list(range(1, 151)))
      self.assertTrue(all(day for day in plan), "every day has a psalm")

  def test_one_per_day_plan_is_all_singletons(self):
    plan = psalter_logic.build_plan(1)
    self.assertTrue(all(len(day) == 1 for day in plan))

  def test_plans_are_deterministic(self):
    for n in psalter_logic.PLAN_CHOICES:
      self.assertEqual(psalter_logic.build_plan(n), psalter_logic.build_plan(n))

  # Golden snapshots: the last psalm of every day, which (with canonical
  # order) fully determines each partition. Two users on the same plan must
  # always see the same schedule -- across processes, servers, and releases.
  # If an intentional algorithm change alters these, treat it as a breaking
  # change for saved per-plan progress before updating the snapshot.
  GOLDEN_DAY_ENDS = {
      1: tuple(range(1, 151)),
      2: (3, 5, 7, 9, 11, 15, 17, 18, 21, 23, 25, 27, 30, 31, 33, 34, 36, 37,
          38, 40, 43, 44, 46, 48, 49, 50, 53, 55, 57, 59, 62, 65, 67, 68, 69,
          71, 72, 73, 75, 77, 78, 80, 82, 84, 86, 88, 89, 91, 93, 95, 97, 101,
          102, 103, 104, 105, 106, 107, 109, 112, 115, 117, 118, 119, 124,
          129, 132, 135, 137, 139, 142, 144, 145, 147, 150),
      3: (5, 8, 11, 17, 18, 21, 23, 26, 30, 33, 35, 37, 39, 43, 45, 49, 51,
          55, 59, 63, 66, 68, 70, 72, 74, 77, 78, 81, 85, 88, 89, 92, 96, 101,
          103, 104, 105, 106, 108, 111, 115, 118, 119, 126, 133, 136, 139,
          143, 146, 150),
      4: (6, 10, 17, 19, 24, 29, 33, 36, 38, 43, 47, 50, 55, 60, 65, 68, 71,
          73, 77, 78, 82, 87, 89, 93, 97, 102, 104, 105, 106, 108, 114, 118,
          119, 128, 135, 139, 145, 150),
      5: (7, 15, 18, 24, 30, 34, 37, 43, 48, 53, 59, 66, 69, 73, 77, 78, 83,
          88, 91, 97, 103, 105, 107, 113, 118, 119, 131, 138, 144, 150),
  }

  def test_plans_match_golden_snapshots(self):
    self.assertEqual(
        set(self.GOLDEN_DAY_ENDS), set(psalter_logic.PLAN_CHOICES)
    )
    for n, expected_ends in self.GOLDEN_DAY_ENDS.items():
      plan = psalter_logic.build_plan(n)
      self.assertEqual(
          tuple(day[-1] for day in plan), expected_ends, f"plan {n} changed"
      )


class PlanBalanceTests(unittest.TestCase):
  """Days are balanced by verse count, not by psalm count."""

  def test_no_day_longer_than_psalm_119(self):
    # Psalm 119 (176 verses) sets the floor for the longest possible day;
    # a balanced plan never packs anything on top of it.
    for n in psalter_logic.PLAN_CHOICES:
      plan = psalter_logic.build_plan(n)
      max_day = max(psalter_logic.day_verse_count(day) for day in plan)
      self.assertEqual(max_day, 176, f"plan {n}: unbalanced long day")

  def test_psalm_119_stands_alone_in_multi_psalm_plans(self):
    for n in psalter_logic.PLAN_CHOICES:
      plan = psalter_logic.build_plan(n)
      day_with_119 = next(day for day in plan if 119 in day)
      self.assertEqual(day_with_119, (119,))

  def test_days_hug_the_average(self):
    # Every day should stay close to the plan's average verse load. A day
    # holding a single long psalm can't be split further, so it is only
    # capped by Psalm 119 (176 verses); combined days must stay in a
    # half-to-one-and-a-half band around the average.
    for n in psalter_logic.PLAN_CHOICES[1:]:  # 1/day can't rebalance singles
      plan = psalter_logic.build_plan(n)
      average = psalter_logic.TOTAL_VERSES / len(plan)
      for day in plan:
        verses = psalter_logic.day_verse_count(day)
        label = (f"plan {n}: day {day} has {verses} verses"
                 f" vs average {average:.1f}")
        self.assertGreaterEqual(verses, average / 2, label)
        if len(day) > 1:
          self.assertLessEqual(verses, average * 1.5, label)
        else:
          self.assertLessEqual(verses, 176, label)


class FormattingTests(unittest.TestCase):
  """Labels and references render as expected."""

  def test_single_psalm_label(self):
    self.assertEqual(psalter_logic.day_label((23,)), "Psalm 23")

  def test_range_label(self):
    self.assertEqual(psalter_logic.day_label((120, 121, 122)), "Psalms 120–122")

  def test_day_refs(self):
    self.assertEqual(
        psalter_logic.day_refs((1, 2)), ["Psalm 1", "Psalm 2"]
    )

  def test_plan_schedule_shape(self):
    schedule = psalter_logic.plan_schedule(5)
    self.assertEqual(len(schedule), 30)
    self.assertEqual(schedule[0]["day"], 1)
    self.assertEqual(schedule[-1]["day"], 30)
    for entry in schedule:
      self.assertEqual(set(entry), {"day", "label", "refs", "verses"})
      self.assertEqual(len(entry["refs"]), len(set(entry["refs"])))
      self.assertGreater(entry["verses"], 0)


if __name__ == "__main__":
  unittest.main()
