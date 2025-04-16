import os
import logging
import threading
import time
from flask import Flask, render_template, session, g, redirect, url_for
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import blueprints and utility functions
from auth import auth_bp
from routes.app_routes import app_bp
from routes.build_routes import build_bp
from routes.api_routes import api_bp
from routes.notification_routes import notification_bp
from models import check_abandoned_builds
import database as db

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'development-key')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max upload size

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(app_bp)
app.register_blueprint(build_bp)
app.register_blueprint(api_bp)
app.register_blueprint(notification_bp, url_prefix='/api')

# Root route redirects to app index
@app.route('/')
def index():
    return redirect(url_for('app.index'))

# Template filter for formatting dates
@app.template_filter('format_date')
def format_date(date_string):
    """
    Format ISO date strings to DD-MMM-YYYY format
    Example: 2023-04-15T10:30:00 -> 15-Apr-2023
    """
    if not date_string:
        return "N/A"
    try:
        # Parse the ISO format date
        if 'T' in date_string:
            date_part = date_string.split('T')[0]
        else:
            date_part = date_string
            
        # Parse the date part
        year, month, day = map(int, date_part.split('-'))
        
        # Format to DD-MMM-YYYY
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{day:02d}-{months[month-1]}-{year}"
    except Exception as e:
        logging.warning(f"Error formatting date '{date_string}': {str(e)}")
        return date_string

# Global request handler
@app.before_request
def load_logged_in_user():
    username = session.get('username')
    if username is None:
        g.user = None
        g.unread_notifications = 0
    else:
        g.user = db.get_user(username)
        g.unread_notifications = db.get_unread_notification_count(username)

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# Background tasks
def background_tasks():
    """Run background tasks periodically"""
    while True:
        try:
            check_abandoned_builds()
        except Exception as e:
            logging.error(f"Error in background task: {str(e)}")
        
        # Sleep for 5 minutes
        time.sleep(300)

# Initialize database and start background tasks
def initialize_app():
    # Initialize database
    db.initialize_db()
    
    # Start background tasks in a separate thread
    bg_thread = threading.Thread(target=background_tasks)
    bg_thread.daemon = True
    bg_thread.start()
    
    logging.info("App initialized successfully")

# Initialize when the app starts
initialize_app()

# Main entry point
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug='true', ssl_context=('cert.pem', 'key.pem')) 