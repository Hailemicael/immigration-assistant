"""
Timeline visualization service for USCIS processing times.

This module generates visual representations of immigration timelines
using matplotlib, ensuring clear and professional charts.
"""

import os
import logging
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Dict, Any
from flask import current_app

# Configure module-level logger
logger = logging.getLogger(__name__)


def plot_timeline(timeline_data: Dict[str, Any], filing_date: str) -> str:
    """
    Generate a professional-looking timeline visualization based on USCIS data.
    
    Args:
        timeline_data: Dictionary containing timeline information
        filing_date: String in YYYY-MM-DD format
    
    Returns:
        String: Path to the generated chart file
    """
    # Parse dates
    filing_date_obj = datetime.datetime.strptime(filing_date, "%Y-%m-%d")
    earliest_date = datetime.datetime.strptime(
        timeline_data["estimated_timeline"]["earliest_date"], "%B %d, %Y")
    median_date = datetime.datetime.strptime(
        timeline_data["estimated_timeline"]["median_date"], "%B %d, %Y")
    latest_date = datetime.datetime.strptime(
        timeline_data["estimated_timeline"]["latest_date"], "%B %d, %Y")
    current_date = datetime.datetime.now()
    
    # Calculate the date range and proper padding
    all_dates = [filing_date_obj, earliest_date, median_date, latest_date, current_date]
    min_date = min(all_dates) - datetime.timedelta(days=15)
    max_date = max(all_dates) + datetime.timedelta(days=15)
    
    # Create figure with improved styling
    plt.figure(figsize=(10, 4), dpi=100)
    ax = plt.gca()
    
    # Set plot colors - USCIS website colors
    PRIMARY_BLUE = "#0071bc"
    DARK_BLUE = "#205493"
    LIGHT_BLUE = "#02bfe7"
    GRAY = "#5b616b"
    LIGHT_GRAY = "#d6d7d9"
    RED = "#e31c3d"
    GREEN = "#2e8540"
    
    # Plot the timeline axis with improved styling
    plt.plot([min_date, max_date], [1, 1], color=LIGHT_GRAY, linewidth=2, zorder=1)
    
    # Add milestone markers
    plt.plot(filing_date_obj, 1, 'o', color=DARK_BLUE, markersize=12, 
             label='Filing Date', zorder=3)
    plt.plot(earliest_date, 1, 'o', color=PRIMARY_BLUE, markersize=12, 
             label='Earliest Estimated Completion', zorder=3)
    plt.plot(median_date, 1, 'o', color=PRIMARY_BLUE, markersize=12, 
             label='Median Estimated Completion', zorder=3)
    plt.plot(latest_date, 1, 'o', color=PRIMARY_BLUE, markersize=12, 
             label='Latest Estimated Completion', zorder=3)
    
    # Highlight the current date
    plt.axvline(x=current_date, color=RED, linestyle='--', linewidth=2, 
                label='Current Date', zorder=2)
    
    # Highlight processing timeframe
    plt.axvspan(earliest_date, latest_date, alpha=0.2, color=LIGHT_BLUE, zorder=0)
    
    # Add milestone labels with better positioning
    label_y_positions = {
        filing_date_obj: 1.1,
        earliest_date: 0.9,
        median_date: 1.1,
        latest_date: 0.9,
        current_date: 1.0
    }
    
    label_texts = {
        filing_date_obj: f"Filed: {filing_date_obj.strftime('%b %d, %Y')}",
        earliest_date: f"Earliest: {earliest_date.strftime('%b %d, %Y')}",
        median_date: f"Median: {median_date.strftime('%b %d, %Y')}",
        latest_date: f"Latest: {latest_date.strftime('%b %d, %Y')}",
        current_date: f"Today: {current_date.strftime('%b %d, %Y')}"
    }
    
    for date, y_pos in label_y_positions.items():
        plt.text(date, y_pos, label_texts[date], ha='center', va='center', 
                 fontsize=10, fontweight='bold', 
                 bbox=dict(facecolor='white', alpha=0.8, edgecolor=LIGHT_GRAY, 
                           boxstyle='round,pad=0.5'))
    
    # Improve title and labels
    form_number = timeline_data["form_info"]["form_number"]
    form_description = timeline_data["form_info"]["form_description"]
    service_center = timeline_data["form_info"]["service_center"]
    form_category = timeline_data["form_info"]["form_category"]
    
    # In the plot_timeline function, ensure this line is updated:
    plt.title(f"{form_number} - {form_description}\n{service_center} - {form_category}", 
            fontsize=14, fontweight='bold', color=DARK_BLUE)
    
    # Configure the axes
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['bottom'].set_color(LIGHT_GRAY)
    
    ax.tick_params(axis='x', labelsize=9, colors=DARK_BLUE)
    ax.yaxis.set_visible(False)
    
    # Set date formatter and locator for x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.xticks(rotation=45, ha='right')
    
    # Add progress bar if filing date is in the past
    if current_date > filing_date_obj:
        progress_percent = timeline_data["filing_info"]["progress_percent"]
        status_text = f"Current Status: {timeline_data['case_status']['current_status']} ({progress_percent}% complete)"
        plt.figtext(0.5, 0.02, status_text, ha='center', fontsize=10, fontweight='bold')
    
    # Indicate if case is eligible for inquiry
    if timeline_data["case_status"]["can_submit_inquiry"]:
        inquiry_text = "Case eligible for USCIS inquiry"
        plt.figtext(0.5, 0.06, inquiry_text, ha='center', fontsize=10, 
                   color=GREEN, fontweight='bold')
    
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.15)
    
    # Create directory for charts if it doesn't exist
    charts_folder = current_app.config.get('CHARTS_FOLDER', 'static/charts')
    os.makedirs(charts_folder, exist_ok=True)
    
    # Save chart with form number and date to avoid overwriting previous charts
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    chart_path = f"{charts_folder}/timeline_{form_number}_{timestamp}.png"
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(chart_path), exist_ok=True)
    
    # Save the chart
    try:
        plt.savefig(chart_path)
        plt.close()
        logger.info(f"Successfully generated timeline chart at {chart_path}")
    except Exception as e:
        logger.error(f"Error saving chart to {chart_path}: {e}")
        # Create a fallback path in case there's an issue with the configured path
        fallback_path = f"static/charts/timeline_{form_number}_{timestamp}.png"
        os.makedirs(os.path.dirname(fallback_path), exist_ok=True)
        plt.savefig(fallback_path)
        plt.close()
        logger.info(f"Saved chart to fallback location: {fallback_path}")
        return fallback_path
    
    return chart_path