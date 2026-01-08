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

    # 1. Top Pages (Last 30 days)
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

    # 2. Realtime (Last 30 minutes)
    realtime_request = RunRealtimeReportRequest(
        property=f"properties/{property_id}",
        metrics=[Metric(name="activeUsers")],
    )
    realtime_response = client.run_realtime_report(realtime_request)
    realtime_users = "0"
    if realtime_response.rows:
      realtime_users = realtime_response.rows[0].metric_values[0].value

    return {
        "top_pages": top_pages,
        "realtime_users": realtime_users,
        "service_email": get_service_account_email(),
    }

  except Exception as e:
    logger.error(f"GA4 API Error: {e}")
    # Return error info to help user debug
    return {"error": str(e), "service_email": get_service_account_email()}
