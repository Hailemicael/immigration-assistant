"""
Database functions for the USCIS Timeline Calculator application.

This module provides functions to create, read, update, and delete data
from the database tables.
"""

import os
import logging
import datetime
from typing import List, Dict, Any, Optional, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import current_app, g

# Configure module-level logger
logger = logging.getLogger(__name__)

def get_db_connection():
    """
    Get a database connection from the connection pool.
    
    Returns:
        A database connection object
    """
    if 'db' not in g:
        g.db = psycopg2.connect(
            host=current_app.config.get('DB_HOST', 'localhost'),
            database=current_app.config.get('DB_NAME', 'uscis_calculator'),
            user=current_app.config.get('DB_USER', 'postgres'),
            password=current_app.config.get('DB_PASSWORD', '12345'),
            cursor_factory=RealDictCursor
        )
    return g.db

def close_db_connection(e=None):
    """
    Close the database connection.
    
    Args:
        e: Optional exception that occurred
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()
def init_db():
    """
    Initialize the database with the schema.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=current_app.config.get('DB_HOST', 'localhost'),
            database=current_app.config.get('DB_NAME', 'uscis_calculator'),
            user=current_app.config.get('DB_USER', 'postgres'),
            password=current_app.config.get('DB_PASSWORD', 'your_password')  # Replace with your password
        )
        
        with conn.cursor() as cursor:
            # Create forms table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS forms (
                    form_id VARCHAR(20) PRIMARY KEY,
                    form_name VARCHAR(255) NOT NULL,
                    description TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create other tables as in your original code...
            
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error initializing database: {e}")
    finally:
        if conn:
            conn.close()
# Form functions
def insert_form(form_id: str, form_name: str, description: str) -> bool:
    """
    Insert a new form or update if it already exists.
    
    Args:
        form_id: Form ID (e.g., I-485)
        form_name: Form name
        description: Form description
    
    Returns:
        True if successful, False otherwise
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO forms (form_id, form_name, description, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (form_id) DO UPDATE
                SET form_name = EXCLUDED.form_name,
                    description = EXCLUDED.description,
                    updated_at = CURRENT_TIMESTAMP
            """, (form_id, form_name, description))
        conn.commit()
        logger.info(f"Successfully inserted/updated form {form_id}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting form {form_id}: {e}")
        return False

def get_all_forms() -> List[Dict[str, Any]]:
    """
    Get all forms from the database.
    
    Returns:
        List of form dictionaries
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM forms ORDER BY form_id")
            forms = cursor.fetchall()
        return forms
    except Exception as e:
        logger.error(f"Error getting forms: {e}")
        return []

def get_form_by_id(form_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a form by ID.
    
    Args:
        form_id: Form ID
    
    Returns:
        Form dictionary or None if not found
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM forms WHERE form_id = %s", (form_id,))
            form = cursor.fetchone()
        return form
    except Exception as e:
        logger.error(f"Error getting form {form_id}: {e}")
        return None

# Service center functions
def insert_service_center(center_name: str, shortcode: Optional[str] = None) -> int:
    """
    Insert a new service center or update if it already exists.
    
    Args:
        center_name: Service center name
        shortcode: Optional shortcode (e.g., CSC for California Service Center)
    
    Returns:
        Center ID if successful, -1 otherwise
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO service_centers (center_name, shortcode, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (center_name) DO UPDATE
                SET shortcode = COALESCE(EXCLUDED.shortcode, service_centers.shortcode),
                    updated_at = CURRENT_TIMESTAMP
                RETURNING center_id
            """, (center_name, shortcode))
            center_id = cursor.fetchone()['center_id']
        conn.commit()
        logger.info(f"Successfully inserted/updated service center {center_name} with ID {center_id}")
        return center_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting service center {center_name}: {e}")
        return -1

def get_all_service_centers() -> List[Dict[str, Any]]:
    """
    Get all service centers from the database.
    
    Returns:
        List of service center dictionaries
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM service_centers ORDER BY center_name")
            centers = cursor.fetchall()
        return centers
    except Exception as e:
        logger.error(f"Error getting service centers: {e}")
        return []

def get_service_center_by_name(center_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a service center by name.
    
    Args:
        center_name: Service center name
    
    Returns:
        Service center dictionary or None if not found
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM service_centers WHERE center_name = %s", (center_name,))
            center = cursor.fetchone()
        return center
    except Exception as e:
        logger.error(f"Error getting service center {center_name}: {e}")
        return None

# Form category functions
def insert_form_category(form_id: str, category_name: str) -> int:
    """
    Insert a new form category or update if it already exists.
    
    Args:
        form_id: Form ID
        category_name: Category name
    
    Returns:
        Category ID if successful, -1 otherwise
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO form_categories (form_id, category_name, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (form_id, category_name) DO UPDATE
                SET updated_at = CURRENT_TIMESTAMP
                RETURNING category_id
            """, (form_id, category_name))
            category_id = cursor.fetchone()['category_id']
        conn.commit()
        logger.info(f"Successfully inserted/updated category {category_name} for form {form_id} with ID {category_id}")
        return category_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting category {category_name} for form {form_id}: {e}")
        return -1

def get_categories_by_form_id(form_id: str) -> List[Dict[str, Any]]:
    """
    Get all categories for a specific form.
    
    Args:
        form_id: Form ID
    
    Returns:
        List of category dictionaries
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT * FROM form_categories 
                WHERE form_id = %s 
                ORDER BY category_name
            """, (form_id,))
            categories = cursor.fetchall()
        return categories
    except Exception as e:
        logger.error(f"Error getting categories for form {form_id}: {e}")
        return []

