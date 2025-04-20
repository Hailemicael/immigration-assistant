"""
Route definitions for the USCIS Timeline Calculator application.

This module defines all routes for the web interface and API endpoints.
"""

import os
from flask import (
    Blueprint, render_template, request, jsonify, current_app,
    abort, send_from_directory, redirect, url_for, flash, send_file
)

from uscis.services.scraping import get_filtered_data, find_unique_values
from uscis.services.timeline import generate_timeline
from uscis.services.visualization import plot_timeline

# Database imports
from uscis.services.database import (
    get_all_forms, get_all_service_centers, get_categories_by_form_id,
    get_service_center_by_name, insert_user_timeline, get_user_timeline
)

# Create blueprints for main routes and API endpoints
main = Blueprint('main', __name__)
api = Blueprint('api', __name__)


# Main routes
@main.route('/')
def index():
    """Render the home page."""
    return render_template('index.html')


@main.route('/calculator', methods=['GET'])
def calculator():
    """Render the calculator form page."""
    try:
        # Get data from database
        forms = get_all_forms()
        form_options = [
            {"value": form["form_id"], "label": f"{form['form_id']} - {form['description']}"}
            for form in forms
        ]
        
        # Get form categories for each form
        form_categories = {}
        for form in forms:
            form_id = form["form_id"]
            categories = get_categories_by_form_id(form_id)
            if categories:
                form_categories[form_id] = [cat["category_name"] for cat in categories]
        
        # Get all service centers
        centers = get_all_service_centers()
        service_centers = [center["center_name"] for center in centers]
        
        return render_template(
            'calculator.html',
            form_options=form_options,
            form_categories=form_categories,
            service_centers=service_centers
        )
    except Exception as e:
        current_app.logger.error(f"Error loading calculator page: {e}")
        
        # Fallback to hardcoded values if database query fails
        form_options = [
            {"value": "I-90", "label": "I-90 - Application to Replace Permanent Resident Card"},
            {"value": "I-102", "label": "I-102 - Application for Replacement/Initial Nonimmigrant Arrival-Departure Document"},
            {"value": "I-129", "label": "I-129 - Petition for a Nonimmigrant Worker"},
            {"value": "I-129CW", "label": "I-129CW - Petition for a CNMI-Only Nonimmigrant Transitional Worker"},
            {"value": "I-129F", "label": "I-129F - Petition for Alien Fiancé(e)"},
            {"value": "I-130", "label": "I-130 - Petition for Alien Relative"},
            {"value": "I-131", "label": "I-131 - Application for Travel Documents"},
            {"value": "I-140", "label": "I-140 - Immigrant Petition for Alien Workers"},
            {"value": "I-485", "label": "I-485 - Application to Register Permanent Residence or Adjust Status"},
            {"value": "I-751", "label": "I-751 - Petition to Remove Conditions on Residence"},
            {"value": "I-765", "label": "I-765 - Application for Employment Authorization"},
            {"value": "N-400", "label": "N-400 - Application for Naturalization"}
        ]
        
        # Hardcoded form categories
        form_categories = {
            "I-130": ["Family-based: Immediate relative", "Family-based: F1", "Family-based: F2A", "Family-based: F2B", "Family-based: F3", "Family-based: F4"],
            "I-485": ["Family-based", "Employment-based", "Special Immigrant", "Asylee/Refugee", "VAWA"],
            "I-765": ["Initial EAD", "Renewal EAD", "Replacement EAD"],
            "I-90": ["Renewal/Replacement", "Biometric Update"],
            "N-400": ["Military", "Non-Military"]
        }
        
        # Hardcoded service centers
        service_centers = [
            "California Service Center",
            "Nebraska Service Center",
            "Potomac Service Center",
            "Texas Service Center",
            "Vermont Service Center",
            "National Benefits Center",
            "Chicago Lockbox",
            "Dallas Lockbox",
            "Phoenix Lockbox"
        ]
        
        return render_template(
            'calculator.html',
            form_options=form_options,
            form_categories=form_categories,
            service_centers=service_centers
        )
