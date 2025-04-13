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
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify, session, g
from dotenv import load_dotenv

from werkzeug.utils import secure_filename
from zipfile import ZipFile

from PIL import Image
import base64
import io
import git

# Import database module
import database as db

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'development-key')

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'ipa'}
BUILD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'builds')
APPLE_TEAM_ID = os.environ.get('APPLE_TEAM_ID', '')  # Get from environment variable
GITHUB_REPO_URL = os.environ.get('GITHUB_REPO_URL', 'https://github.com/username/app-dist')  # GitHub repository URL

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB max upload size

# Create necessary directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BUILD_FOLDER, exist_ok=True)

# Initialize database
db.initialize_db()

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
        status (str): The new status (queued, in_progress, completed, failed)
        log (str, optional): The build log to append
        end_time (str, optional): The end time of the build
    
    Returns:
        bool: True if successful, False otherwise
    """
    build = db.get_build(build_id)
    if not build:
        return False
        
    build['status'] = status
    
    if log is not None:
        build['log'] = log
        
    if end_time is not None:
        build['end_time'] = end_time
        
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

def extract_app_info(filepath):
    """Extract app information from IPA file"""
    app_id = str(uuid.uuid4())
    filename = os.path.basename(filepath)
    
    # Extract info from IPA file
    with zipfile.ZipFile(filepath, 'r') as ipa:
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
    
    return {
        "id": app_id,
        "name": app_name,
        "version": version,
        "bundle_id": bundle_id,
        "filename": filename,
        "upload_date": datetime.now().isoformat(),
        "size": os.path.getsize(filepath),
        "icon": icon,
        "versions": [{
            "version": version,
            "filename": filename,
            "upload_date": datetime.now().isoformat(),
            "size": os.path.getsize(filepath)
        }]
    }

def add_app_version(app_id, filepath, version=None):
    """Add a new version to an existing app"""
    app = db.get_app(app_id)
    if not app:
        return None
        
    filename = os.path.basename(filepath)
    
    # If version is not provided, extract it from the IPA
    if version is None:
        try:
            with zipfile.ZipFile(filepath, 'r') as ipa:
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
    
    # Update app with new version
    app['version'] = version
    app['filename'] = filename
    app['size'] = os.path.getsize(filepath)
    
    # Add to versions history
    app['versions'].append({
        "version": version,
        "filename": filename,
        "upload_date": datetime.now().isoformat(),
        "size": os.path.getsize(filepath)
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
        
        # Verify the BUILD_FOLDER exists and is accessible
        logging.info(f"Build folder path: {BUILD_FOLDER}")
        if not os.path.exists(BUILD_FOLDER):
            error_msg = f"BUILD_FOLDER does not exist: {BUILD_FOLDER}"
            logging.error(error_msg)
            db.update_build_status(build_id, 'failed', error_msg)
            return
            
        # Update build status
        db.update_build_status(build_id, 'building', f"Starting build process for {repo_url} (branch: {branch})\n")
        
        # Create a temporary directory for the build
        build_dir = os.path.join(BUILD_FOLDER, build_id)
        logging.info(f"Creating build directory: {build_dir}")
        os.makedirs(build_dir, exist_ok=True)
        
        # Verify git is installed and accessible
        try:
            git_version = subprocess.run(['git', '--version'], capture_output=True, text=True, check=True)
            logging.info(f"Git version: {git_version.stdout.strip()}")
        except Exception as e:
            error_msg = f"Git command not found. Make sure git is installed and in PATH: {str(e)}"
            logging.error(error_msg)
            db.update_build_status(build_id, 'failed', error_msg)
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
                db.update_build_status(build_id, 'failed', error_msg)
                return
                
            db.update_build_status(build_id, 'building', f"Repository cloned successfully\n")
        except Exception as e:
            error_msg = f"Failed to clone repository: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)
            db.update_build_status(build_id, 'failed', error_msg)
            return
        
        # Verify build directory contents
        try:
            logging.info(f"Listing build directory contents: {build_dir}")
            for root, dirs, files in os.walk(build_dir):
                relative_path = os.path.relpath(root, build_dir)
                logging.info(f"Directory: {relative_path}")
                for f in files:
                    logging.info(f"  File: {os.path.join(relative_path, f)}")
        except Exception as e:
            logging.warning(f"Error listing directory contents: {str(e)}")
        
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
            db.update_build_status(build_id, 'failed', error_msg)
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
        
        # Verify the build file exists
        if not os.path.exists(build_file):
            error_msg = f"Selected build file does not exist: {build_file}"
            logging.error(error_msg)
            db.update_build_status(build_id, 'failed', error_msg)
            return
        
        # Check if Podfile exists and run pod install if needed
        podfile_path = os.path.join(os.path.dirname(build_file), 'Podfile')
        if os.path.exists(podfile_path):
            db.update_build_status(build_id, 'building', "Podfile found, running pod install...\n")
            try:
                # Verify pod command is available
                try:
                    pod_version = subprocess.run(['pod', '--version'], capture_output=True, text=True, check=True)
                    logging.info(f"CocoaPods version: {pod_version.stdout.strip()}")
                except Exception as e:
                    warning_msg = f"CocoaPods command not found. Skipping pod install: {str(e)}"
                    logging.warning(warning_msg)
                    db.update_build_status(build_id, 'building', f"{warning_msg}\n")
                    # Continue without pod install
                else:
                    # Run pod install if available
                    pod_result = subprocess.run(['pod', 'install'], 
                                              cwd=os.path.dirname(build_file),
                                              capture_output=True, text=True)
                    db.update_build_status(build_id, 'building', f"Pod install output: {pod_result.stdout}\n")
                    if pod_result.returncode != 0:
                        db.update_build_status(build_id, 'building', f"Pod install error: {pod_result.stderr}\n")
            except Exception as e:
                error_msg = f"Error running pod install: {str(e)}\n{traceback.format_exc()}"
                logging.error(error_msg)
                db.update_build_status(build_id, 'building', error_msg)
                # Continue anyway as pod install might not be critical
        
        # Set up build parameters
        scheme_name = app_name or os.path.basename(build_file).split('.')[0]
        archive_path = os.path.join(build_dir, f"{scheme_name}.xcarchive")
        ipa_dir = os.path.join(build_dir, "export")
        os.makedirs(ipa_dir, exist_ok=True)
        ipa_path = os.path.join(ipa_dir, f"{scheme_name}.ipa")
        
        # Check if we're on macOS and have xcodebuild available
        is_macos = sys.platform == 'darwin'
        xcodebuild_available = False
        
        if is_macos:
            try:
                xcodebuild_version = subprocess.run(['xcodebuild', '-version'], 
                                                  capture_output=True, text=True, check=True)
                xcodebuild_available = True
                db.update_build_status(build_id, 'building', 
                                      f"Found Xcode: {xcodebuild_version.stdout.strip()}\n")
                
                # Check if we need to use a specific Xcode version
                build_record = db.get_build(build_id)
                requested_xcode = build_record.get('xcode_version', 'latest')
                
                if requested_xcode != 'latest':
                    db.update_build_status(build_id, 'building', 
                                         f"Requested Xcode version: {requested_xcode}\n")
                    
                    # Try to select the requested Xcode version using xcode-select
                    try:
                        # First, check available Xcode installations
                        xcode_select_result = subprocess.run(['mdfind', 'kMDItemCFBundleIdentifier="com.apple.dt.Xcode"'], 
                                                          capture_output=True, text=True)
                        
                        available_xcodes = xcode_select_result.stdout.strip().split('\n')
                        db.update_build_status(build_id, 'building', 
                                             f"Found {len(available_xcodes)} Xcode installations\n")
                        
                        # Look for an Xcode version that matches the requested version
                        matching_xcode = None
                        for xcode_path in available_xcodes:
                            if not xcode_path:
                                continue
                                
                            # Get the version info for this Xcode
                            version_plist = os.path.join(xcode_path, 'Contents/version.plist')
                            if os.path.exists(version_plist):
                                try:
                                    with open(version_plist, 'rb') as f:
                                        plist_data = plistlib.load(f)
                                        version = plist_data.get('CFBundleShortVersionString', '')
                                        if version.startswith(requested_xcode):
                                            matching_xcode = xcode_path
                                            break
                                except:
                                    continue
                        
                        if matching_xcode:
                            db.update_build_status(build_id, 'building', 
                                                 f"Using Xcode at: {matching_xcode}\n")
                            
                            # Set the active developer directory
                            subprocess.run(['sudo', 'xcode-select', '--switch', matching_xcode], 
                                         capture_output=True, text=True)
                        else:
                            db.update_build_status(build_id, 'building', 
                                                 f"Requested Xcode version {requested_xcode} not found. Using default.\n")
                    except Exception as e:
                        db.update_build_status(build_id, 'building', 
                                             f"Error selecting Xcode version: {str(e)}. Using default.\n")
                        
            except Exception as e:
                db.update_build_status(build_id, 'building', 
                                      f"On macOS but xcodebuild not found: {str(e)}\n")
        
        if is_macos and xcodebuild_available:
            # Set up build parameters
            db.update_build_status(build_id, 'building', "Preparing to build with Xcode...\n")
            
            # Find the scheme name if not specified
            if not app_name:
                try:
                    if build_type == 'workspace':
                        scheme_list_cmd = ['xcodebuild', '-workspace', build_file, '-list']
                    else:
                        scheme_list_cmd = ['xcodebuild', '-project', build_file, '-list']
                    
                    scheme_result = subprocess.run(scheme_list_cmd, 
                                                cwd=os.path.dirname(build_file),
                                                capture_output=True, text=True)
                    
                    # Parse schemes from the output
                    schemes = []
                    in_schemes = False
                    for line in scheme_result.stdout.splitlines():
                        if "Schemes:" in line:
                            in_schemes = True
                        elif in_schemes and line.strip():
                            schemes.append(line.strip())
                    
                    if schemes:
                        scheme_name = schemes[0]  # Use the first scheme
                        db.update_build_status(build_id, 'building', 
                                             f"Auto-detected scheme: {scheme_name}\n")
                except Exception as e:
                    db.update_build_status(build_id, 'building', 
                                         f"Error detecting schemes: {str(e)}. Will use folder name.\n")
            
            # Create the build command
            if build_type == 'workspace':
                build_cmd = [
                    'xcodebuild', '-workspace', build_file, 
                    '-scheme', scheme_name, 
                    '-configuration', build_config,
                    '-archivePath', archive_path,
                    'archive'
                ]
            else:
                build_cmd = [
                    'xcodebuild', '-project', build_file, 
                    '-scheme', scheme_name, 
                    '-configuration', build_config,
                    '-archivePath', archive_path,
                    'archive'
                ]
                
            # Add team ID if available
            team_id = db.get_build(build_id).get('team_id')
            if team_id:
                build_cmd.extend(['-teamID', team_id])
                
            # Log the build command
            db.update_build_status(build_id, 'building', 
                                  f"Running build command: {' '.join(build_cmd)}\n")
            
            # Run the build
            try:
                build_result = subprocess.run(build_cmd, 
                                           cwd=os.path.dirname(build_file),
                                           capture_output=True, text=True)
                
                # Log the output
                db.update_build_status(build_id, 'building', 
                                     f"Build output:\n{build_result.stdout}\n")
                
                if build_result.returncode != 0:
                    db.update_build_status(build_id, 'building', 
                                         f"Build error:\n{build_result.stderr}\n")
                    raise Exception(f"xcodebuild archive failed with code {build_result.returncode}")
                
                # Create export options plist
                export_plist_path = os.path.join(build_dir, "ExportOptions.plist")
                with open(export_plist_path, 'w') as f:
                    f.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>development</string>
    <key>compileBitcode</key>
    <false/>
    <key>teamID</key>
    <string>{team_id or "YOUR_TEAM_ID"}</string>
</dict>
</plist>""")
                
                # Export the IPA
                export_cmd = [
                    'xcodebuild', '-exportArchive',
                    '-archivePath', archive_path,
                    '-exportPath', ipa_dir,
                    '-exportOptionsPlist', export_plist_path
                ]
                
                db.update_build_status(build_id, 'building', 
                                     f"Exporting IPA with command: {' '.join(export_cmd)}\n")
                
                export_result = subprocess.run(export_cmd,
                                            capture_output=True, text=True)
                
                # Log the output
                db.update_build_status(build_id, 'building', 
                                     f"Export output:\n{export_result.stdout}\n")
                
                if export_result.returncode != 0:
                    db.update_build_status(build_id, 'building', 
                                         f"Export error:\n{export_result.stderr}\n")
                    raise Exception(f"xcodebuild export failed with code {export_result.returncode}")
                
                # Find the IPA file
                ipa_files = []
                for file in os.listdir(ipa_dir):
                    if file.endswith('.ipa'):
                        ipa_files.append(os.path.join(ipa_dir, file))
                
                if not ipa_files:
                    raise Exception(f"No IPA file found in {ipa_dir}")
                
                ipa_path = ipa_files[0]
                db.update_build_status(build_id, 'building', f"IPA file created at: {ipa_path}\n")
                
            except Exception as e:
                error_msg = f"Error building IPA: {str(e)}\n{traceback.format_exc()}"
                logging.error(error_msg)
                db.update_build_status(build_id, 'failed', error_msg)
                return
                
        else:
            # Not on macOS or xcodebuild not available - create a placeholder IPA
            db.update_build_status(build_id, 'building', 
                                 "Running on non-macOS system or xcodebuild not available.\n" + 
                                 "Creating a simulated build instead of running xcodebuild.\n" +
                                 "For real builds, please run on macOS with Xcode installed.\n")
            
            # Log what would have been the build command
            if build_type == 'workspace':
                build_cmd = [
                    'xcodebuild', '-workspace', build_file, 
                    '-scheme', scheme_name, 
                    '-configuration', build_config,
                    '-archivePath', archive_path,
                    'archive'
                ]
            else:
                build_cmd = [
                    'xcodebuild', '-project', build_file, 
                    '-scheme', scheme_name, 
                    '-configuration', build_config,
                    '-archivePath', archive_path,
                    'archive'
                ]
                
            # Add team ID if available
            team_id = db.get_build(build_id).get('team_id')
            if team_id:
                build_cmd.extend(['-teamID', team_id])
                
            # Log the command that would have been run (for documentation)
            logging.info(f"Simulating build command: {' '.join(build_cmd)}")
            db.update_build_status(build_id, 'building', f"Build command that would run on macOS: {' '.join(build_cmd)}\n")
            
            # Create a mock archive directory
            mock_archive_dir = os.path.join(build_dir, "MockArchive")
            os.makedirs(mock_archive_dir, exist_ok=True)
            
            db.update_build_status(build_id, 'building', "Creating placeholder IPA file...\n")
            
            # Create a simple placeholder IPA (zip file)
            try:
                with zipfile.ZipFile(ipa_path, 'w') as placeholder_ipa:
                    # Add metadata file
                    placeholder_info = os.path.join(build_dir, "info.txt")
                    with open(placeholder_info, 'w') as f:
                        f.write(f"Placeholder IPA for {app_name or scheme_name} built from {repo_url} (branch: {branch})\n\n")
                        f.write("NOTE: This is a simulated build because the build was not run on macOS or xcodebuild was not available.\n")
                        f.write("For real builds, please run on macOS with Xcode installed.\n")
                        
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
                    
                logging.info(f"Created placeholder IPA at: {ipa_path}")
                db.update_build_status(build_id, 'building', f"Created placeholder IPA: {ipa_path}\n")
            except Exception as e:
                error_msg = f"Error creating placeholder IPA: {str(e)}\n{traceback.format_exc()}"
                logging.error(error_msg)
                db.update_build_status(build_id, 'failed', error_msg)
                return
        
        # Read the IPA file
        try:
            with open(ipa_path, 'rb') as f:
                ipa_data = f.read()
            logging.info(f"Read IPA file of size: {len(ipa_data)} bytes")
        except Exception as e:
            error_msg = f"Error reading IPA file: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)
            db.update_build_status(build_id, 'failed', error_msg)
            return
        
        # Generate a default icon for the app
        default_icon = load_default_icon()
        
        # Create app entry in the database
        app_info = {
            'id': str(uuid.uuid4()),
            'name': app_name or scheme_name,
            'bundle_id': f"com.github.{scheme_name.lower()}",
            'version': '1.0.0',
            'build_number': '1',
            'icon': default_icon,
            'ipa_data': base64.b64encode(ipa_data).decode('utf-8'),
            'creation_date': datetime.now().isoformat(),
            'source': f"GitHub: {repo_url} (branch: {branch})",
            'build_id': build_id  # Store the build ID to link back to the build
        }
        
        try:
            db.save_app(app_info)
            logging.info(f"Saved app to database with ID: {app_info['id']}")
            db.update_build_status(build_id, 'completed', f"Build completed successfully. App ID: {app_info['id']}\n")
        except Exception as e:
            error_msg = f"Error saving app to database: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)
            db.update_build_status(build_id, 'failed', error_msg)
            return
        
    except Exception as e:
        error_msg = f"Build failed with error: {str(e)}\n{traceback.format_exc()}"
        logging.error(error_msg)
        db.update_build_status(build_id, 'failed', error_msg)
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
    return render_template('manage_users.html', users=users)

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
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            
            # If no version provided, try to extract it from the IPA
            if not app_version:
                try:
                    with zipfile.ZipFile(filepath, 'r') as ipa:
                        plist_path = None
                        for f in ipa.namelist():
                            if 'Info.plist' in f:
                                plist_path = f
                                break
                                
                        if plist_path:
                            with ipa.open(plist_path) as plist_file:
                                plist_data = plistlib.load(plist_file)
                                app_version = plist_data.get('CFBundleShortVersionString', '1.0.0')
                        else:
                            app_version = "1.0.0"
                except Exception as e:
                    logging.error(f"Error extracting version from IPA: {str(e)}")
                    app_version = "1.0.0"
                    
                logging.info(f"Auto-detected version {app_version} from IPA file")
            
            if app_id:  # Adding a new version to existing app
                app = db.get_app(app_id)
                if not app:
                    flash("App not found")
                    return redirect(request.url)
                
                # Update app with new version
                app['version'] = app_version
                app['filename'] = filename
                app['size'] = os.path.getsize(filepath)
                
                # Add to versions history
                app['versions'].append({
                    "version": app_version,
                    "filename": filename,
                    "upload_date": datetime.now().isoformat(),
                    "size": os.path.getsize(filepath)
                })
                
                # Save updated app to database
                db.save_app(app)
                flash(f"New version {app_version} added for {app['name']}")
            else:  # Adding a new app
                # Extract info from IPA file for defaults
                extracted_info = extract_app_info(filepath)
                
                # Create new app with user-provided info
                app_info = {
                    "id": extracted_info["id"],
                    "name": app_name,
                    "version": app_version,
                    "bundle_id": bundle_id if bundle_id else extracted_info["bundle_id"],
                    "filename": filename,
                    "upload_date": datetime.now().isoformat(),
                    "size": os.path.getsize(filepath),
                    "icon": extracted_info["icon"],
                    "versions": [{
                        "version": app_version,
                        "filename": filename,
                        "upload_date": datetime.now().isoformat(),
                        "size": os.path.getsize(filepath)
                    }]
                }
                
                db.save_app(app_info)
                flash(f"App {app_name} (v{app_version}) uploaded successfully")
                
            return redirect(url_for('index'))
    
    # For GET request, show upload form
    apps = db.get_apps()
    return render_template('upload.html', apps=apps)

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
        
        # Handle certificate and provisioning profile uploads
        certificate_path = None
        profile_path = None
        
        if 'certificate' in request.files and request.files['certificate'].filename:
            cert_file = request.files['certificate']
            certificate_path = os.path.join(BUILD_FOLDER, f"cert_{uuid.uuid4()}.p12")
            cert_file.save(certificate_path)
        
        if 'provisioning_profile' in request.files and request.files['provisioning_profile'].filename:
            profile_file = request.files['provisioning_profile']
            profile_path = os.path.join(BUILD_FOLDER, f"profile_{uuid.uuid4()}.mobileprovision")
            profile_file.save(profile_path)
        
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
            'log': f"Build queued for {repo_url} (branch: {branch})\n"
        }
        
        # Save the build record
        db.save_build(new_build)
        
        # Start the build process in a background thread
        thread = threading.Thread(
            target=build_ios_app_from_github,
            args=(build_id, repo_url, branch, app_name, build_config, certificate_path, profile_path)
        )
        thread.daemon = True
        thread.start()
        
        flash(f"Build for {app_name} from {repo_url} has been queued")
        return redirect(url_for('github_build'))
    
    # For GET request, show the build form and list recent builds
    builds = db.get_builds()
    # Sort builds by start time (newest first)
    builds.sort(key=lambda x: x.get('start_time', ''), reverse=True)
    
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
    
    # Generate a filename for the IPA
    filename = f"{app['name'].replace(' ', '_')}_{app['version']}.ipa"
    
    # For GitHub-built apps with ipa_data
    if 'ipa_data' in app:
        # Create a temporary file with the IPA data
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, filename)
        
        try:
            # Decode base64 data and write to temporary file
            ipa_data = base64.b64decode(app['ipa_data'])
            with open(temp_file_path, 'wb') as f:
                f.write(ipa_data)
                
            return send_from_directory(temp_dir, filename, as_attachment=True)
        except Exception as e:
            flash(f"Error preparing download: {str(e)}")
            return redirect(url_for('github_build'))
    elif 'filename' in app:
        # For directly uploaded apps or if ipa_data is not present
        return send_from_directory(UPLOAD_FOLDER, os.path.basename(app['filename']), as_attachment=True)
    else:
        flash("App does not have an associated IPA file")
        return redirect(url_for('github_build'))

