"""
USCIS Timeline Calculator Application

This is the main entry point for the USCIS Timeline Calculator application,
which provides estimated processing timelines for various USCIS forms.
"""

import os
from uscis import create_app

# Create application instance with appropriate configuration
app = create_app(os.getenv('FLASK_CONFIG', 'default'))

if __name__ == '__main__':
    # Run the application with debug mode enabled for development
    app.run(debug=True, port = 8080)