@main.route('/calculate', methods=['POST'])
def calculate():
    """Process the calculator form and display results."""
    try:
        # Extract form data
        form_number = request.form.get('form_number', '')
        form_category = request.form.get('form_category', '')
        service_center = request.form.get('service_center', '')
        filing_date = request.form.get('filing_date', '')
        
        # Validate required fields
        if not form_number or not service_center or not filing_date:
            flash('Please complete all required fields.', 'danger')
            return redirect(url_for('main.calculator'))
        
        # Get data matching the form number and service center
        matched_items = get_filtered_data(form_number, service_center)
        
        if not matched_items:
            flash('No data found for the specified form type and service center.', 'danger')
            return redirect(url_for('main.calculator'))
        
        # If multiple service centers match but none was specified, use the first one
        data_item = matched_items[0]
        
        # Generate timeline and chart
        timeline = generate_timeline(data_item, filing_date, form_category)
        chart_path = plot_timeline(timeline, filing_date)
        
        # Extract filename from path
        chart_filename = os.path.basename(chart_path)
        
        current_app.logger.info(f"Generated chart: {chart_path}")
        
        # Store the timeline in the database
        try:
            # Get service center ID
            center_info = get_service_center_by_name(service_center)
            if center_info:
                center_id = center_info["center_id"]
                
                # Get category ID if applicable
                category_id = None
                if form_category:
                    categories = get_categories_by_form_id(form_number)
                    for cat in categories:
                        if cat["category_name"] == form_category:
                            category_id = cat["category_id"]
                            break
                
                # Parse filing date
                import datetime
                filing_date_obj = datetime.datetime.strptime(filing_date, "%Y-%m-%d")
                
                # Parse completion dates
                earliest_date = datetime.datetime.strptime(
                    timeline["estimated_timeline"]["earliest_date"], "%B %d, %Y")
                median_date = datetime.datetime.strptime(
                    timeline["estimated_timeline"]["median_date"], "%B %d, %Y")
                latest_date = datetime.datetime.strptime(
                    timeline["estimated_timeline"]["latest_date"], "%B %d, %Y")
                
                # Get user IP (if available)
                user_ip = request.remote_addr if request else None
                
                # Insert into database
                insert_user_timeline(
                    form_id=form_number,
                    center_id=center_id,
                    category_id=category_id,
                    filing_date=filing_date_obj.date(),
                    earliest_completion_date=earliest_date.date(),
                    median_completion_date=median_date.date(),
                    latest_completion_date=latest_date.date(),
                    chart_path=chart_path,
                    user_ip=user_ip
                )
        except Exception as e:
            current_app.logger.error(f"Error saving timeline to database: {e}")
            # Continue without database save
        
        # Render the results template
        return render_template(
            'results.html',
            timeline=timeline,
            chart_url=chart_filename
        )
        
    except Exception as e:
        current_app.logger.error(f"Error in calculate route: {e}")
        flash(f'An error occurred: {str(e)}', 'danger')
        return redirect(url_for('main.calculator'))


@main.route('/charts/<filename>')
def serve_chart(filename):
    """
    Serve timeline chart images.
    
    This route handles serving the generated timeline chart images.
    """
    charts_folder = current_app.config.get('CHARTS_FOLDER', 'static/charts')
    current_app.logger.info(f"Serving chart from {charts_folder}/{filename}")
    
    try:
        return send_from_directory(os.path.abspath(charts_folder), filename)
    except FileNotFoundError:
        current_app.logger.error(f"Chart file not found: {filename}")
        # Return a fallback image or error message
        return send_from_directory('static', 'images/chart-error.png')


@main.route('/about')
def about():
    """Render the about page with USCIS processing time methodology information."""
    return render_template('about.html')


