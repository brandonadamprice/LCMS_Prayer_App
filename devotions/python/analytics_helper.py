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
    if not isinstance(visits, dict):
      continue

    for uid, visit_data in visits.items():
      if not isinstance(visit_data, dict):
        continue
      user_ids.add(uid)
      
      paths = visit_data.get("paths")
      if paths is None:
        paths = []
      elif not isinstance(paths, list):
        paths = [str(paths)]
        
      timestamps = visit_data.get("timestamps")
      if timestamps is None:
        timestamps = []
      elif not isinstance(timestamps, list):
        timestamps = [str(timestamps)]

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

      created_at_val = row["created_at"]
      created_at_str = None
      if pd.notnull(created_at_val) and hasattr(created_at_val, "isoformat"):
        created_at_str = created_at_val.isoformat()

      # Safe retrieval and sorting for hashes
      hashes = u_info.get("ip_hashes")
      if hashes is None:
        hashes = []
      elif not isinstance(hashes, list):
        hashes = [str(hashes)]
      safe_hashes = sorted([str(h) for h in hashes])

      # Safe retrieval and sorting for paths
      paths = row["paths"]
      if paths is None:
        paths = []
      elif not isinstance(paths, list):
        paths = [str(paths)]
      safe_paths = sorted([str(p) for p in paths])

      visitors_list.append({
          "email": u_info.get("email"),
          "hashes": safe_hashes,
          "paths": safe_paths,
          "timestamps": ts_list,
          "user_agent": row["user_agent"],
          "created_at": created_at_str,
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
    if not ua or pd.isnull(ua):
      return "Unknown"
    try:
      ua_lower = str(ua).lower()
    except Exception:
      return "Unknown"
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
  hour_counts = [0] * 24
  try:
    # Flatten timestamps
    all_timestamps = []
    for ts_list in df["timestamps"]:
      if isinstance(ts_list, list):
        all_timestamps.extend(ts_list)
    
    if all_timestamps:
      # Strings to datetime, coerce errors to NaT
      ts_series = pd.to_datetime(all_timestamps, errors="coerce")
      ts_series = ts_series.dropna()

      # Convert to Eastern Time if possible (assuming UTC/ISO)
      # If they are tz-aware (from ISO), this converts.
      # If they are naive, we might need to localize first, but main.py saves as ISO with offset (Eastern).
      # So they should be tz-aware.
      if not ts_series.empty:
        # Check if tz-aware
        if ts_series.dt.tz is not None:
           ts_series = ts_series.dt.convert_timezone(eastern_timezone)
        
        hours = ts_series.dt.hour
        h_counts = hours.value_counts().sort_index()
        for h, count in h_counts.items():
          hour_counts[int(h)] = int(count)
  except Exception as e:
    print(f"Error calculating Time of Day: {e}")

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
  new_users_daily = []
  returning_users_daily = []
  try:
    for date_str in date_strs:
      day_df = df[df["date"] == date_str]
      new_cnt = 0
      ret_cnt = 0
      for _, row in day_df.iterrows():
        created_at_val = row["created_at"]
        if pd.notnull(created_at_val) and hasattr(
            created_at_val, "astimezone"
        ):
          try:
            created_date_str = (
                created_at_val.astimezone(eastern_timezone).strftime("%Y-%m-%d")
            )
            if created_date_str == date_str:
              new_cnt += 1
            else:
              ret_cnt += 1
          except Exception:
            ret_cnt += 1
        else:
          # Fallback: if created_at is missing, count as returning or new?
          # If we don't know, returning is safer for retention stats, 
          # but new is safer for "visits from unknown".
          # Let's assume returning for stability.
          ret_cnt += 1
      new_users_daily.append(new_cnt)
      returning_users_daily.append(ret_cnt)
  except Exception as e:
    print(f"Error calculating New vs Returning: {e}")
    # Fill with zeros if failed
    new_users_daily = [0] * len(date_strs)
    returning_users_daily = [0] * len(date_strs)

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
