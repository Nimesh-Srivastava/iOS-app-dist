import os
import threading
import database as db
import logging
from utils.file_utils import extract_app_info, extract_minimal_app_info
from datetime import datetime

def add_app_version(app_id, file_data, filename, version=None, release_notes=None):
    """
    Add a new version of an app to the database
    
    Args:
        app_id (str): The app ID
        file_data (bytes): The IPA file data
        filename (str): The filename of the IPA file
        version (str, optional): The version string
        release_notes (str, optional): Release notes for this version
        
    Returns:
        dict: The app data
    """
    # Get app if it exists
    app = db.get_app(app_id)
    
    # Extract app info from IPA
    app_info = extract_app_info(file_data, filename)
    
    # If app exists, preserve some fields
    if app:
        old_versions = app.get('versions', [])
        
        # Create version entry for the old app
        if app.get('version') and app.get('build_number'):
            old_version = {
                'version': app.get('version'),
                'build_number': app.get('build_number'),
                'filename': app.get('filename'),
                'file_id': app.get('file_id'),
                'upload_date': app.get('upload_date'),
                'release_notes': app.get('release_notes')
            }
            
            # Only add if it doesn't exist already
            if not any(v.get('version') == old_version['version'] and 
                     v.get('build_number') == old_version['build_number'] 
                     for v in old_versions):
                old_versions.append(old_version)
        
        # Update app with new values
        app['version'] = version or app_info['version']
        app['build_number'] = app_info['build_number']
        app['filename'] = filename
        app['file_id'] = app_info['file_id']
        app['upload_date'] = app_info['upload_date']
        app['versions'] = old_versions
        app['release_notes'] = release_notes
        
        # Save the file with the new file_id
        db.save_file(app_info['file_id'], filename, file_data)
        
        # Save updated app to database
        db.save_app(app)
        return app
    else:
        # Create new app
        new_app = app_info.copy()
        if version:
            new_app['version'] = version
        new_app['versions'] = []
        new_app['release_notes'] = release_notes
        
        # Save the file
        db.save_file(app_info['file_id'], filename, file_data)
        
        # Save app to database
        db.save_app(new_app)
        return new_app

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

def build_ios_app_from_github(build_id, repo_url, branch, app_name, build_config='Release', 
                        certificate_path=None, provisioning_profile=None, release_notes=None):
    """
    Build an iOS app from a GitHub repository
    
    Args:
        build_id (str): The build ID
        repo_url (str): The GitHub repository URL
        branch (str): The branch to build from
        app_name (str): The name of the app
        build_config (str): The build configuration (Debug/Release)
        certificate_path (str, optional): Path to the signing certificate
        provisioning_profile (str, optional): Path to the provisioning profile
        release_notes (str, optional): Release notes for this version
        
    Returns:
        bool: True if build started successfully, False otherwise
    """
    # Set status to in progress
    update_build_status(build_id, 'in_progress', "Starting build...")
    
    # Import here to avoid circular import
    from utils.github_utils import fork_and_setup_github_workflow, monitor_github_workflow
    
    # Setup GitHub workflow
    success, message, fork_info = fork_and_setup_github_workflow(
        build_id, repo_url, branch, app_name, build_config
    )
    
    if not success:
        update_build_status(build_id, 'failed', message)
        return False
    
    # Update build with fork info and release notes
    build = db.get_build(build_id)
    if build:
        build['fork_info'] = fork_info
        build['status'] = 'in_progress'
        build['log'] = message
        if release_notes:
            build['release_notes'] = release_notes
        db.save_build(build)
    
    # Start a thread to monitor the workflow
    monitor_thread = threading.Thread(
        target=monitor_github_workflow,
        args=(build_id, fork_info)
    )
    monitor_thread.daemon = True
    monitor_thread.start()
    
    return True

def check_abandoned_builds():
    """
    Check for abandoned builds and mark them as failed
    This is meant to be called periodically
    """
    builds = db.get_builds()
    
    for build in builds:
        # Only check in-progress builds
        if build.get('status') != 'in_progress':
            continue
        
        # Check if it has been running for too long
        start_time = datetime.fromisoformat(build.get('start_time', ''))
        current_time = datetime.now()
        
        # If running for more than 1 hour and no updates in log for more than 15 minutes
        time_diff = (current_time - start_time).total_seconds()
        if time_diff > 3600:  # 1 hour
            update_build_status(
                build['id'], 
                'failed', 
                "Build timed out. No updates received for over an hour.",
                current_time.isoformat()
            )
            
            # Clean up GitHub fork if needed
            if 'fork_info' in build:
                from utils.github_utils import cleanup_fork_on_failure
                cleanup_fork_on_failure(build) 