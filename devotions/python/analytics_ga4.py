"""Helper functions for fetching Google Analytics 4 data."""

import logging
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange
from google.analytics.data_v1beta.types import Dimension
from google.analytics.data_v1beta.types import Metric
from google.analytics.data_v1beta.types import RunRealtimeReportRequest
from google.analytics.data_v1beta.types import RunReportRequest
import google.auth
import google.auth.transport.requests
import requests

logger = logging.getLogger(__name__)


def get_service_account_email():
  """Attempts to retrieve the current authenticated email."""
  try:
    credentials, _ = google.auth.default()

    # Try to refresh credentials to ensure we have a token
    if not credentials.valid:
      request = google.auth.transport.requests.Request()
      credentials.refresh(request)

    # If it's a service account with an email attribute, return it
    if (
        hasattr(credentials, "service_account_email")
        and credentials.service_account_email
    ):
      return credentials.service_account_email

    # If not, or if we want to be sure, query the token info endpoint
    if credentials.token:
      resp = requests.get(
          f"https://www.googleapis.com/oauth2/v3/tokeninfo?access_token={credentials.token}",
          timeout=5,
      )
      if resp.status_code == 200:
        data = resp.json()
        # 'email' is present for user credentials and some SAs
        if "email" in data:
          return data["email"]

    return "Unknown (Could not determine authenticated email)"
  except Exception as e:
    logger.error(f"Error fetching credentials email: {e}")
    return "Error fetching credentials"


def fetch_traffic_stats(property_id):
  """Fetches traffic stats from GA4."""
  if not property_id:
    raise ValueError("GA4_PROPERTY_ID is not set.")

  try:
    client = BetaAnalyticsDataClient()

    # 1. Daily Trend (Last 30 days)
    # Reverting to 'activeUsers' per request.
    # We pre-fill the last 30 days with zeros to ensure the chart always renders
    # even if the API returns no rows or partial data.
    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="activeUsers"), Metric(name="screenPageViews")],
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        order_bys=[{"dimension": {"dimension_name": "date"}}],
        keep_empty_rows=True,
    )
    response = client.run_report(request)

    import datetime
    
    # Create a map of date_str (YYYYMMDD) -> data
    api_data_map = {}
    for row in response.rows:
        date_str = row.dimension_values[0].value
        api_data_map[date_str] = {
            "users": int(row.metric_values[0].value),
            "views": int(row.metric_values[1].value)
        }

    # Generate last 30 days including today
    daily_data = []
    today = datetime.date.today()
    # We go back 30 days. 
    # Note: '30daysAgo' in GA4 usually implies start date. 
    # range(30) covers 0 to 29 days ago.
    for i in range(29, -1, -1):
        d = today - datetime.timedelta(days=i)
        date_key = d.strftime("%Y%m%d")
        
        day_data = api_data_map.get(date_key, {"users": 0, "views": 0})
        
        formatted_date = d.strftime("%m-%d")
        day_name = d.strftime("%A")

        daily_data.append({
            "date": formatted_date,
            "day_name": day_name,
            "users": day_data["users"],
            "views": day_data["views"],
        })

    logger.info(f"Fetched {len(daily_data)} daily traffic rows.")

    # 2. Top Pages (Last 30 days)
    page_request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="pageTitle"), Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews")],
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        limit=10,
    )
    page_response = client.run_report(page_request)

    top_pages = []
    for row in page_response.rows:
      top_pages.append({
          "title": row.dimension_values[0].value,
          "path": row.dimension_values[1].value,
          "views": int(row.metric_values[0].value),
      })

    logger.info(f"Fetched {len(top_pages)} top pages.")

    # 3. Realtime (Last 30 minutes)
    realtime_request = RunRealtimeReportRequest(
        property=f"properties/{property_id}",
        metrics=[Metric(name="activeUsers")],
    )
    realtime_response = client.run_realtime_report(realtime_request)
    realtime_users = "0"
    if realtime_response.rows:
      realtime_users = realtime_response.rows[0].metric_values[0].value

    # 4. User Retention (New vs Returning) - Last 30 Days
    retention_request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="newVsReturning")],
        metrics=[Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
    )
    retention_response = client.run_report(retention_request)
    retention_data = {"new": 0, "returning": 0}
    for row in retention_response.rows:
      key = row.dimension_values[0].value.lower()  # 'new' or 'returning'
      if "new" in key:
        retention_data["new"] = int(row.metric_values[0].value)
      elif "returning" in key:
        retention_data["returning"] = int(row.metric_values[0].value)

    # 5. Time of Day (Hourly) - Last 30 Days
    hourly_request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="hour")],
        metrics=[Metric(name="activeUsers")],
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
        order_bys=[{"dimension": {"dimension_name": "hour"}}],
        keep_empty_rows=True,
    )
    hourly_response = client.run_report(hourly_request)

    # Initialize 0-23 hours with 0
    hourly_counts = [0] * 24
    for row in hourly_response.rows:
      try:
        h = int(row.dimension_values[0].value)
        if 0 <= h < 24:
          hourly_counts[h] = int(row.metric_values[0].value)
      except ValueError:
        pass

    return {
        "daily_traffic": daily_data,
        "top_pages": top_pages,
        "realtime_users": realtime_users,
        "retention_data": retention_data,
        "hourly_data": hourly_counts,
        "service_email": get_service_account_email(),
    }

  except Exception as e:
    logger.error(f"GA4 API Error: {e}")
    # Return error info to help user debug
    return {"error": str(e), "service_email": get_service_account_email()}