# API endpoints
@api.route('/processing-times', methods=['GET'])
def api_processing_times():
    """
    API endpoint to get processing time data.
    
    Query parameters:
        form_number: Optional filter for form number
        service_center: Optional filter for service center
    
    Returns:
        JSON response with filtered processing time data
    """
    form_number = request.args.get('form_number', '')
    service_center = request.args.get('service_center', '')
    
    # Get filtered data
    filtered_data = get_filtered_data(form_number, service_center)
    
    return jsonify({
        'success': True,
        'data': filtered_data
    })


@api.route('/form-options', methods=['GET'])
def api_form_options():
    """
    API endpoint to get available form options and service centers.
    
    Returns:
        JSON response with form options and service centers
    """
    try:
        # Get data from database
        from uscis.services.database import get_all_forms, get_all_service_centers, get_categories_by_form_id
        
        forms = get_all_forms()
        form_options = [
            {"value": form["form_id"], "label": f"{form['form_id']} - {form['description']}"}
            for form in forms
        ]
        
        # Get form categories for each form
        form_categories = {}
        for form in forms:
            form_id = form["form_id"]
            categories = get_categories_by_form_id(form_id)
            if categories:
                form_categories[form_id] = [cat["category_name"] for cat in categories]
        
        # Get all service centers
        centers = get_all_service_centers()
        service_centers = [center["center_name"] for center in centers]
        
        return jsonify({
            'success': True,
            'form_options': form_options,
            'form_categories': form_categories,
            'service_centers': service_centers
        })
    except Exception as e:
        current_app.logger.error(f"Error in api_form_options: {e}")
        
        # Fall back to hardcoded values if database query fails
        form_options = [
            {"value": "I-90", "label": "I-90 - Application to Replace Permanent Resident Card"},
            {"value": "I-102", "label": "I-102 - Application for Replacement/Initial Nonimmigrant Arrival-Departure Document"},
            {"value": "I-129", "label": "I-129 - Petition for a Nonimmigrant Worker"},
            {"value": "I-129CW", "label": "I-129CW - Petition for a CNMI-Only Nonimmigrant Transitional Worker"},
            {"value": "I-129F", "label": "I-129F - Petition for Alien Fiancé(e)"},
            {"value": "I-130", "label": "I-130 - Petition for Alien Relative"},
            {"value": "I-131", "label": "I-131 - Application for Travel Documents"},
            {"value": "I-140", "label": "I-140 - Immigrant Petition for Alien Workers"},
            {"value": "I-485", "label": "I-485 - Application to Register Permanent Residence or Adjust Status"},
            {"value": "I-751", "label": "I-751 - Petition to Remove Conditions on Residence"},
            {"value": "I-765", "label": "I-765 - Application for Employment Authorization"},
            {"value": "N-400", "label": "N-400 - Application for Naturalization"}
        ]
        
        # Hardcoded form categories
        form_categories = {
            "I-130": ["Family-based: Immediate relative", "Family-based: F1", "Family-based: F2A", "Family-based: F2B", "Family-based: F3", "Family-based: F4"],
            "I-485": ["Family-based", "Employment-based", "Special Immigrant", "Asylee/Refugee", "VAWA"],
            "I-765": ["Initial EAD", "Renewal EAD", "Replacement EAD"],
            "I-90": ["Renewal/Replacement", "Biometric Update"],
            "N-400": ["Military", "Non-Military"]
        }
        
        # Hardcoded service centers
        service_centers = [
            "California Service Center",
            "Nebraska Service Center",
            "Potomac Service Center",
            "Texas Service Center",
            "Vermont Service Center",
            "National Benefits Center",
            "Chicago Lockbox",
            "Dallas Lockbox",
            "Phoenix Lockbox"
        ]
        
        return jsonify({
            'success': True,
            'form_options': form_options,
            'form_categories': form_categories,
            'service_centers': service_centers
        })