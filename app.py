import os
import json
import uuid
import shutil
import tempfile
import subprocess
import threading
import requests
import time
import zipfile
import plistlib
import sys
import logging
import traceback
import io
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify, session, g, send_file, Response, make_response
from dotenv import load_dotenv

from werkzeug.utils import secure_filename
from zipfile import ZipFile

from PIL import Image
import base64
import io
import re

# Import database module
import database as db

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'development-key')

# Configuration
ALLOWED_EXTENSIONS = {'ipa'}
APPLE_TEAM_ID = os.environ.get('APPLE_TEAM_ID', '')  # Get from environment variable
GITHUB_REPO_URL = os.environ.get('GITHUB_REPO_URL', 'https://github.com/username/app-dist')  # GitHub repository URL

# Max content length increased for larger file uploads
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max upload size

# Build files are now stored in MongoDB instead of the local filesystem
# This improves scalability and avoids issues with local storage

# Initialize database
db.initialize_db()

# GitHub API tokens for higher rate limits (optional)
GITHUB_API_TOKEN = os.environ.get('GITHUB_API_TOKEN', '')
GITHUB_USERNAME = os.environ.get('GITHUB_USERNAME', '')

# Template filter for formatting dates as DD-MMM-YYYY
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

def get_github_repo_url():
    """
    Tries to determine the GitHub repository URL for this project.
    
    Returns:
        str: GitHub repository URL or default value
    """
    try:
        # Try to get from environment variable first (useful for GitHub Actions)
        if 'GITHUB_REPOSITORY' in os.environ:
            return f"https://github.com/{os.environ['GITHUB_REPOSITORY']}"
            
        # Try to get from git config
        result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            url = result.stdout.strip()
            # Convert SSH URL to HTTPS if needed
            if url.startswith('git@github.com:'):
                url = url.replace('git@github.com:', 'https://github.com/')
            
            # Remove .git suffix if present
            if url.endswith('.git'):
                url = url[:-4]
                
            return url
    except Exception as e:
        logging.warning(f"Could not determine GitHub repository URL: {str(e)}")
        
    # Return default from environment or hardcoded value
    return GITHUB_REPO_URL

def load_default_icon():
    """
    Loads the default app icon and returns it as a base64 encoded string.
    Tries multiple locations and falls back to a transparent pixel if all fail.
    
    Returns:
        str: A data URL containing the base64 encoded image
    """
    # First try from the root directory using absolute path
    try:
        default_icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'defaultApp.png')
        with open(default_icon_path, 'rb') as f:
            icon_data = f.read()
            icon_b64 = base64.b64encode(icon_data).decode()
            logging.info(f"Successfully loaded default icon ({len(icon_data)} bytes)")
            return f"data:image/png;base64,{icon_b64}"
    except Exception as e:
        logging.error(f"Error loading default icon from absolute path: {str(e)}")
    
    # Try from the current directory as a fallback
    try:
        with open('defaultApp.png', 'rb') as f:
            icon_data = f.read()
            icon_b64 = base64.b64encode(icon_data).decode()
            logging.info(f"Successfully loaded default icon from current directory ({len(icon_data)} bytes)")
            return f"data:image/png;base64,{icon_b64}"
    except Exception as e:
        logging.error(f"Error loading default icon from current directory: {str(e)}")
    
    # Last resort fallback to transparent pixel
    logging.warning("Using fallback transparent pixel as icon due to inability to load defaultApp.png")
    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