@app.route('/build_log/<build_id>')
@login_required
def build_log(build_id):
    """View the log for a build"""
    build = db.get_build(build_id)
    if not build:
        flash("Build not found")
        return redirect(url_for('github_build'))
    
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
        
    # Check if this is a GitHub-built app (which has ipa_data instead of a file)
    if 'ipa_data' in app:
        # Create a temporary file with the IPA data
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, filename)
        
        try:
            # Decode base64 data and write to temporary file
            ipa_data = base64.b64decode(app['ipa_data'])
            with open(temp_file_path, 'wb') as f:
                f.write(ipa_data)
                
            return send_from_directory(temp_dir, filename, as_attachment=True)
        except Exception as e:
            flash(f"Error preparing download: {str(e)}")
            return redirect(url_for('app_detail', app_id=app_id))
    else:
        # For traditional uploads, serve from the upload folder
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

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
        if 'ipa_data' in app:
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
    if 'ipa_data' in app:
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
            # Delete physical files for manually uploaded apps
            if 'versions' in app and app['versions']:
                for version in app['versions']:
                    try:
                        if 'filename' in version:
                            filepath = os.path.join(UPLOAD_FOLDER, version['filename'])
                            if os.path.exists(filepath):
                                os.remove(filepath)
                                logging.info(f"Deleted file: {filepath}")
                    except Exception as e:
                        logging.error(f"Error deleting file for version {version.get('version', 'unknown')}: {str(e)}")
            
            # Delete the app from the database
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=('cert.pem', 'key.pem'))