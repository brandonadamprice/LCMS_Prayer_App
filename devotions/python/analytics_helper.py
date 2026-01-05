"""Helper functions for analytics using Pandas."""

import datetime
from google.cloud import firestore
import pandas as pd
import pytz


def get_analytics_data(db):
  """Fetches and aggregates analytics data using Pandas.

  Args:
      db: Firestore client.

  Returns:
      A dictionary containing daily traffic details and aggregated stats.
  """
  eastern_timezone = pytz.timezone("America/New_York")
  today = datetime.datetime.now(eastern_timezone).date()
  start_date = datetime.date(2025, 12, 11)  # Analytics start date

  date_strs = []
  for i in range(14):
    current_date = today - datetime.timedelta(days=i)
    if current_date >= start_date:
      date_strs.append(current_date.strftime("%Y-%m-%d"))
    else:
      break

  # Ensure chronological order for charts
  date_strs.sort()

  if not date_strs:
    return {"daily_traffic": [], "stats": {}}

  # 1. Fetch Daily Analytics
  daily_refs = [db.collection("daily_analytics").document(d) for d in date_strs]
  daily_snapshots = list(db.get_all(daily_refs))

  # 2. Collect Data
  user_ids = set()
  records = []  # List of dicts for DataFrame

  # To reconstruct the detailed view later
  daily_visitors_map = {d: [] for d in date_strs}

  for snap in daily_snapshots:
    if not snap.exists:
      continue
    date_str = snap.id
    data = snap.to_dict()
    visits = data.get("visits", {})

    for uid, visit_data in visits.items():
      user_ids.add(uid)
      paths = visit_data.get("paths", [])
      timestamps = visit_data.get("timestamps", [])
      ua = visit_data.get("user_agent", "")

      # Record for Pandas (one row per user per day is enough for most stats,
      # but for page counts we need paths)
      records.append({
          "date": date_str,
          "user_id": uid,
          "paths": paths,
          "timestamps": timestamps,
          "user_agent": ua,
      })

  # 3. Fetch User Details
  users_info = {}
  if user_ids:
    # Fetch in chunks if needed, but get_all handles lists well usually
    # Splitting into chunks of 100 just to be safe if list is huge
    user_ids_list = list(user_ids)
    chunk_size = 100
    for i in range(0, len(user_ids_list), chunk_size):
      chunk = user_ids_list[i : i + chunk_size]
      user_refs = [
          db.collection("analytics_users").document(uid) for uid in chunk
      ]
      user_snaps = db.get_all(user_refs)
      for snap in user_snaps:
        if snap.exists:
          users_info[snap.id] = snap.to_dict()

  # 4. Build Response and DataFrame
  if not records:
    return _empty_stats(date_strs)

  df = pd.DataFrame(records)

  # Augment with user info
  def get_created_at(uid):
    u = users_info.get(uid)
    if u and u.get("created_at"):
      # Firestore timestamp to datetime
      return u.get("created_at")
    return None

  df["created_at"] = df["user_id"].apply(get_created_at)

  # Calculate Stats

  # A. Daily Traffic (Unique Visits)
  # Already grouped by date in 'records', count rows per date
  daily_counts = df.groupby("date").size()

  # Build detailed list for table
  daily_traffic = []
  for date_str in date_strs:
    day_records = df[df["date"] == date_str]
    visitors_list = []
    for _, row in day_records.iterrows():
      uid = row["user_id"]
      u_info = users_info.get(uid, {})

      # Format timestamps for display
      ts_list = row["timestamps"]
      if ts_list:
        ts_list = sorted(ts_list)

      visitors_list.append({
          "email": u_info.get("email"),
          "hashes": sorted(u_info.get("ip_hashes", [])),
          "paths": sorted(row["paths"]),
          "timestamps": ts_list,
          "user_agent": row["user_agent"],
          "created_at": (
              row["created_at"].isoformat() if row["created_at"] else None
          ),
      })

    daily_traffic.append({
        "date": date_str,
        "count": len(visitors_list),
        "visitors": visitors_list,
    })

  # B. Top Pages
  all_paths = []
  for paths_list in df["paths"]:
    for p in paths_list:
      if p != "/sw.js" and not p.startswith("/static"):
        all_paths.append(p)

  if all_paths:
    top_pages_df = pd.Series(all_paths).value_counts().head(10)
    top_pages = top_pages_df.to_dict()
  else:
    top_pages = {}

  # C. Device Breakdown
  def classify_device(ua):
    if not ua:
      return "Unknown"
    ua_lower = ua.lower()
    if "mobi" in ua_lower or "android" in ua_lower:
      return "Mobile"
    if ua == "Unknown":
      return "Other"
    return "Desktop"

  device_counts = (
      df["user_agent"].apply(classify_device).value_counts().to_dict()
  )
  # Ensure keys exist
  for k in ["Mobile", "Desktop", "Other"]:
    if k not in device_counts:
      device_counts[k] = 0

  # D. Time of Day
  # Flatten timestamps
  all_timestamps = []
  for ts_list in df["timestamps"]:
    all_timestamps.extend(ts_list)

  hour_counts = [0] * 24
  if all_timestamps:
    # Strings to datetime
    # Timestamps stored as ISO strings in Firestore via array union in main.py?
    # main.py uses: timestamp = current_time.isoformat()
    ts_series = pd.to_datetime(all_timestamps)
    # We need them in local time (EST) roughly or as stored (which was EST converted to ISO?)
    # main.py: current_time = datetime.datetime.now(eastern_timezone)
    # So the ISO string is offset-aware. pd.to_datetime handles it.
    # We want the hour.
    hours = ts_series.dt.hour
    h_counts = hours.value_counts().sort_index()
    for h, count in h_counts.items():
      hour_counts[int(h)] = int(count)

  # E. Frequency (Retention)
  # Count days per user
  user_days_count = df.groupby("user_id")["date"].nunique()
  freq_buckets = {"1 Day": 0, "2-5 Days": 0, "6-10 Days": 0, "11+ Days": 0}
  for count in user_days_count:
    if count == 1:
      freq_buckets["1 Day"] += 1
    elif count <= 5:
      freq_buckets["2-5 Days"] += 1
    elif count <= 10:
      freq_buckets["6-10 Days"] += 1
    else:
      freq_buckets["11+ Days"] += 1

  # F. New vs Returning
  # New if created_at date == date
  new_users_daily = []
  returning_users_daily = []

  for date_str in date_strs:
    day_df = df[df["date"] == date_str]
    new_cnt = 0
    ret_cnt = 0
    for _, row in day_df.iterrows():
      if row["created_at"]:
        # created_at is datetime with timezone
        # date_str is YYYY-MM-DD
        # Convert created_at to date string in similar timezone context
        # Assuming created_at stored with timezone info
        created_date_str = (
            row["created_at"].astimezone(eastern_timezone).strftime("%Y-%m-%d")
        )
        if created_date_str == date_str:
          new_cnt += 1
        else:
          ret_cnt += 1
      else:
        ret_cnt += 1
    new_users_daily.append(new_cnt)
    returning_users_daily.append(ret_cnt)

  return {
      "daily_traffic": daily_traffic,
      "stats": {
          "top_pages": top_pages,
          "devices": device_counts,
          "time_of_day": hour_counts,
          "frequency": freq_buckets,
          "new_vs_returning": {
              "dates": date_strs,
              "new_users": new_users_daily,
              "returning_users": returning_users_daily,
          },
      },
  }


def _empty_stats(date_strs):
  return {
      "daily_traffic": [],
      "stats": {
          "top_pages": {},
          "devices": {"Mobile": 0, "Desktop": 0, "Other": 0},
          "time_of_day": [0] * 24,
          "frequency": {
              "1 Day": 0,
              "2-5 Days": 0,
              "6-10 Days": 0,
              "11+ Days": 0,
          },
          "new_vs_returning": {
              "dates": date_strs,
              "new_users": [0] * len(date_strs),
              "returning_users": [0] * len(date_strs),
          },
      },
  }