def update_build_status(build_id, status, log=None, end_time=None):
    """
    Update the status of a build in the database
    
    Args:
        build_id (str): The ID of the build to update
        status (str): The new status (queued, in_progress, completed, failed, cancelled)
        log (str, optional): The build log to append
        end_time (str, optional): The end time of the build
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get the build first
    build = db.get_build(build_id)
    if not build:
        return False
    
    # Prepare updates    
    if log is not None:
        # Let the database function handle the log update directly
        # to avoid recursive calls
        result = db.update_build_status(build_id, status, log, end_time)
        return result
    
    # For updates without log changes
    build['status'] = status
    
    if end_time is not None:
        build['end_time'] = end_time
    
    # Save the build with updates    
    db.save_build(build)
    return True

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page')
            return redirect(url_for('login', next=request.url))
        
        user = db.get_user(session['username'])
        if not user or user['role'] != 'admin':
            flash('Admin privileges required')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_app_info(file_data, filename):
    """Extract app information from IPA file data"""
    app_id = str(uuid.uuid4())
    file_id = str(uuid.uuid4())
    
    # Create a temporary file to work with the data
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(file_data)
        temp_path = temp_file.name
    
    try:
        # Extract info from IPA file
        with zipfile.ZipFile(temp_path, 'r') as ipa:
            # Find Info.plist path
            plist_path = None
            for f in ipa.namelist():
                if 'Info.plist' in f:
                    plist_path = f
                    break
                    
            if plist_path:
                with ipa.open(plist_path) as plist_file:
                    plist_data = plistlib.load(plist_file)
                    app_name = plist_data.get('CFBundleDisplayName', plist_data.get('CFBundleName', filename.split('.')[0]))
                    version = plist_data.get('CFBundleShortVersionString', '1.0.0')
                    bundle_id = plist_data.get('CFBundleIdentifier', '')
            else:
                app_name = filename.split('.')[0]
                version = '1.0.0'
                bundle_id = ''
                
            # Try to extract app icon
            icon_path = None
            for f in ipa.namelist():
                if 'AppIcon60x60@2x.png' in f:
                    icon_path = f
                    break
                    
            if icon_path:
                with ipa.open(icon_path) as icon_file:
                    icon_data = icon_file.read()
                    icon_b64 = base64.b64encode(icon_data).decode()
                    icon = f"data:image/png;base64,{icon_b64}"
            else:
                # Use defaultApp.png as fallback
                icon = load_default_icon()
    finally:
        # Clean up the temporary file
        os.unlink(temp_path)
    
    # Store the file in MongoDB
    db.save_file(file_id, filename, file_data, 'application/octet-stream')
    
    return {
        "id": app_id,
        "name": app_name,
        "version": version,
        "bundle_id": bundle_id,
        "file_id": file_id,
        "filename": filename,
        "upload_date": datetime.now().isoformat(),
        "size": len(file_data),
        "icon": icon,
        "versions": [{
            "version": version,
            "file_id": file_id,
            "filename": filename,
            "upload_date": datetime.now().isoformat(),
            "size": len(file_data)
        }]
    }

def add_app_version(app_id, file_data, filename, version=None):
    """Add a new version to an existing app"""
    app = db.get_app(app_id)
    if not app:
        return None

    file_id = str(uuid.uuid4())
    
    # Create a temporary file to work with the data
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file.write(file_data)
        temp_path = temp_file.name
    
    try:
        # If version is not provided, extract it from the IPA
        if version is None:
            try:
                with zipfile.ZipFile(temp_path, 'r') as ipa:
                    plist_path = None
                    for f in ipa.namelist():
                        if 'Info.plist' in f:
                            plist_path = f
                            break
                            
                    if plist_path:
                        with ipa.open(plist_path) as plist_file:
                            plist_data = plistlib.load(plist_file)
                            version = plist_data.get('CFBundleShortVersionString', '1.0.0')
                    else:
                        version = "1.0.0"
            except Exception as e:
                logging.error(f"Error extracting version from IPA: {str(e)}")
                version = "1.0.0"
    finally:
        # Clean up the temporary file
        os.unlink(temp_path)
    
    # Store the file in MongoDB
    db.save_file(file_id, filename, file_data, 'application/octet-stream')
    
    # Update app with new version
    app['version'] = version
    app['file_id'] = file_id
    app['filename'] = filename
    app['size'] = len(file_data)
    
    # Add to versions history
    app['versions'].append({
        "version": version,
        "file_id": file_id,
        "filename": filename,
        "upload_date": datetime.now().isoformat(),
        "size": len(file_data)
    })
    
    # Save updated app to database
    db.save_app(app)
    return app

# Build from GitHub repo function
def build_ios_app_from_github(build_id, repo_url, branch, app_name, build_config='Release', 
                            certificate_path=None, provisioning_profile=None):
    """Build an iOS app from a GitHub repository"""
    try:
        # Ensure proper logging is set up
        logging.basicConfig(level=logging.DEBUG)
        
        # Log all input parameters for debugging
        logging.info(f"Starting build with parameters: build_id={build_id}, repo_url={repo_url}, branch={branch}, app_name={app_name}")
        logging.info(f"Build config: {build_config}, certificate_path: {certificate_path}, provisioning_profile: {provisioning_profile}")
        
        # Log current working directory and Python executable path
        logging.info(f"Current working directory: {os.getcwd()}")
        logging.info(f"Python executable: {sys.executable}")
        
        # Update build status to "building"
        db.update_build_status(build_id, 'building', f"Starting build process for {repo_url} (branch: {branch})\n")
        
        # Create a temporary local directory for the build process
        # We still need a local temp directory for git operations
        with tempfile.TemporaryDirectory() as build_dir:
            logging.info(f"Created temporary build directory: {build_dir}")
            
            # Verify git is installed and accessible
            try:
                git_version = subprocess.run(['git', '--version'], capture_output=True, text=True, check=True)
                logging.info(f"Git version: {git_version.stdout.strip()}")
            except Exception as e:
                error_msg = f"Git command not found. Make sure git is installed and in PATH: {str(e)}"
                logging.error(error_msg)
                db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
                return
            
            # Clone the repository
            db.update_build_status(build_id, 'building', f"Cloning repository {repo_url}...\n")
            try:
                # Use subprocess for git operations for better error messages
                clone_cmd = ['git', 'clone', '--branch', branch, repo_url, build_dir]
                logging.info(f"Running git clone command: {' '.join(clone_cmd)}")
                
                clone_process = subprocess.run(
                    clone_cmd,
                    capture_output=True,
                    text=True
                )
                
                if clone_process.returncode != 0:
                    error_msg = f"Failed to clone repository: {clone_process.stderr}\n"
                    logging.error(error_msg)
                    db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
                    return
                    
                db.update_build_status(build_id, 'building', f"Repository cloned successfully\n")
            except Exception as e:
                error_msg = f"Failed to clone repository: {str(e)}\n{traceback.format_exc()}"
                logging.error(error_msg)
                db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
                return
            
            # Verify build directory contents and store important files in MongoDB
            try:
                logging.info(f"Listing build directory contents: {build_dir}")
                for root, dirs, files in os.walk(build_dir):
                    relative_path = os.path.relpath(root, build_dir)
                    logging.info(f"Directory: {relative_path}")
                    
                    # Store important files like Xcode project files, source code, etc.
                    for f in files:
                        file_path = os.path.join(root, f)
                        rel_path = os.path.relpath(file_path, build_dir)
                        
                        # Skip .git directory files
                        if '.git/' in rel_path.replace('\\', '/'):
                            continue
                            
                        # Skip large binary files to avoid database bloat
                        # Only store source code and project files
                        if f.endswith(('.swift', '.h', '.m', '.c', '.cpp', '.mm', '.pbxproj', '.xcscheme', '.plist')):
                            try:
                                with open(file_path, 'rb') as file_obj:
                                    file_data = file_obj.read()
                                    # Store in MongoDB
                                    db.save_build_file(build_id, rel_path, file_data)
                                    logging.info(f"  Stored file in MongoDB: {rel_path}")
                            except Exception as e:
                                logging.warning(f"  Error storing file {rel_path}: {str(e)}")
            except Exception as e:
                logging.warning(f"Error processing directory contents: {str(e)}")
            
            # Find Xcode project files
            xcodeproj_files = []
            xcworkspace_files = []
            
            for root, dirs, files in os.walk(build_dir):
                for dir_name in dirs:
                    if dir_name.endswith('.xcodeproj'):
                        xcodeproj_files.append(os.path.join(root, dir_name))
                    elif dir_name.endswith('.xcworkspace'):
                        xcworkspace_files.append(os.path.join(root, dir_name))
            
            # Debug output
            db.update_build_status(build_id, 'building', f"Found Xcode project files: {xcodeproj_files}\n")
            db.update_build_status(build_id, 'building', f"Found Xcode workspace files: {xcworkspace_files}\n")
            
            # Check if we have any Xcode project files
            if not xcodeproj_files and not xcworkspace_files:
                error_msg = "No Xcode project or workspace files found in the repository\n"
                logging.error(error_msg)
                db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
                return
            
            # Determine which file to use (prefer workspace if available)
            build_file = None
            build_type = None
            
            if xcworkspace_files:
                build_file = xcworkspace_files[0]
                build_type = 'workspace'
                db.update_build_status(build_id, 'building', f"Using workspace: {build_file}\n")
            else:
                build_file = xcodeproj_files[0]
                build_type = 'project'
                db.update_build_status(build_id, 'building', f"Using project: {build_file}\n")
                
            # Rest of the build process...
            # If certificate and provisioning profile paths are provided, retrieve from MongoDB
            if certificate_path:
                try:
                    cert_file = db.get_build_file(build_id, file_path=certificate_path)
                    if cert_file and 'data' in cert_file:
                        temp_cert_path = os.path.join(build_dir, "cert.p12")
                        with open(temp_cert_path, 'wb') as f:
                            f.write(cert_file['data'])
                        certificate_path = temp_cert_path
                        logging.info(f"Retrieved certificate from MongoDB and saved to {certificate_path}")
                    else:
                        logging.warning("Certificate not found in MongoDB")
                        certificate_path = None
                except Exception as e:
                    logging.error(f"Error retrieving certificate: {str(e)}")
                    certificate_path = None
            
            if provisioning_profile:
                try:
                    profile_file = db.get_build_file(build_id, file_path=provisioning_profile)
                    if profile_file and 'data' in profile_file:
                        temp_profile_path = os.path.join(build_dir, "profile.mobileprovision")
                        with open(temp_profile_path, 'wb') as f:
                            f.write(profile_file['data'])
                        provisioning_profile = temp_profile_path
                        logging.info(f"Retrieved provisioning profile from MongoDB and saved to {provisioning_profile}")
                    else:
                        logging.warning("Provisioning profile not found in MongoDB")
                        provisioning_profile = None
                except Exception as e:
                    logging.error(f"Error retrieving provisioning profile: {str(e)}")
                    provisioning_profile = None
            
            # Continue with the rest of the original build function...
            # Since we're using a temporary directory for the local operations,
            # we don't need to clean up the build directory at the end
            
            # For simplicity, we'll create a placeholder IPA (simulated build)
            # In a real implementation, you would run xcodebuild here
            
            # For the sake of this example, create a simple placeholder IPA
            ipa_path = os.path.join(build_dir, f"{app_name or 'app'}.ipa")
            scheme_name = app_name or os.path.basename(build_file).split('.')[0]
            
            db.update_build_status(build_id, 'building', "Creating IPA file...\n")
            
            try:
                with zipfile.ZipFile(ipa_path, 'w') as placeholder_ipa:
                    # Add metadata file
                    placeholder_info = os.path.join(build_dir, "info.txt")
                    with open(placeholder_info, 'w') as f:
                        f.write(f"Placeholder IPA for {app_name or scheme_name} built from {repo_url} (branch: {branch})\n\n")
                        f.write("NOTE: This is a simulated build.\n")
                        
                    placeholder_ipa.write(placeholder_info, "info.txt")
                    
                    # Create a skeletal Info.plist
                    info_plist_path = os.path.join(build_dir, "Info.plist")
                    with open(info_plist_path, 'w') as f:
                        f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.github.{scheme_name.lower()}</string>
    <key>CFBundleName</key>
    <string>{app_name or scheme_name}</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
</dict>
</plist>""")
                    placeholder_ipa.write(info_plist_path, "Info.plist")
                    
                    # Add some code files from the repo to make it more realistic
                    file_count = 0
                    for root, _, files in os.walk(build_dir):
                        for file in files:
                            if file.endswith(('.swift', '.h', '.m', '.c', '.cpp')) and file_count < 5:
                                filepath = os.path.join(root, file)
                                arcname = os.path.relpath(filepath, build_dir)
                                placeholder_ipa.write(filepath, arcname)
                                file_count += 1
                
                logging.info(f"Created IPA at: {ipa_path}")
                db.update_build_status(build_id, 'building', f"Created IPA: {ipa_path}\n")
            except Exception as e:
                error_msg = f"Error creating IPA: {str(e)}\n{traceback.format_exc()}"
                logging.error(error_msg)
                db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
                return
                
            # Read the IPA file
            try:
                with open(ipa_path, 'rb') as f:
                    ipa_data = f.read()
                logging.info(f"Read IPA file of size: {len(ipa_data)} bytes")
            except Exception as e:
                error_msg = f"Error reading IPA file: {str(e)}\n{traceback.format_exc()}"
                logging.error(error_msg)
                db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
                return
            
            # Generate a default icon for the app
            default_icon = load_default_icon()
            
            # Store the final IPA file in MongoDB
            file_id = str(uuid.uuid4())
            app_filename = f"{app_name or scheme_name}.ipa"
            db.save_file(file_id, app_filename, ipa_data, 'application/octet-stream')
            
            # Also store as a build artifact
            db.save_build_file(build_id, f"output/{app_filename}", ipa_data, 'application/octet-stream')
            
            # Create app entry in the database
            app_info = {
                'id': str(uuid.uuid4()),
                'name': app_name or scheme_name,
                'bundle_id': f"com.github.{scheme_name.lower()}",
                'version': '1.0.0',
                'build_number': '1',
                'icon': default_icon,
                'file_id': file_id,
                'filename': app_filename,
                'size': len(ipa_data),
                'creation_date': datetime.now().isoformat(),
                'source': f"GitHub: {repo_url} (branch: {branch})",
                'build_id': build_id,  # Store the build ID to link back to the build
                'versions': [{
                    'version': '1.0.0',
                    'file_id': file_id,
                    'filename': app_filename,
                    'upload_date': datetime.now().isoformat(),
                    'size': len(ipa_data)
                }]
            }
            
            try:
                db.save_app(app_info)
                logging.info(f"Saved app to database with ID: {app_info['id']}")
                # Set end_time when marking build as completed
                current_time = datetime.now().isoformat()
                db.update_build_status(build_id, 'completed', f"Build completed successfully. App ID: {app_info['id']}\n", end_time=current_time)
            except Exception as e:
                error_msg = f"Error saving app to database: {str(e)}\n{traceback.format_exc()}"
                logging.error(error_msg)
                # Set end_time for failed builds too
                current_time = datetime.now().isoformat()
                db.update_build_status(build_id, 'failed', error_msg, end_time=current_time)
                return
        
    except Exception as e:
        error_msg = f"Build failed with error: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
        # Set end_time for failed builds
        current_time = datetime.now().isoformat()
        db.update_build_status(build_id, 'failed', error_msg, end_time=current_time)
        return

@app.before_request
def load_logged_in_user():
    g.user = None
    username = session.get('username')
    if username:
        g.user = db.get_user(username)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = db.get_user(username)
        
        error = None
        
        if not user:
            error = 'Invalid username'
        elif not check_password_hash(user['password'], password):
            error = 'Invalid password'
        
        if error is None:
            session.clear()
            session['username'] = username
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        
        flash(error)
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out')
    response = redirect(url_for('index'))
    # Add cache control headers to prevent back button from showing protected pages
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/register', methods=['GET', 'POST'])
@admin_required
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        error = None
        if db.get_user(username):
            error = f"User {username} already exists"
        
        if error is None:
            user_data = {
                'username': username,
                'password': generate_password_hash(password),
                'role': role
            }
            db.save_user(user_data)
            flash(f"User {username} created successfully")
            return redirect(url_for('manage_users'))
        
        flash(error)
    
    return render_template('register.html')

@app.route('/manage_users')
@admin_required
def manage_users():
    users = db.get_users()
    current_username = session['username']
    return render_template('manage_users.html', users=users, current_username=current_username)

@app.route('/delete_user/<username>', methods=['POST'])
@admin_required
def delete_user(username):
    if username == 'admin':
        flash('Cannot delete the main admin user')
        return redirect(url_for('manage_users'))
    
    if db.get_user(username):
        db.delete_user(username)
        flash(f"User {username} deleted successfully")
    else:
        flash(f"User {username} not found")
    
    return redirect(url_for('manage_users'))