# Processing time functions
def insert_processing_time(
    form_id: str, 
    center_id: int, 
    category_id: Optional[int], 
    min_months: float, 
    median_months: float, 
    max_months: float,
    last_updated: datetime.datetime
) -> int:
    """
    Insert a new processing time or update if it already exists.
    Sets the active flag to True and any previous entries to False.
    
    Args:
        form_id: Form ID
        center_id: Service center ID
        category_id: Category ID (optional)
        min_months: Minimum processing time in months
        median_months: Median processing time in months
        max_months: Maximum processing time in months
        last_updated: Last updated timestamp
    
    Returns:
        Processing time ID if successful, -1 otherwise
    """
    conn = get_db_connection()
    try:
        # Calculate receipt date for inquiry (max_months converted to days)
        receipt_date = datetime.datetime.now() - datetime.timedelta(days=int(max_months * 30.5))
        
        # First, deactivate any existing active records for this combination
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE processing_times
                SET active = FALSE, updated_at = CURRENT_TIMESTAMP
                WHERE form_id = %s AND center_id = %s AND 
                      (category_id = %s OR (category_id IS NULL AND %s IS NULL)) AND
                      active = TRUE
            """, (form_id, center_id, category_id, category_id))
        
        # Insert the new processing time
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO processing_times 
                (form_id, center_id, category_id, min_months, median_months, max_months, 
                 last_updated, receipt_date_for_inquiry, active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
                RETURNING time_id
            """, (form_id, center_id, category_id, min_months, median_months, max_months, 
                  last_updated, receipt_date))
            time_id = cursor.fetchone()['time_id']
        
        conn.commit()
        logger.info(f"Successfully inserted processing time for {form_id} at center {center_id} with ID {time_id}")
        return time_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting processing time for {form_id} at center {center_id}: {e}")
        return -1

def get_processing_time(
    form_id: str, 
    center_id: int, 
    category_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Get the active processing time for a form, service center, and category.
    
    Args:
        form_id: Form ID
        center_id: Service center ID
        category_id: Category ID (optional)
    
    Returns:
        Processing time dictionary or None if not found
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT pt.*, f.form_name, f.description as form_description, 
                       sc.center_name, fc.category_name
                FROM processing_times pt
                JOIN forms f ON pt.form_id = f.form_id
                JOIN service_centers sc ON pt.center_id = sc.center_id
                LEFT JOIN form_categories fc ON pt.category_id = fc.category_id
                WHERE pt.form_id = %s AND pt.center_id = %s AND 
                      (pt.category_id = %s OR (pt.category_id IS NULL AND %s IS NULL)) AND
                      pt.active = TRUE
            """, (form_id, center_id, category_id, category_id))
            processing_time = cursor.fetchone()
        return processing_time
    except Exception as e:
        logger.error(f"Error getting processing time for {form_id} at center {center_id}: {e}")
        return None

def get_processing_times_by_form(form_id: str) -> List[Dict[str, Any]]:
    """
    Get all active processing times for a specific form.
    
    Args:
        form_id: Form ID
    
    Returns:
        List of processing time dictionaries
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT pt.*, f.form_name, f.description as form_description, 
                       sc.center_name, fc.category_name
                FROM processing_times pt
                JOIN forms f ON pt.form_id = f.form_id
                JOIN service_centers sc ON pt.center_id = sc.center_id
                LEFT JOIN form_categories fc ON pt.category_id = fc.category_id
                WHERE pt.form_id = %s AND pt.active = TRUE
                ORDER BY sc.center_name, fc.category_name
            """, (form_id,))
            processing_times = cursor.fetchall()
        return processing_times
    except Exception as e:
        logger.error(f"Error getting processing times for form {form_id}: {e}")
        return []

# User timeline functions
def insert_user_timeline(
    form_id: str,
    center_id: int,
    category_id: Optional[int],
    filing_date: datetime.date,
    earliest_completion_date: datetime.date,
    median_completion_date: datetime.date,
    latest_completion_date: datetime.date,
    chart_path: Optional[str] = None,
    user_ip: Optional[str] = None
) -> int:
    """
    Insert a user timeline calculation.
    
    Args:
        form_id: Form ID
        center_id: Service center ID
        category_id: Category ID (optional)
        filing_date: Filing date
        earliest_completion_date: Earliest estimated completion date
        median_completion_date: Median estimated completion date
        latest_completion_date: Latest estimated completion date
        chart_path: Path to the chart image (optional)
        user_ip: User IP address (optional)
    
    Returns:
        Timeline ID if successful, -1 otherwise
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_timelines
                (form_id, center_id, category_id, filing_date, earliest_completion_date,
                 median_completion_date, latest_completion_date, chart_path, user_ip)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING timeline_id
            """, (form_id, center_id, category_id, filing_date, earliest_completion_date,
                  median_completion_date, latest_completion_date, chart_path, user_ip))
            timeline_id = cursor.fetchone()['timeline_id']
        conn.commit()
        logger.info(f"Successfully inserted user timeline for {form_id} with ID {timeline_id}")
        return timeline_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error inserting user timeline for {form_id}: {e}")
        return -1

def get_user_timeline(timeline_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a user timeline by ID.
    
    Args:
        timeline_id: Timeline ID
    
    Returns:
        Timeline dictionary or None if not found
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT ut.*, f.form_name, f.description as form_description, 
                       sc.center_name, fc.category_name
                FROM user_timelines ut
                JOIN forms f ON ut.form_id = f.form_id
                JOIN service_centers sc ON ut.center_id = sc.center_id
                LEFT JOIN form_categories fc ON ut.category_id = fc.category_id
                WHERE ut.timeline_id = %s
            """, (timeline_id,))
            timeline = cursor.fetchone()
        return timeline
    except Exception as e:
        logger.error(f"Error getting user timeline {timeline_id}: {e}")
        return None

