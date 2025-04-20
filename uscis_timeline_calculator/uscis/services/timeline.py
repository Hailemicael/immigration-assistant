"""
Timeline calculation service for USCIS processing times.

This module handles the calculation of immigration timelines based on
form type, service center, form category, and filing date using the official USCIS methodology.
"""

import datetime
import logging
from typing import Dict, Any, Optional

# Configure module-level logger
logger = logging.getLogger(__name__)


def generate_timeline(data_item: Dict[str, Any], filing_date: str, 
                      form_category: Optional[str] = None) -> Dict[str, Any]:
    """
    Calculate detailed processing timeline based on USCIS methodology.
    
    The USCIS processing time is the amount of time it took to complete 
    80% of adjudicated cases over the last six months.
    
    Args:
        data_item: Dictionary containing processing time information
        filing_date: String in YYYY-MM-DD format
        form_category: Category of the form (optional)
    
    Returns:
        Dictionary with comprehensive timeline information
    """
    # Extract processing times from data item
    min_months = data_item["min_months"]
    median_months = data_item["median_months"]
    max_months = data_item["max_months"]
    
    # Parse filing date
    try:
        filing_date_obj = datetime.datetime.strptime(filing_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Filing date must be in YYYY-MM-DD format.")
    
    # Calculate processing milestone dates
    current_date = datetime.datetime.now()
    
    earliest_approval_date = filing_date_obj + datetime.timedelta(days=int(min_months * 30.5))
    median_approval_date = filing_date_obj + datetime.timedelta(days=int(median_months * 30.5))
    latest_approval_date = filing_date_obj + datetime.timedelta(days=int(max_months * 30.5))
    
    # Calculate days elapsed since filing
    days_elapsed = (current_date - filing_date_obj).days
    if days_elapsed < 0:
        days_elapsed = 0  # Handle future filing dates
    
    # Calculate progress percentage
    if days_elapsed == 0:
        progress_percent = 0
    else:
        estimated_total_days = median_months * 30.5
        progress_percent = min(100, round((days_elapsed / estimated_total_days) * 100))
    
    # Determine case status based on timeline
    if current_date > latest_approval_date:
        status = "Outside normal processing time"
        can_submit_inquiry = True
    elif current_date > median_approval_date:
        status = "Approaching final stage"
        can_submit_inquiry = False
    elif current_date > earliest_approval_date:
        status = "Within normal processing timeframe"
        can_submit_inquiry = False
    else:
        status = "Initial processing stage"
        can_submit_inquiry = False
    
    # Calculate case inquiry eligibility date
    # USCIS formula: Case inquiry allowed when case takes longer than time to complete 93% of adjudications
    # This is approximated as max_months in our data model
    inquiry_eligibility_date = filing_date_obj + datetime.timedelta(days=int(max_months * 30.5))
    
    # If inquiry eligibility date is in the past, set to "Eligible now"
    if inquiry_eligibility_date <= current_date:
        inquiry_eligibility_text = "Eligible now"
    else:
        inquiry_eligibility_text = inquiry_eligibility_date.strftime("%B %d, %Y")
    
    # Construct timeline dictionary
    timeline = {
        "form_info": {
            "form_number": data_item["form_number"],
            "form_description": data_item["form_description"],
            "service_center": data_item["service_center"],
            "form_category": form_category or "Standard Processing"
        },
        "filing_info": {
            "filing_date": filing_date_obj.strftime("%B %d, %Y"),
            "days_since_filing": days_elapsed,
            "progress_percent": progress_percent
        },
        "processing_time": {
            "min_months": round(min_months, 1),
            "median_months": round(median_months, 1),
            "max_months": round(max_months, 1),
        },
        "estimated_timeline": {
            "earliest_date": earliest_approval_date.strftime("%B %d, %Y"),
            "median_date": median_approval_date.strftime("%B %d, %Y"),
            "latest_date": latest_approval_date.strftime("%B %d, %Y")
        },
        "case_status": {
            "current_status": status,
            "can_submit_inquiry": can_submit_inquiry,
            "inquiry_eligibility_date": inquiry_eligibility_text
        },
        "data_source": {
            "last_updated": data_item["last_updated"],
            "next_update": (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%B %d, %Y"),
            "calculation_note": "Based on time to complete 80% of cases over last 6 months."
        }
    }
    
    # For cycle time methodology forms (I-129, I-129CW), add note about different calculation
    if data_item["form_number"] in ["I-129", "I-129CW"]:
        timeline["data_source"]["calculation_note"] = "This form uses USCIS cycle time methodology."
    
    return timeline