"""Helper functions for fetching Google Analytics 4 data."""

import logging
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange
from google.analytics.data_v1beta.types import Dimension
from google.analytics.data_v1beta.types import Metric
from google.analytics.data_v1beta.types import RunReportRequest
import google.auth

logger = logging.getLogger(__name__)

def get_service_account_email():
    """Attempts to retrieve the current service account email."""
    try:
        credentials, project_id = google.auth.default()
        if hasattr(credentials, "service_account_email"):
            return credentials.service_account_email
        return "Unknown (Using default credentials, check Cloud Console)"
    except Exception as e:
        logger.error(f"Error fetching credentials: {e}")
        return "Error fetching credentials"

def fetch_traffic_stats(property_id):
    """Fetches traffic stats from GA4."""
    if not property_id:
        raise ValueError("GA4_PROPERTY_ID is not set.")

    try:
        client = BetaAnalyticsDataClient()
        
        # 1. Daily Trend (Last 14 days)
        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="date"), Dimension(name="dayOfWeekName")],
            metrics=[Metric(name="activeUsers"), Metric(name="screenPageViews")],
            date_ranges=[DateRange(start_date="14daysAgo", end_date="today")],
            order_bys=[{"dimension": {"dimension_name": "date"}}],
        )
        response = client.run_report(request)
        
        daily_data = []
        for row in response.rows:
            # Date format YYYYMMDD
            date_str = row.dimension_values[0].value
            formatted_date = f"{date_str[4:6]}-{date_str[6:8]}" # MM-DD
            
            daily_data.append({
                "date": formatted_date,
                "day_name": row.dimension_values[1].value,
                "users": row.metric_values[0].value,
                "views": row.metric_values[1].value
            })

        # 2. Top Pages (Last 30 days)
        page_request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="pageTitle"), Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews")],
            date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
            limit=10
        )
        page_response = client.run_report(page_request)
        
        top_pages = []
        for row in page_response.rows:
            top_pages.append({
                "title": row.dimension_values[0].value,
                "path": row.dimension_values[1].value,
                "views": row.metric_values[0].value
            })

        return {
            "daily_traffic": daily_data,
            "top_pages": top_pages,
            "service_email": get_service_account_email()
        }

    except Exception as e:
        logger.error(f"GA4 API Error: {e}")
        # Return error info to help user debug
        return {
            "error": str(e),
            "service_email": get_service_account_email()
        }