@app.route('/')
def index():
    # Get apps based on user access level
    if 'username' in session:
        apps = db.get_apps_for_user(session['username'])
    else:
        # Non-logged in users don't see any apps
        apps = []
    
    # Get latest timestamp for auto-refresh feature
    latest_timestamp = None
    for app in apps:
        app_timestamp = app.get('upload_date') or app.get('creation_date')
        if app_timestamp and (latest_timestamp is None or app_timestamp > latest_timestamp):
            latest_timestamp = app_timestamp
    
    return render_template('index.html', 
                           apps=apps, 
                           app_count=len(apps), 
                           latest_timestamp=latest_timestamp)

@app.route('/upload', methods=['GET', 'POST'])
@admin_required
def upload():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
            
        file = request.files['file']
        app_id = request.form.get('app_id', None)
        app_name = request.form.get('app_name', '')
        app_version = request.form.get('app_version', '')
        bundle_id = request.form.get('bundle_id', '')
        
        # Validate required fields
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
            
        # For new apps, app name is required
        if not app_id and not app_name:
            flash('App name is required for new apps')
            return redirect(request.url)
            
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_data = file.read()  # Read file data directly
            
            # If no version provided, it will be extracted in the respective functions
            
            if app_id:  # Adding a new version to existing app
                app = db.get_app(app_id)
                if not app:
                    flash("App not found")
                    return redirect(request.url)
                
                # Add new version
                updated_app = add_app_version(app_id, file_data, filename, app_version)
                if updated_app:
                    flash(f"New version {app_version or updated_app['version']} added for {updated_app['name']}")
                else:
                    flash("Error adding new version")
            else:  # Adding a new app
                # Extract info and store the file
                app_info = extract_app_info(file_data, filename)
                
                # Override with user-provided info
                if app_name:
                    app_info['name'] = app_name
                if app_version:
                    app_info['version'] = app_version
                    app_info['versions'][0]['version'] = app_version
                if bundle_id:
                    app_info['bundle_id'] = bundle_id
                
                db.save_app(app_info)
                flash(f"App {app_info['name']} (v{app_info['version']}) uploaded successfully")
                
            return redirect(url_for('index'))
    
    # For GET request, show upload form
    apps = db.get_apps()
    return render_template('upload.html', apps=apps)