# Data import functions
def bulk_import_processing_times(data: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Bulk import processing time data from a list of dictionaries.
    
    Args:
        data: List of dictionaries with processing time data
    
    Returns:
        Tuple of (success_count, error_count)
    """
    success_count = 0
    error_count = 0
    
    for item in data:
        try:
            # Extract data
            form_number = item.get('form_number')
            form_description = item.get('form_description')
            service_center_name = item.get('service_center')
            min_months = float(item.get('min_months', 0))
            median_months = float(item.get('median_months', 0))
            max_months = float(item.get('max_months', 0))
            
            # Parse last_updated date
            last_updated_str = item.get('last_updated')
            try:
                last_updated = datetime.datetime.strptime(last_updated_str, '%B %d, %Y')
            except (ValueError, TypeError):
                last_updated = datetime.datetime.now()
            
            # First ensure the form exists
            if not insert_form(form_number, form_number, form_description):
                error_count += 1
                continue
            
            # Ensure the service center exists
            center_id = insert_service_center(service_center_name)
            if center_id == -1:
                error_count += 1
                continue
            
            # Insert the processing time
            time_id = insert_processing_time(
                form_number, center_id, None, min_months, median_months, 
                max_months, last_updated
            )
            
            if time_id != -1:
                success_count += 1
            else:
                error_count += 1
        
        except Exception as e:
            logger.error(f"Error importing processing time data: {e}")
            error_count += 1
    
    return (success_count, error_count)

def import_form_categories(form_categories: Dict[str, List[str]]) -> Tuple[int, int]:
    """
    Import form categories from a dictionary.
    
    Args:
        form_categories: Dictionary with form ID as key and list of categories as value
    
    Returns:
        Tuple of (success_count, error_count)
    """
    success_count = 0
    error_count = 0
    
    for form_id, categories in form_categories.items():
        # Ensure the form exists (even with minimal data)
        if not insert_form(form_id, form_id, form_id):
            error_count += len(categories)
            continue
        
        for category in categories:
            category_id = insert_form_category(form_id, category)
            if category_id != -1:
                success_count += 1
            else:
                error_count += 1
    
    return (success_count, error_count)

def get_filtered_data_from_db(form_number=None, service_center=None) -> List[Dict[str, Any]]:
    """
    Get filtered processing time data from the database.
    
    Args:
        form_number: Optional filter for form number
        service_center: Optional filter for service center
    
    Returns:
        List of dictionaries with processing time data
    """
    conn = get_db_connection()
    result = []
    
    try:
        query = """
            SELECT pt.*, f.form_name, f.description as form_description, 
                  sc.center_name, fc.category_name
            FROM processing_times pt
            JOIN forms f ON pt.form_id = f.form_id
            JOIN service_centers sc ON pt.center_id = sc.center_id
            LEFT JOIN form_categories fc ON pt.category_id = fc.category_id
            WHERE pt.active = TRUE
        """
        params = []
        
        if form_number:
            query += " AND pt.form_id = %s"
            params.append(form_number)
        
        if service_center:
            query += " AND sc.center_name ILIKE %s"
            params.append(f"%{service_center}%")
        
        query += " ORDER BY f.form_id, sc.center_name"
        
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            processing_times = cursor.fetchall()
        
        # Convert database records to the expected format
        for pt in processing_times:
            result.append({
                "form_number": pt["form_id"],
                "form_description": pt["form_description"],
                "service_center": pt["center_name"],
                "min_months": float(pt["min_months"]),
                "median_months": float(pt["median_months"]),
                "max_months": float(pt["max_months"]),
                "last_updated": pt["last_updated"].strftime("%B %d, %Y"),
                "receipt_date_for_inquiry": pt["receipt_date_for_inquiry"].strftime("%B %d, %Y") if pt["receipt_date_for_inquiry"] else None
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting filtered data from database: {e}")
        return []