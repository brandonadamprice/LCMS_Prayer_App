"""Functions for generating the Psalter reading plans page."""

import json
import flask
import psalter_logic

DEFAULT_PSALMS_PER_DAY = 1


def generate_psalter_page(
    psalter_progress=None, completed_by_plan=None, plan_arg=None, bible_streak=0
):
  """Generates HTML for the Psalter reading plans page.

  The active plan is the ?plan= query value when valid, else the user's saved
  choice, else the default. Like Bible in a Year, the whole schedule is passed
  to the template and client-side JavaScript handles day progression and
  fetching psalm text via /get_passage_text. Completed days are stored per
  plan, so switching plans never loses progress.
  """
  psalter_progress = psalter_progress or {}
  completed_by_plan = completed_by_plan or {}

  psalms_per_day = None
  plan_explicit = False
  try:
    requested = int(plan_arg)
    if requested in psalter_logic.PLAN_CHOICES:
      psalms_per_day = requested
      plan_explicit = True
  except (TypeError, ValueError):
    pass
  if psalms_per_day is None:
    saved = psalter_progress.get("psalms_per_day")
    psalms_per_day = (
        saved if saved in psalter_logic.PLAN_CHOICES else DEFAULT_PSALMS_PER_DAY
    )

  schedule = psalter_logic.plan_schedule(psalms_per_day)
  completed_days = completed_by_plan.get(str(psalms_per_day), [])

  template_data = {
      "schedule": json.dumps(schedule),
      "psalter_progress": (
          json.dumps(psalter_progress) if psalter_progress else "null"
      ),
      "completed_days": json.dumps(completed_days),
      "psalms_per_day": psalms_per_day,
      "num_days": len(schedule),
      "plan_explicit": plan_explicit,
      "bible_streak": bible_streak,
      "plan_choices": [
          {"n": n, "days": psalter_logic.plan_length(n)}
          for n in psalter_logic.PLAN_CHOICES
      ],
  }

  return flask.render_template("psalter.html", **template_data)