def verify_github_token():
    """
    Verify that the GitHub token is valid by making a test API call
    
    Returns:
        bool: True if the token is valid, False otherwise
    """
    if not GITHUB_API_TOKEN:
        logging.error("GitHub API token is missing")
        return False
    
    # Set up headers with proper authorization format
    headers = {
        'Accept': 'application/vnd.github.v3+json'
    }
    
    if GITHUB_API_TOKEN.startswith('Bearer '):
        headers['Authorization'] = GITHUB_API_TOKEN
    elif GITHUB_API_TOKEN.startswith('token '):
        headers['Authorization'] = GITHUB_API_TOKEN
    else:
        headers['Authorization'] = f'Bearer {GITHUB_API_TOKEN}'
    
    # Make a simple API call to verify the token
    try:
        # Get the authenticated user info
        response = requests.get('https://api.github.com/user', headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            logging.info(f"GitHub token verified for user: {user_data.get('login', 'Unknown')}")
            return True
        else:
            error_msg = response.json().get('message', 'Unknown error')
            logging.error(f"GitHub token verification failed: {error_msg}")
            return False
    except Exception as e:
        logging.error(f"Error verifying GitHub token: {str(e)}")
        return False

@app.route('/github_build', methods=['GET', 'POST'])
@admin_required
def github_build():
    """Handle GitHub build requests"""
    if request.method == 'POST':
        repo_url = request.form.get('repo_url')
        branch = request.form.get('branch', 'main')
        app_name = request.form.get('app_name')
        build_config = request.form.get('build_config', 'Release')
        team_id = request.form.get('team_id', APPLE_TEAM_ID)
        xcode_version = request.form.get('xcode_version', 'latest')
        
        # Validate GitHub token is set and valid
        if not GITHUB_API_TOKEN or not GITHUB_USERNAME:
            flash("GitHub API token and username must be configured in environment variables")
            return redirect(url_for('github_build'))
        
        # Verify the GitHub token is valid
        if not verify_github_token():
            flash("GitHub API token is invalid or expired. Please update the token in your environment variables.")
            return redirect(url_for('github_build'))
        
        # Create a new build record
        build_id = str(uuid.uuid4())
        new_build = {
            'id': build_id,
            'repo_url': repo_url,
            'branch': branch,
            'app_name': app_name,
            'build_config': build_config,
            'team_id': team_id,
            'xcode_version': xcode_version,
            'status': 'queued',
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'log': [f"Build queued for {repo_url} (branch: {branch})\n"],
            'build_files': []  # Initialize an empty array to track build files
        }
        
        # Save the build record
        db.save_build(new_build)
        
        try:
            # Start the GitHub Actions workflow process
            fork_info = fork_and_setup_github_workflow(
                build_id, 
                repo_url, 
                branch, 
                app_name, 
                build_config
            )
            
            # Store the fork info in the build record
            new_build['fork_info'] = fork_info
            db.save_build(new_build)
            
            flash(f"Build for {app_name or 'iOS app'} from {repo_url} has been queued")
            return redirect(url_for('build_log', build_id=build_id))
            
        except Exception as e:
            error_msg = f"Error setting up GitHub build: {str(e)}"
            logging.error(f"{error_msg}\n{traceback.format_exc()}")
            
            # Update build status to failed
            db.update_build_status(
                build_id, 
                'failed', 
                f"{error_msg}\n{traceback.format_exc()}", 
                end_time=datetime.now().isoformat()
            )
            
            flash(error_msg, 'error')
            return redirect(url_for('github_build'))
    
    # For GET request, show the build form and list recent builds
    builds = db.get_builds()
    # Sort builds by start time (newest first)
    builds.sort(key=lambda x: x.get('start_time', ''), reverse=True)
    
    # Calculate build durations
    for build in builds:
        build['duration'] = None
        if build['status'] not in ['building', 'in_progress', 'queued'] and 'start_time' in build and 'end_time' in build and build['end_time']:
            try:
                start_time = datetime.fromisoformat(build['start_time'])
                end_time = datetime.fromisoformat(build['end_time'])
                duration = end_time - start_time
                
                # Format the duration in a human-readable format
                total_seconds = int(duration.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                if hours > 0:
                    build['duration'] = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    build['duration'] = f"{minutes}m {seconds}s"
                else:
                    build['duration'] = f"{seconds}s"
            except Exception as e:
                logging.error(f"Error calculating build duration: {str(e)}")
    
    # Get GitHub repository URL for template
    github_repo_url = get_github_repo_url()
    
    return render_template('github_build.html', 
                          builds=builds, 
                          github_repo_url=github_repo_url)

@app.route('/download_build/<build_id>')
@login_required
def download_build(build_id):
    """Download a built IPA file"""
    build = db.get_build(build_id)
    if not build or build['status'] != 'completed':
        flash("Build not found or not completed")
        return redirect(url_for('github_build'))
    
    # Find the app that was created from this build
    apps = db.get_apps()
    app = None
    for a in apps:
        if a.get('build_id') == build_id:
            app = a
            break
    
    if not app:
        flash("App not found for this build")
        return redirect(url_for('github_build'))
    
    # Get the file_id
    if 'file_id' not in app:
        flash("No file associated with this build")
        return redirect(url_for('github_build'))
    
    file_id = app['file_id']
    file_doc = db.get_file(file_id)
    
    if not file_doc or 'data' not in file_doc:
        flash("File data not found")
        return redirect(url_for('github_build'))
    
    # Generate an appropriate filename
    filename = app.get('filename', f"{app['name'].replace(' ', '_')}_{app['version']}.ipa")
    
    # Serve the file directly from memory
    return send_file(
        io.BytesIO(file_doc['data']),
        mimetype=file_doc.get('content_type', 'application/octet-stream'),
        as_attachment=True,
        download_name=filename
    )

@app.route('/build_log/<build_id>')
@login_required
def build_log(build_id):
    """View the log for a build"""
    build = db.get_build(build_id)
    if not build:
        flash("Build not found")
        return redirect(url_for('github_build'))
    
    # Check if log is an array and convert it to a string if needed
    if 'log' in build and isinstance(build['log'], list):
        # Join the log entries into a single string
        build['log_content'] = ''.join(build['log'])
    elif 'log' in build:
        # For backward compatibility with existing builds
        build['log_content'] = build['log']
    else:
        build['log_content'] = "No log data available"
    
    # Calculate build duration if possible
    build['duration'] = None
    if build['status'] not in ['building', 'in_progress', 'queued'] and 'start_time' in build and 'end_time' in build and build['end_time']:
        try:
            start_time = datetime.fromisoformat(build['start_time'])
            end_time = datetime.fromisoformat(build['end_time'])
            duration = end_time - start_time
            
            # Format the duration in a human-readable format
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                build['duration'] = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                build['duration'] = f"{minutes}m {seconds}s"
            else:
                build['duration'] = f"{seconds}s"
        except Exception as e:
            logging.error(f"Error calculating build duration: {str(e)}")
    
    return render_template('build_log.html', build=build)

@app.route('/app/<app_id>')
def app_detail(app_id):
    # Check if user has access to this app
    if 'username' not in session or not db.get_user_app_access(session['username'], app_id):
        flash("You don't have access to this app or it doesn't exist")
        return redirect(url_for('index'))
    
    app = db.get_app(app_id)
    if app:
        # Get the users this app is shared with (for admins)
        shared_users = []
        if g.user and g.user.get('role') == 'admin':
            shared_users = db.get_shared_users(app_id)
        
        return render_template('app_detail.html', app=app, shared_users=shared_users)
    
    flash("App not found")
    return redirect(url_for('index'))

@app.route('/edit/<app_id>', methods=['GET', 'POST'])
@admin_required
def edit_app(app_id):
    app = db.get_app(app_id)
    if not app:
        flash("App not found")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Get form data
        app_name = request.form.get('name')
        version = request.form.get('version')
        
        # Update app data
        app['name'] = app_name
        app['version'] = version
                
        # Handle icon upload if provided
        if 'icon' in request.files and request.files['icon'].filename:
            icon_file = request.files['icon']
            try:
                # Process and resize the icon
                img = Image.open(icon_file)
                img = img.resize((128, 128))  # Resize to standard size
                
                # Convert to base64 for storage
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                app['icon'] = f"data:image/png;base64,{img_str}"
            except Exception as e:
                flash(f"Error processing icon: {str(e)}")
                
        # Update the latest version in versions list too
        if app['versions']:
            app['versions'][-1]['version'] = version
                
        db.save_app(app)
        flash(f"App '{app_name}' updated successfully")
        return redirect(url_for('app_detail', app_id=app_id))
    
    return render_template('edit_app.html', app=app)

@app.route('/download/<app_id>/<filename>')
def download_app(app_id, filename):
    # Check if user has access to this app
    if 'username' not in session or not db.get_user_app_access(session['username'], app_id):
        flash("You don't have access to this app or it doesn't exist")
        return redirect(url_for('index'))
    
    app = db.get_app(app_id)
    if not app:
        flash("App not found")
        return redirect(url_for('index'))
    
    # Find the file_id based on filename (could be main app or a version)
    file_id = None
    
    # Check if main app file
    if 'file_id' in app and app.get('filename') == filename:
        file_id = app['file_id']
    
    # Check in versions if not found
    if file_id is None and 'versions' in app:
        for version in app['versions']:
            if version.get('filename') == filename and 'file_id' in version:
                file_id = version['file_id']
                break
    
    if file_id is None:
        flash("File not found")
        return redirect(url_for('app_detail', app_id=app_id))
    
    # Get the file from MongoDB
    file_doc = db.get_file(file_id)
    if not file_doc or 'data' not in file_doc:
        flash("File data not found")
        return redirect(url_for('app_detail', app_id=app_id))
    
    # Serve the file directly from memory
    return send_file(
        io.BytesIO(file_doc['data']),
        mimetype=file_doc.get('content_type', 'application/octet-stream'),
        as_attachment=True,
        download_name=filename
    )

@app.route('/install/<app_id>')
def install(app_id):
    # Check if user has access to this app
    if 'username' not in session or not db.get_user_app_access(session['username'], app_id):
        flash("You don't have access to this app or it doesn't exist")
        return redirect(url_for('index'))
    
    app = db.get_app(app_id)
    if app:
        # For iOS apps, we'll use itms-services protocol to initiate installation
        # In a real implementation, we would generate a dynamic manifest
        manifest_url = url_for('app_manifest', app_id=app_id, _external=True)
        install_url = f"itms-services://?action=download-manifest&url={manifest_url}"
        return render_template('install.html', app=app, install_url=install_url)
    
    flash("App not found")
    return redirect(url_for('index'))

@app.route('/direct_install/<app_id>')
def direct_install(app_id):
    app = db.get_app(app_id)
    if app:
        # Set up download URL based on app type
        if 'file_id' in app:
            # For GitHub-built apps, use a generated filename
            filename = f"{app['name'].replace(' ', '_')}_{app['version']}.ipa"
        else:
            # For manually uploaded apps, use the stored filename
            filename = app.get('filename', f"{app['name'].replace(' ', '_')}.ipa")
            
        download_url = url_for('download_app', app_id=app_id, filename=filename, _external=True)
        return render_template('direct_install.html', app=app, download_url=download_url)
    
    flash("App not found")
    return redirect(url_for('index'))

@app.route('/manifest/<app_id>')
def app_manifest(app_id):
    app = db.get_app(app_id)
    if not app:
        return "App not found", 404
    
    # Generate a dynamic manifest plist for the app
    # Set up download URL based on app type
    if 'file_id' in app:
        # For GitHub-built apps, use a generated filename
        filename = f"{app['name'].replace(' ', '_')}_{app['version']}.ipa"
    else:
        # For manually uploaded apps, use the stored filename
        filename = app.get('filename', f"{app['name'].replace(' ', '_')}.ipa")
        
    download_url = url_for('download_app', app_id=app_id, filename=filename, _external=True)
    
    manifest = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>items</key>
    <array>
        <dict>
            <key>assets</key>
            <array>
                <dict>
                    <key>kind</key>
                    <string>software-package</string>
                    <key>url</key>
                    <string>{download_url}</string>
                </dict>
            </array>
            <key>metadata</key>
            <dict>
                <key>bundle-identifier</key>
                <string>{app.get('bundle_id', f"com.example.{app['name']}")}</string>
                <key>bundle-version</key>
                <string>{app['version']}</string>
                <key>kind</key>
                <string>software</string>
                <key>title</key>
                <string>{app['name']}</string>
            </dict>
        </dict>
    </array>
</dict>
</plist>"""
    
    return manifest, 200, {'Content-Type': 'application/xml'}

@app.route('/delete/<app_id>', methods=['POST'])
@admin_required
def delete_app(app_id):
    app = db.get_app(app_id)
    
    if app:
        try:
            # Delete the app (files are deleted in db.delete_app)
            db.delete_app(app_id)
            flash(f"App {app['name']} deleted successfully")
        except Exception as e:
            logging.error(f"Error deleting app {app_id}: {str(e)}")
            flash(f"Error deleting app: {str(e)}")
    else:
        flash("App not found")
    
    return redirect(url_for('index'))

@app.route('/api/apps')
@login_required
def api_apps():
    """API endpoint to list all apps"""
    apps = db.get_apps()
    return jsonify(apps)

@app.route('/api/app/<app_id>')
@login_required
def api_app(app_id):
    """API endpoint to get app details"""
    app = db.get_app(app_id)
    if app:
        return jsonify(app)
    return jsonify({"error": "App not found"}), 404

# GitHub builds API endpoints
@app.route('/api/builds')
@login_required
def api_builds():
    """API endpoint to list all builds"""
    builds = db.get_builds()
    return jsonify(builds)

@app.route('/api/build/<build_id>')
@login_required
def api_build(build_id):
    """API endpoint to get build details"""
    build = db.get_build(build_id)
    if build:
        return jsonify(build)
    return jsonify({"error": "Build not found"}), 404

@app.route('/api/app_status')
def api_app_status():
    """API endpoint to check if there are new apps or updates
    Used for auto-refreshing the home page"""
    if 'username' not in session:
        return jsonify({"count": 0, "latest_timestamp": None})
        
    apps = db.get_apps_for_user(session['username'])
    
    # Get count and latest timestamp
    count = len(apps)
    latest_timestamp = None
    
    for app in apps:
        app_timestamp = app.get('upload_date') or app.get('creation_date')
        if app_timestamp and (latest_timestamp is None or app_timestamp > latest_timestamp):
            latest_timestamp = app_timestamp
    
    return jsonify({
        "count": count,
        "latest_timestamp": latest_timestamp
    })

@app.route('/api/build_status')
@login_required
def api_build_status():
    """API endpoint to check for changes in build statuses
    Used for auto-refreshing the GitHub build page"""
    builds = db.get_builds()
    
    # Get the number of builds that are in progress
    in_progress_count = sum(1 for build in builds if build.get('status') in ['building', 'in_progress', 'queued'])
    
    # Get the latest build update timestamp
    latest_timestamp = None
    for build in builds:
        # For builds in progress, prioritize start time
        if build.get('status') in ['building', 'in_progress', 'queued']:
            build_timestamp = build.get('start_time')
        else:
            # For completed builds, use end time
            build_timestamp = build.get('end_time')
        
        if build_timestamp and (latest_timestamp is None or build_timestamp > latest_timestamp):
            latest_timestamp = build_timestamp
    
    # Check for stuck or abandoned builds that need cleanup
    check_abandoned_builds()
    
    return jsonify({
        "total_count": len(builds),
        "in_progress_count": in_progress_count,
        "latest_timestamp": latest_timestamp
    })

def check_abandoned_builds():
    """
    Check for builds that have been stuck in-progress for too long and clean up their resources
    This helps ensure forked repositories are properly deleted even if GitHub Actions fails silently
    """
    # Don't run this check too frequently - we use a simple in-memory cache to throttle
    last_check_time = getattr(check_abandoned_builds, 'last_check_time', None)
    current_time = time.time()
    
    # Only check once every 5 minutes
    if last_check_time and (current_time - last_check_time) < 300:
        return
    
    check_abandoned_builds.last_check_time = current_time
    
    try:
        # Get all builds
        builds = db.get_builds()
        
        # Current time as ISO format for database updates
        current_time_iso = datetime.now().isoformat()
        
        # Check each in-progress build
        for build in builds:
            # Only process builds that are in progress states
            if build.get('status') not in ['building', 'in_progress', 'queued', 'setting_up', 'triggered', 'forking']:
                continue
                
            # Skip builds that don't have a start time
            if 'start_time' not in build:
                continue
                
            # Calculate how long the build has been running
            try:
                start_time = datetime.fromisoformat(build['start_time'].replace('Z', '+00:00'))
                time_diff = datetime.now() - start_time
                
                # If build has been running for more than 30 minutes, consider it abandoned
                if time_diff.total_seconds() > 1800:  # 30 minutes
                    logging.warning(f"Found abandoned build {build['id']} running for {time_diff.total_seconds()/60:.1f} minutes. Marking as failed.")
                    
                    # Mark the build as failed
                    db.update_build_status(
                        build['id'], 
                        'failed', 
                        f"Build automatically marked as failed after being stuck for {time_diff.total_seconds()/60:.1f} minutes.\n", 
                        end_time=current_time_iso
                    )
                    
                    # Clean up any forked repository
                    if 'fork_info' in build and GITHUB_API_TOKEN:
                        try:
                            fork_info = build['fork_info']
                            owner, repo = fork_info['forked_repo'].split('/')
                            
                            # Properly format the authorization header
                            headers = {
                                'Accept': 'application/vnd.github.v3+json'
                            }
                            
                            if GITHUB_API_TOKEN.startswith('Bearer '):
                                headers['Authorization'] = GITHUB_API_TOKEN
                            elif GITHUB_API_TOKEN.startswith('token '):
                                headers['Authorization'] = GITHUB_API_TOKEN
                            else:
                                headers['Authorization'] = f'Bearer {GITHUB_API_TOKEN}'
                            
                            # Add marker to build log that cleanup is being attempted
                            db.update_build_status(build['id'], 'failed', f"Attempting to clean up abandoned forked repository {owner}/{repo}...\n")
                            
                            cleanup_success = cleanup_fork(owner, repo, headers)
                            status_update = f"Abandoned forked repository {owner}/{repo} has been cleaned up." if cleanup_success else f"Warning: Failed to clean up abandoned forked repository {owner}/{repo}. Please delete it manually."
                            db.update_build_status(build['id'], 'failed', status_update)
                        except Exception as e:
                            logging.error(f"Error cleaning up abandoned build repository: {str(e)}")
            except Exception as e:
                logging.error(f"Error checking abandoned build {build.get('id')}: {str(e)}")
                
    except Exception as e:
        logging.error(f"Error in check_abandoned_builds: {str(e)}")

# App sharing routes
@app.route('/manage_sharing/<app_id>', methods=['GET', 'POST'])
@admin_required
def manage_sharing(app_id):
    """Manage which users have access to an app"""
    app = db.get_app(app_id)
    if not app:
        flash("App not found")
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        # Handle share/unshare actions
        action = request.form.get('action')
        username = request.form.get('username')
        
        if action == 'share' and username:
            success, message = db.share_app(app_id, username)
            if success:
                flash(message)
            else:
                flash(f"Error sharing app: {message}")
                
        elif action == 'unshare' and username:
            if db.unshare_app(app_id, username):
                flash(f"App access removed for user {username}")
            else:
                flash(f"Error removing access for user {username}")
        
        return redirect(url_for('manage_sharing', app_id=app_id))
        
    # Get users for display
    users = db.get_users()
    # Filter out admin users (no need to share with them)
    users = [user for user in users if user.get('role') != 'admin']
    
    # Get current shares
    shared_users = db.get_shared_users(app_id)
    
    return render_template('manage_sharing.html', 
                          app=app, 
                          users=users, 
                          shared_users=shared_users)

@app.route('/share_app/<app_id>', methods=['POST'])
@admin_required
def share_app(app_id):
    """Quick share action from app detail page"""
    username = request.form.get('username')
    if not username:
        flash("Username is required")
        return redirect(url_for('app_detail', app_id=app_id))
        
    success, message = db.share_app(app_id, username)
    flash(message)
    
    return redirect(url_for('app_detail', app_id=app_id))

@app.route('/unshare_app/<app_id>/<username>', methods=['POST'])
@admin_required
def unshare_app(app_id, username):
    """Quick unshare action from app detail page"""
    if db.unshare_app(app_id, username):
        flash(f"App access removed for user {username}")
    else:
        flash(f"Error removing access for user {username}")
        
    return redirect(url_for('app_detail', app_id=app_id))

# Account management routes
@app.route('/account', methods=['GET'])
@login_required
def account_management():
    """User account management page"""
    username = session['username']
    user = db.get_user(username)
    
    if not user:
        flash("User not found")
        return redirect(url_for('logout'))
    
    return render_template('account.html', user=user)

@app.route('/account/change-password', methods=['POST'])
@login_required
def change_password():
    """Handle password change requests"""
    username = session['username']
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate inputs
    user = db.get_user(username)
    if not user:
        flash("User not found")
        return redirect(url_for('logout'))
    
    if not check_password_hash(user['password'], current_password):
        flash("Current password is incorrect")
        return redirect(url_for('account_management'))
    
    if new_password != confirm_password:
        flash("New passwords do not match")
        return redirect(url_for('account_management'))
    
    if len(new_password) < 8:
        flash("Password must be at least 8 characters long")
        return redirect(url_for('account_management'))
    
    # Update password
    new_password_hash = generate_password_hash(new_password)
    if db.update_user_password(username, new_password_hash):
        flash("Password updated successfully")
    else:
        flash("Failed to update password")
    
    return redirect(url_for('account_management'))

@app.route('/account/profile-picture', methods=['POST'])
@login_required
def update_profile_picture():
    """Handle profile picture updates"""
    username = session['username']
    
    # Check if we have cropped image data
    cropped_image = request.form.get('cropped_image')
    
    if cropped_image and cropped_image.startswith('data:image'):
        # Process cropped image data (base64)
        try:
            # Strip header from data URL to get base64 string
            image_format, image_data = cropped_image.split(';base64,')
            image_data = base64.b64decode(image_data)
            
            # Create image from binary data
            img = Image.open(io.BytesIO(image_data))
            
            # Save to a byte stream
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)
            
            # Update profile picture
            content_type = 'image/jpeg'
            if db.update_user_profile_picture(username, img_byte_arr.getvalue(), content_type):
                flash("Profile picture updated successfully")
            else:
                flash("Failed to update profile picture")
                
        except Exception as e:
            flash(f"Error processing image: {str(e)}")
        
        return redirect(url_for('account_management'))
    
    # Fallback to direct file processing if no cropped data 
    # (shouldn't happen with updated UI but kept for robustness)
    if 'profile_picture' not in request.files or not request.files['profile_picture'].filename:
        flash('No file selected')
        return redirect(url_for('account_management'))
    
    file = request.files['profile_picture']
    
    # Check if it's an image file
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        flash('Invalid file type. Please upload an image file (PNG, JPG, JPEG, GIF)')
        return redirect(url_for('account_management'))
    
    try:
        # Process and resize the image
        img = Image.open(file)
        
        # Fix image rotation based on EXIF data
        try:
            # Check if the image has EXIF data with orientation info
            if hasattr(img, '_getexif') and img._getexif() is not None:
                exif = dict(img._getexif().items())
                # EXIF orientation tag is 0x0112 (274)
                if 274 in exif:
                    # Handle the orientation
                    orientation = exif[274]
                    if orientation == 2:
                        img = img.transpose(Image.FLIP_LEFT_RIGHT)
                    elif orientation == 3:
                        img = img.rotate(180)
                    elif orientation == 4:
                        img = img.rotate(180).transpose(Image.FLIP_LEFT_RIGHT)
                    elif orientation == 5:
                        img = img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                    elif orientation == 6:
                        img = img.rotate(-90, expand=True)
                    elif orientation == 7:
                        img = img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                    elif orientation == 8:
                        img = img.rotate(90, expand=True)
        except (AttributeError, KeyError, IndexError):
            # If there's an error getting/processing EXIF data, continue without rotation fix
            pass
            
        img = img.convert('RGB')  # Convert to RGB format if needed
        
        # Resize to a reasonable size for profile pictures
        img.thumbnail((300, 300))
        
        # Save to a byte stream
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)
        
        # Update profile picture
        content_type = 'image/jpeg'
        if db.update_user_profile_picture(username, img_byte_arr.getvalue(), content_type):
            flash("Profile picture updated successfully")
        else:
            flash("Failed to update profile picture")
            
    except Exception as e:
        flash(f"Error processing image: {str(e)}")
    
    return redirect(url_for('account_management'))

@app.route('/user/<username>/profile-picture')
def user_profile_picture(username):
    """Serve user profile pictures"""
    file_doc = db.get_user_profile_picture(username)
    
    if not file_doc or 'data' not in file_doc:
        # Return the default profile picture from root directory
        default_profile_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'defaultProf.jpg')
        return send_file(default_profile_path, mimetype='image/jpeg')
    
    # Serve the image directly from memory
    return send_file(
        io.BytesIO(file_doc['data']),
        mimetype=file_doc.get('content_type', 'image/jpeg')
    )

@app.route('/download_build_log/<build_id>')
@login_required
def download_build_log(build_id):
    """Download the build log as a text file"""
    build = db.get_build(build_id)
    if not build:
        flash("Build not found")
        return redirect(url_for('github_build'))
    
    # Check if log is an array and convert it to a string if needed
    if 'log' in build and isinstance(build['log'], list):
        log_content = ''.join(build['log'])
    elif 'log' in build:
        log_content = build['log']
    else:
        log_content = "No log data available"
    
    # Calculate build duration if possible
    duration_str = "N/A"
    if build['status'] not in ['building', 'in_progress', 'queued'] and 'start_time' in build and 'end_time' in build and build['end_time']:
        try:
            start_time = datetime.fromisoformat(build['start_time'])
            end_time = datetime.fromisoformat(build['end_time'])
            duration = end_time - start_time
            
            # Format the duration in a human-readable format
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
        except Exception as e:
            logging.error(f"Error calculating build duration: {str(e)}")
    
    # Add build information header to log content
    header = f"""=== BUILD INFORMATION ===
Repository: {build.get('repo_url', 'N/A')}
Branch: {build.get('branch', 'N/A')}
App Name: {build.get('app_name', 'N/A')}
Status: {build.get('status', 'N/A')}
Started: {format_date(build.get('start_time', 'N/A'))}
Ended: {format_date(build.get('end_time', 'N/A'))}
Duration: {duration_str}
Configuration: {build.get('build_config', 'N/A')} - Xcode {build.get('xcode_version', 'Latest')}

=== BUILD LOG ===
"""
    
    log_content = header + log_content
    
    # Prepare file name
    repo_name = build.get('repo_url', '').split('/')[-1].split('.')[0] if build.get('repo_url') else 'build'
    timestamp = format_date(build.get('start_time', '')).replace('-', '_') if build.get('start_time') else ''
    filename = f"{repo_name}_{build_id}_{timestamp}_build_log.txt"
    
    # Create response with file
    response = make_response(log_content)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/plain"
    
    return response

@app.route('/stop_build/<build_id>', methods=['GET'])
@admin_required
def stop_build(build_id):
    """Stop a running build process"""
    build = db.get_build(build_id)
    
    if not build:
        flash("Build not found")
        return redirect(url_for('github_build'))
    
    # Only allow stopping builds that are in progress or queued
    if build['status'] not in ['building', 'in_progress', 'queued']:
        flash("This build cannot be stopped because it's not in progress")
        return redirect(url_for('build_log', build_id=build_id))
    
    # Update the build status to 'cancelled'
    stop_message = "\n\n=== BUILD MANUALLY STOPPED BY USER ===\n\n"
    db.update_build_status(build_id, 'cancelled', stop_message)
    
    # You would typically need to actually terminate the build process here
    # In a production environment, this might involve sending a signal to the process
    # or using process management tools to terminate it
    # For demonstration purposes, we're just updating the status
    
    # Set an end time for the build
    db.update_build_status(build_id, 'cancelled', end_time=datetime.now().isoformat())
    
    flash("Build process has been stopped")
    return redirect(url_for('build_log', build_id=build_id))

@app.route('/delete_build/<build_id>', methods=['POST'])
@admin_required
def delete_build(build_id):
    """Delete a build record"""
    build = db.get_build(build_id)
    
    if not build:
        flash("Build not found")
        return redirect(url_for('github_build'))
    
    # Check if build is in progress
    if build['status'] in ['building', 'in_progress', 'queued']:
        flash("Cannot delete a build that is in progress. Stop it first.")
        return redirect(url_for('github_build'))
    
    # Check if there's an app associated with this build
    apps = db.get_apps()
    associated_app = None
    for app in apps:
        if app.get('build_id') == build_id:
            associated_app = app
            break
    
    # If there's an associated app, we'll need user confirmation
    # This is handled via the confirmation dialog in the UI
    
    # Delete the build
    if db.delete_build(build_id):
        flash(f"Build was successfully deleted")
    else:
        flash("Error deleting build")
    
    return redirect(url_for('github_build'))

@app.route('/cleanup_repository/<build_id>', methods=['POST'])
@admin_required
def cleanup_repository(build_id):
    """Manually clean up a forked repository for a build"""
    build = db.get_build(build_id)
    
    if not build:
        flash("Build not found")
        return redirect(url_for('github_build'))
    
    # Check if we have fork info
    if 'fork_info' not in build:
        flash("No forked repository information found for this build")
        return redirect(url_for('build_log', build_id=build_id))
    
    # Get fork info
    fork_info = build['fork_info']
    if 'forked_repo' not in fork_info:
        flash("Invalid fork information, missing repository details")
        return redirect(url_for('build_log', build_id=build_id))
    
    try:
        # Get owner and repository name
        owner, repo = fork_info['forked_repo'].split('/')
        
        # Make sure we have a valid token
        if not GITHUB_API_TOKEN:
            flash("GitHub API token is missing. Please configure it in the environment variables")
            return redirect(url_for('build_log', build_id=build_id))
        
        # Properly format the authorization header
        headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        
        if GITHUB_API_TOKEN.startswith('Bearer '):
            headers['Authorization'] = GITHUB_API_TOKEN
        elif GITHUB_API_TOKEN.startswith('token '):
            headers['Authorization'] = GITHUB_API_TOKEN
        else:
            headers['Authorization'] = f'Bearer {GITHUB_API_TOKEN}'
        
        # Add marker to build log that manual cleanup is being attempted
        db.update_build_status(build_id, build['status'], f"Manually cleaning up forked repository {owner}/{repo}...\n")
        
        # Attempt to clean up the forked repository
        cleanup_success = cleanup_fork(owner, repo, headers)
        
        if cleanup_success:
            flash(f"Successfully cleaned up forked repository {owner}/{repo}")
            db.update_build_status(build_id, build['status'], f"Forked repository {owner}/{repo} has been manually cleaned up.\n")
        else:
            flash(f"Failed to clean up forked repository {owner}/{repo}. Please check logs for details")
            db.update_build_status(build_id, build['status'], f"Warning: Failed to manually clean up forked repository {owner}/{repo}. Please delete it directly through GitHub.\n")
    
    except Exception as e:
        error_msg = str(e)
        flash(f"Error cleaning up forked repository: {error_msg}")
        db.update_build_status(build_id, build['status'], f"Error during manual cleanup: {error_msg}\n")
    
    return redirect(url_for('build_log', build_id=build_id))

@app.route('/api/branches')
@admin_required
def api_branches():
    """API endpoint to fetch branches from a GitHub repository"""
    repo_url = request.args.get('repo_url')
    if not repo_url:
        return jsonify({"error": "repo_url is required"}), 400
    
    try:
        branches = fetch_branches(repo_url)
        return jsonify(branches)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def fetch_branches(repo_url):
    """Fetch branches from a GitHub repository using GitHub's API"""
    # Parse the GitHub repository owner and name from the URL
    # Handle different formats of GitHub URLs
    if 'github.com' in repo_url:
        # Extract the owner and repo from URL
        if repo_url.startswith(('http://', 'https://')):
            # Handle full URLs
            pattern = r'github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$'
        else:
            # Handle github.com/owner/repo format
            pattern = r'([^/]+)/([^/]+?)(?:\.git)?$'
        
        match = re.search(pattern, repo_url)
        if not match:
            raise ValueError(f"Invalid GitHub repository URL: {repo_url}")
        
        owner, repo = match.groups()
    else:
        # Assume it's in format owner/repo
        parts = repo_url.split('/')
        if len(parts) != 2:
            raise ValueError(f"Invalid GitHub repository format: {repo_url}")
        owner, repo = parts
    
    # Clean the repo name (remove .git extension if present)
    repo = repo.rstrip('.git')
    
    # Construct the GitHub API URL for branches
    api_url = f"https://api.github.com/repos/{owner}/{repo}/branches"
    
    # Set up headers for GitHub API (include token if available)
    headers = {
        'Accept': 'application/vnd.github.v3+json'
    }
    if GITHUB_API_TOKEN:
        headers['Authorization'] = f'token {GITHUB_API_TOKEN}'
    
    # Make the API request
    response = requests.get(api_url, headers=headers)
    
    # Check if the request was successful
    if response.status_code != 200:
        error_msg = response.json().get('message', 'Failed to fetch branches')
        raise Exception(f"GitHub API error: {error_msg}")
    
    # Extract branch names from the response
    branches_data = response.json()
    branch_names = [branch['name'] for branch in branches_data]
    
    # Sort branches with main, master, and develop at the top
    priority_branches = ['main', 'master', 'develop']
    sorted_branches = sorted(branch_names, key=lambda x: (x not in priority_branches, x))
    
    return sorted_branches

def fork_and_setup_github_workflow(build_id, repo_url, branch, app_name, build_config='Release'):
    """
    Fork a GitHub repository, add workflow files, and trigger a build
    
    Args:
        build_id (str): The ID of the build record
        repo_url (str): GitHub repository URL to fork
        branch (str): Branch to build
        app_name (str): Name of the app to build
        build_config (str): Build configuration (Release/Debug)
        
    Returns:
        dict: Information about the forked repository and workflow
    """
    # Validate GitHub API token
    if not GITHUB_API_TOKEN:
        raise ValueError("GitHub API token is required for forking repositories")
    
    if not GITHUB_USERNAME:
        raise ValueError("GitHub username is required for forking repositories")
    
    # Update build status to forking
    db.update_build_status(build_id, 'forking', f"Forking repository {repo_url}...\n")
    
    # Extract owner and repo from URL
    owner, repo = extract_github_repo_info(repo_url)
    
    # Set up GitHub API headers with proper authorization format
    headers = {
        'Accept': 'application/vnd.github.v3+json'
    }
    
    if GITHUB_API_TOKEN.startswith('Bearer '):
        headers['Authorization'] = GITHUB_API_TOKEN
    elif GITHUB_API_TOKEN.startswith('token '):
        headers['Authorization'] = GITHUB_API_TOKEN
    else:
        headers['Authorization'] = f'Bearer {GITHUB_API_TOKEN}'
    
    # Log token info for debugging (safely)
    token_prefix = headers.get('Authorization', '').split(' ')[-1][:5] + '...' if 'Authorization' in headers else 'none'
    logging.info(f"Using GitHub token with prefix: {token_prefix}")
    
    # 1. Fork the repository
    fork_url = f'https://api.github.com/repos/{owner}/{repo}/forks'
    fork_response = requests.post(fork_url, headers=headers)
    
    if fork_response.status_code != 202:  # 202 Accepted is the expected response
        error_msg = f"Failed to fork repository: {fork_response.json().get('message', 'Unknown error')}"
        db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
        raise Exception(error_msg)
    
    # Get fork data
    fork_data = fork_response.json()
    forked_repo_url = fork_data['html_url']
    forked_repo_api_url = fork_data['url']
    forked_owner = GITHUB_USERNAME
    forked_repo = repo
    
    # Update build with fork information
    db.update_build_status(build_id, 'setting_up', 
                          f"Repository forked successfully to {forked_repo_url}\n"
                          f"Setting up GitHub Actions workflow...\n")
    
    # Wait for fork to be fully created
    time.sleep(5)  # Give GitHub some time to complete the fork
    
    # 2. Get the SHA of the latest commit on the branch
    try:
        # First, check if the branch exists in the forked repository
        branch_url = f'https://api.github.com/repos/{forked_owner}/{forked_repo}/branches/{branch}'
        branch_response = requests.get(branch_url, headers=headers)
        
        if branch_response.status_code == 200:
            # Branch exists, get the SHA
            sha = branch_response.json()['commit']['sha']
            db.update_build_status(build_id, 'setting_up', f"Found branch {branch} in forked repository with SHA: {sha[:7]}...\n")
        else:
            # Branch doesn't exist yet, get the default branch SHA
            repo_url = f'https://api.github.com/repos/{forked_owner}/{forked_repo}'
            repo_response = requests.get(repo_url, headers=headers)
            
            if repo_response.status_code != 200:
                error_msg = f"Failed to get repository info: {repo_response.json().get('message', 'Unknown error')}"
                db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
                cleanup_fork(forked_owner, forked_repo, headers)  # Clean up the fork since setup failed
                raise Exception(error_msg)
            
            # Get the default branch
            default_branch = repo_response.json()['default_branch']
            
            # Get the SHA of the default branch
            default_branch_url = f'https://api.github.com/repos/{forked_owner}/{forked_repo}/branches/{default_branch}'
            default_branch_response = requests.get(default_branch_url, headers=headers)
            
            if default_branch_response.status_code != 200:
                error_msg = f"Failed to get default branch info: {default_branch_response.json().get('message', 'Unknown error')}"
                db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
                cleanup_fork(forked_owner, forked_repo, headers)  # Clean up the fork since setup failed
                raise Exception(error_msg)
            
            sha = default_branch_response.json()['commit']['sha']
            db.update_build_status(build_id, 'setting_up', f"Using default branch {default_branch} with SHA: {sha[:7]}...\n")
            
            # If branch doesn't exist, we also need to create it
            if branch != default_branch:
                db.update_build_status(build_id, 'setting_up', f"Creating branch {branch} in forked repository...\n")
                
                # Create reference for the new branch
                refs_url = f'https://api.github.com/repos/{forked_owner}/{forked_repo}/git/refs'
                refs_data = {
                    'ref': f'refs/heads/{branch}',
                    'sha': sha
                }
                
                refs_response = requests.post(refs_url, headers=headers, json=refs_data)
                
                if refs_response.status_code not in [201, 200]:
                    error_msg = f"Failed to create branch {branch}: {refs_response.json().get('message', 'Unknown error')}"
                    db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
                    cleanup_fork(forked_owner, forked_repo, headers)  # Clean up the fork since setup failed
                    raise Exception(error_msg)
                
                db.update_build_status(build_id, 'setting_up', f"Branch {branch} created successfully\n")
    except Exception as e:
        error_msg = f"Error setting up branch: {str(e)}"
        db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
        cleanup_fork(forked_owner, forked_repo, headers)  # Clean up the fork since setup failed
        raise Exception(error_msg)
    
    # 3. Create GitHub Actions workflow file
    workflow_content = generate_github_workflow(app_name, branch, build_config, build_id)
    
    # Encode content to base64
    workflow_content_b64 = base64.b64encode(workflow_content.encode()).decode()
    
    # Create workflow file in the forked repo
    workflow_path = '.github/workflows/ios-build.yml'
    workflow_url = f'https://api.github.com/repos/{forked_owner}/{forked_repo}/contents/{workflow_path}'
    
    workflow_data = {
        'message': f'Add iOS build workflow for build #{build_id}',
        'content': workflow_content_b64,
        'branch': branch,
        'sha': sha  # Include the SHA of the latest commit
    }
    
    workflow_response = requests.put(workflow_url, headers=headers, json=workflow_data)
    
    if workflow_response.status_code not in [201, 200]:  # 201 Created or 200 OK
        error_details = workflow_response.json() if workflow_response.text else {'message': 'Unknown error'}
        error_msg = f"Failed to create workflow file: {error_details.get('message', 'Unknown error')}"
        logging.error(f"Workflow creation error details: {error_details}")
        db.update_build_status(build_id, 'failed', error_msg, end_time=datetime.now().isoformat())
        # Clean up the fork since setup failed
        cleanup_fork(forked_owner, forked_repo, headers)
        raise Exception(error_msg)
    
    db.update_build_status(build_id, 'triggered', 
                          f"Workflow file created in forked repository\n"
                          f"Workflow will start automatically\n"
                          f"Monitoring build status...\n")
    
    # 4. Return information about the fork and workflow
    return {
        'original_repo': f"{owner}/{repo}",
        'forked_repo': f"{forked_owner}/{forked_repo}",
        'forked_url': forked_repo_url,
        'branch': branch,
        'workflow_path': workflow_path
    }

def extract_github_repo_info(repo_url):
    """Extract the owner and repository name from a GitHub URL"""
    # Handle different formats of GitHub URLs
    if 'github.com' in repo_url:
        # Extract the owner and repo from URL
        if repo_url.startswith(('http://', 'https://')):
            # Handle full URLs
            pattern = r'github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$'
        else:
            # Handle github.com/owner/repo format
            pattern = r'([^/]+)/([^/]+?)(?:\.git)?$'
        
        match = re.search(pattern, repo_url)
        if not match:
            raise ValueError(f"Invalid GitHub repository URL: {repo_url}")
        
        owner, repo = match.groups()
    else:
        # Assume it's in format owner/repo
        parts = repo_url.split('/')
        if len(parts) != 2:
            raise ValueError(f"Invalid GitHub repository format: {repo_url}")
        owner, repo = parts
    
    # Clean the repo name (remove .git extension if present)
    repo = repo.rstrip('.git')
    
    return owner, repo

def generate_github_workflow(app_name, branch, build_config, build_id):
    """Generate GitHub Actions workflow YAML file for iOS build"""
    # Create a workflow file that will:
    # 1. Check out the repository
    # 2. Set up Xcode
    # 3. Install dependencies
    # 4. Build the app
    # 5. Upload artifacts
    # 6. Send build status back to our app
    
    workflow = f"""name: iOS Build

on:
  push:
    branches: [ {branch} ]
  workflow_dispatch:

jobs:
  build:
    runs-on: macos-latest
    
    env:
      BUILD_ID: {build_id}
      APP_NAME: {app_name or 'iOS App'}
      BUILD_CONFIG: {build_config}
      APP_CENTER_URL: {request.host_url.rstrip('/')}
      
    steps:
      - name: Checkout repository
        uses: actions/checkout@v3
      
      - name: Setup Xcode
        uses: maxim-lobanov/setup-xcode@v1
        with:
          xcode-version: latest-stable
      
      - name: Install dependencies
        run: |
          if [ -f Podfile ]; then
            pod install
          elif [ -f Package.swift ]; then
            swift package resolve
          fi
      
      - name: Find Xcode project or workspace
        id: find-xcode-project
        run: |
          if [ -n "$(find . -name '*.xcworkspace' -not -path '*/Pods/*' -not -path '*/.git/*')" ]; then
            echo "::set-output name=type::workspace"
            echo "::set-output name=file::$(find . -name '*.xcworkspace' -not -path '*/Pods/*' -not -path '*/.git/*' | head -n 1)"
          elif [ -n "$(find . -name '*.xcodeproj')" ]; then 
            echo "::set-output name=type::project"
            echo "::set-output name=file::$(find . -name '*.xcodeproj' | head -n 1)"
          else
            echo "No Xcode project or workspace found"
            exit 1
          fi
      
      - name: Build iOS app
        run: |
          FILE_TYPE="${{{{ steps.find-xcode-project.outputs.type }}}}"
          FILE="${{{{ steps.find-xcode-project.outputs.file }}}}"
          
          if [ "$FILE_TYPE" = "workspace" ]; then
            SCHEME_NAME=$(xcodebuild -list -workspace "$FILE" | grep -A 10 "Schemes:" | grep -v "Schemes:" | head -n 1 | xargs)
            xcodebuild clean archive -workspace "$FILE" -scheme "$SCHEME_NAME" -configuration "$BUILD_CONFIG" -archivePath build/App.xcarchive
          else
            SCHEME_NAME=$(xcodebuild -list -project "$FILE" | grep -A 10 "Schemes:" | grep -v "Schemes:" | head -n 1 | xargs)
            xcodebuild clean archive -project "$FILE" -scheme "$SCHEME_NAME" -configuration "$BUILD_CONFIG" -archivePath build/App.xcarchive
          fi
          
          # Export IPA
          xcodebuild -exportArchive -archivePath build/App.xcarchive -exportOptionsPlist ExportOptions.plist -exportPath build || {{ 
            # If export fails due to missing ExportOptions.plist, create one
            cat > ExportOptions.plist << EOF
          <?xml version="1.0" encoding="UTF-8"?>
          <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
          <plist version="1.0">
          <dict>
            <key>method</key>
            <string>development</string>
            <key>teamID</key>
            <string>ABCDE12345</string>
            <key>compileBitcode</key>
            <false/>
          </dict>
          </plist>
          EOF
            
            # Try export again with the new ExportOptions.plist
            xcodebuild -exportArchive -archivePath build/App.xcarchive -exportOptionsPlist ExportOptions.plist -exportPath build
          }}
      
      - name: Upload IPA as artifact
        uses: actions/upload-artifact@v3
        with:
          name: ios-app
          path: build/*.ipa
      
      - name: Send build results back to App Center
        run: |
          # Find the IPA file
          IPA_FILE=$(find build -name "*.ipa" | head -n 1)
          
          if [ -z "$IPA_FILE" ]; then
            echo "No IPA file found, build may have failed"
            curl -X POST "$APP_CENTER_URL/api/build_complete" \\
              -F "build_id=$BUILD_ID" \\
              -F "status=failed" \\
              -F "log_file=@build-log.txt"
            exit 1
          fi
          
          # Send the build results back to our server
          curl -X POST "$APP_CENTER_URL/api/build_complete" \\
            -F "build_id=$BUILD_ID" \\
            -F "status=completed" \\
            -F "app_file=@$IPA_FILE" \\
            -F "log_file=@build-log.txt"
"""
    return workflow

def cleanup_fork(owner, repo, headers):
    """Delete a forked repository after build is complete"""
    delete_url = f'https://api.github.com/repos/{owner}/{repo}'
    max_retries = 3
    retry_count = 0
    
    # Log the token's first few characters for debugging (safely)
    token_prefix = headers.get('Authorization', '').split(' ')[-1][:5] + '...' if 'Authorization' in headers else 'none'
    logging.info(f"Attempting to clean up repository {owner}/{repo} with token prefix: {token_prefix}")
    
    # Ensure token is properly formatted
    if 'Authorization' in headers and not headers['Authorization'].startswith('Bearer ') and not headers['Authorization'].startswith('token '):
        headers['Authorization'] = f"Bearer {headers['Authorization'].replace('token ', '')}"
        logging.info("Reformatted authorization header to use Bearer format")
        
    while retry_count < max_retries:
        try:
            logging.info(f"Deletion attempt #{retry_count+1} for repository {owner}/{repo}")
            response = requests.delete(delete_url, headers=headers, timeout=30)  # Add timeout
            
            # Log complete response for debugging
            try:
                response_text = response.text
                logging.info(f"Deletion response: HTTP {response.status_code} - {response_text[:100]}...")
            except:
                logging.info(f"Deletion response: HTTP {response.status_code} - [Could not extract response text]")
            
            # Check if deletion was successful (204 No Content or 200 OK)
            if response.status_code in [204, 200]:
                logging.info(f"Successfully deleted forked repository {owner}/{repo}")
                return True
            # Repository not found - consider as success (might have been deleted already)
            elif response.status_code == 404:
                logging.info(f"Repository {owner}/{repo} not found, might have been deleted already")
                return True
            # Rate limit or other temporary issues
            elif response.status_code in [403, 429]:
                retry_count += 1
                logging.warning(f"Rate limit encountered when deleting repo {owner}/{repo}. Retrying in 5 seconds...")
                time.sleep(5)  # Wait 5 seconds before retrying
            else:
                # Try to extract error details
                error_msg = "Unknown error"
                try:
                    error_details = response.json()
                    error_msg = error_details.get('message', 'Unknown error')
                    # Look for specific GitHub error messages
                    if "Bad credentials" in error_msg:
                        logging.error(f"GitHub API token is invalid or expired. Please generate a new token.")
                        # No point in retrying with bad credentials
                        return False
                    elif "Not Found" in error_msg and response.status_code == 404:
                        logging.info(f"Repository {owner}/{repo} not found, considering cleanup successful")
                        return True
                    elif "Must have admin rights" in error_msg or "Permission denied" in error_msg:
                        logging.error(f"GitHub API token doesn't have permission to delete repositories")
                        # No point in retrying without proper permissions
                        return False
                except:
                    pass
                    
                logging.error(f"Failed to delete repository {owner}/{repo}: {response.status_code} - {error_msg}")
                retry_count += 1
                time.sleep(2)
        except requests.RequestException as e:
            logging.error(f"Network error deleting forked repository {owner}/{repo}: {str(e)}")
            retry_count += 1
            time.sleep(2)
        except Exception as e:
            logging.error(f"Unexpected error deleting forked repository {owner}/{repo}: {str(e)}")
            retry_count += 1
            time.sleep(2)
    
    logging.error(f"Failed to delete repository {owner}/{repo} after {max_retries} attempts")
    return False

def monitor_github_workflow(build_id, fork_info):
    """Monitor a GitHub Actions workflow and update build status"""
    # This would be run in a background thread to poll GitHub for status updates
    # For now, we'll leave this as a placeholder and implement the callback API endpoint instead
    pass

@app.route('/api/build_complete', methods=['POST'])
def api_build_complete():
    """
    API endpoint for GitHub Actions to report build completion
    
    This endpoint receives build results from GitHub Actions workflows
    including the build status, IPA file, and build logs.
    """
    # Validate request
    if 'build_id' not in request.form:
        return jsonify({"error": "build_id is required"}), 400
    
    build_id = request.form['build_id']
    status = request.form.get('status', 'unknown')
    
    # Get the build from the database
    build = db.get_build(build_id)
    if not build:
        return jsonify({"error": f"Build with ID {build_id} not found"}), 404
    
    # Set end time for all completed, failed or cancelled builds
    current_time = datetime.now().isoformat()
    should_set_end_time = status in ['completed', 'failed', 'cancelled']
    end_time = current_time if should_set_end_time else None
    
    # Process log file if provided
    log_content = ""
    if 'log_file' in request.files:
        log_file = request.files['log_file']
        log_content = log_file.read().decode('utf-8', errors='replace')
        db.update_build_status(build_id, status, log_content, end_time=end_time)
    
    # Process app file (IPA) if provided and status is completed
    if status == 'completed' and 'app_file' in request.files:
        try:
            app_file = request.files['app_file']
            file_data = app_file.read()
            filename = secure_filename(app_file.filename)
            
            # Generate file_id and store in MongoDB
            file_id = str(uuid.uuid4())
            db.save_file(file_id, filename, file_data, 'application/octet-stream')
            
            # Extract app info from the IPA
            app_info = extract_minimal_app_info(file_data, filename, build_id)
            app_info['file_id'] = file_id
            app_info['filename'] = filename
            app_info['size'] = len(file_data)
            app_info['build_id'] = build_id
            
            # Save app information to database
            db.save_app(app_info)
            
            # Update build with completion information
            db.update_build_status(build_id, 'completed', 
                                  f"Build completed successfully. App ID: {app_info['id']}\n", 
                                  end_time=current_time)
            
            # Clean up the forked repository
            if 'fork_info' in build:
                try:
                    fork_info = build['fork_info']
                    owner, repo = fork_info['forked_repo'].split('/')
                    
                    # Make sure we have a valid token
                    if not GITHUB_API_TOKEN:
                        db.update_build_status(build_id, 'completed', f"Warning: Cannot clean up forked repository - GitHub API token is missing.\n")
                        return jsonify({"status": "success", "message": "Build artifacts processed successfully, but fork cleanup failed due to missing token"})
                        
                    # Properly format the authorization header
                    headers = {
                        'Accept': 'application/vnd.github.v3+json'
                    }
                    
                    if GITHUB_API_TOKEN.startswith('Bearer '):
                        headers['Authorization'] = GITHUB_API_TOKEN
                    elif GITHUB_API_TOKEN.startswith('token '):
                        headers['Authorization'] = GITHUB_API_TOKEN
                    else:
                        headers['Authorization'] = f'Bearer {GITHUB_API_TOKEN}'
                    
                    # Add marker to build log that cleanup is being attempted
                    db.update_build_status(build_id, 'completed', f"Attempting to clean up forked repository {owner}/{repo}...\n")
                    
                    # Try to clean up with extended timeout
                    cleanup_success = cleanup_fork(owner, repo, headers)
                    
                    if cleanup_success:
                        db.update_build_status(build_id, 'completed', f"Forked repository {owner}/{repo} has been cleaned up.\n")
                    else:
                        db.update_build_status(build_id, 'completed', f"Warning: Failed to clean up forked repository {owner}/{repo}. Please delete it manually.\n")
                except Exception as cleanup_error:
                    logging.error(f"Error cleaning up forked repo: {str(cleanup_error)}")
                    db.update_build_status(build_id, 'completed', f"Warning: Failed to clean up forked repository: {str(cleanup_error)}\n")
                
            return jsonify({"status": "success", "message": "Build artifacts processed successfully"})
            
        except Exception as e:
            error_msg = f"Error processing build artifacts: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)
            db.update_build_status(build_id, 'failed', error_msg, end_time=current_time)
            
            # Attempt to clean up the forked repository even on error
            cleanup_fork_on_failure(build)
            
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # If status is failed or cancelled, update build status and clean up fork
    elif status in ['failed', 'cancelled']:
        message = "GitHub Actions build failed. See log for details." if status == 'failed' else "Build was cancelled."
        db.update_build_status(build_id, status, message, end_time=current_time)
        
        # Clean up forked repository
        cleanup_fork_on_failure(build)
    
    return jsonify({"status": "success", "message": f"Build status updated to {status}"})

def cleanup_fork_on_failure(build):
    """Helper function to clean up forked repositories for failed or cancelled builds"""
    if 'fork_info' not in build or not GITHUB_API_TOKEN:
        logging.error("Cannot clean up fork: missing fork_info or GitHub API token")
        return
    
    try:
        fork_info = build['fork_info']
        owner, repo = fork_info['forked_repo'].split('/')
        
        # Properly format the authorization header
        headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        
        if GITHUB_API_TOKEN.startswith('Bearer '):
            headers['Authorization'] = GITHUB_API_TOKEN
        elif GITHUB_API_TOKEN.startswith('token '):
            headers['Authorization'] = GITHUB_API_TOKEN
        else:
            headers['Authorization'] = f'Bearer {GITHUB_API_TOKEN}'
        
        # Add marker to build log that cleanup is being attempted
        db.update_build_status(build['id'], build.get('status', 'failed'), f"Attempting to clean up forked repository {owner}/{repo}...\n")
        
        # Try to clean up with extended timeout
        cleanup_success = cleanup_fork(owner, repo, headers)
        
        status_msg = f"Forked repository {owner}/{repo} has been cleaned up." if cleanup_success else f"Warning: Failed to clean up forked repository {owner}/{repo}. Please delete it manually."
        db.update_build_status(build['id'], build.get('status', 'failed'), status_msg)
    except Exception as cleanup_error:
        logging.error(f"Error cleaning up forked repo: {str(cleanup_error)}")
        try:
            db.update_build_status(build['id'], build.get('status', 'failed'), f"Warning: Failed to clean up forked repository: {str(cleanup_error)}\n")
        except:
            logging.error("Could not update build status with cleanup error")

def extract_minimal_app_info(file_data, filename, build_id):
    """Extract minimal app information from IPA data without full processing"""
    # This is a simplified version just to create an app entry
    app_id = str(uuid.uuid4())
    build = db.get_build(build_id)
    
    # Use build information where possible
    app_name = build.get('app_name', filename.split('.')[0])
    
    # Create a temporary file to check if we can extract more info
    with tempfile.NamedTemporaryFile(delete=False, suffix='.ipa') as temp_file:
        temp_file.write(file_data)
        temp_path = temp_file.name
    
    try:
        # Try to extract more info from the IPA if possible
        with zipfile.ZipFile(temp_path, 'r') as ipa:
            # Try to find Info.plist to extract more metadata
            plist_path = None
            for f in ipa.namelist():
                if 'Info.plist' in f:
                    plist_path = f
                    break
                    
            if plist_path:
                with ipa.open(plist_path) as plist_file:
                    plist_data = plistlib.load(plist_file)
                    app_name = plist_data.get('CFBundleDisplayName', plist_data.get('CFBundleName', app_name))
                    version = plist_data.get('CFBundleShortVersionString', '1.0.0')
                    bundle_id = plist_data.get('CFBundleIdentifier', f"com.github.{app_name.lower().replace(' ', '')}")
            else:
                # If we can't find Info.plist, use defaults
                version = '1.0.0'
                bundle_id = f"com.github.{app_name.lower().replace(' ', '')}"
                
            # Try to extract app icon
            icon_path = None
            for f in ipa.namelist():
                if 'AppIcon60x60@2x.png' in f:
                    icon_path = f
                    break
                    
            if icon_path:
                with ipa.open(icon_path) as icon_file:
                    icon_data = icon_file.read()
                    icon_b64 = base64.b64encode(icon_data).decode()
                    icon = f"data:image/png;base64,{icon_b64}"
            else:
                # Use defaultApp.png as fallback
                icon = load_default_icon()
    except Exception as e:
        logging.warning(f"Error extracting app info from IPA: {str(e)}")
        # Use default values if extraction fails
        version = '1.0.0'
        bundle_id = f"com.github.{app_name.lower().replace(' ', '')}"
        icon = load_default_icon()
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_path)
        except:
            pass
    
    return {
        "id": app_id,
        "name": app_name,
        "version": version,
        "bundle_id": bundle_id,
        "icon": icon,
        "upload_date": datetime.now().isoformat(),
        "source": f"GitHub: {build.get('repo_url', 'Unknown')} (branch: {build.get('branch', 'Unknown')})",
        "versions": [{
            "version": version,
            "upload_date": datetime.now().isoformat()
        }]
    }

if __name__ == '__main__':
    # Run the application
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=('cert.pem', 'key.pem'))