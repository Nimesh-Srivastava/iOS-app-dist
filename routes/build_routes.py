from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, abort, jsonify
import database as db
import os
import io
import uuid
from datetime import datetime
import logging
import base64
import threading

from utils.decorators import login_required, admin_required, admin_or_developer_required
from utils.github_utils import verify_github_token, fetch_branches, cleanup_fork
from models import build_ios_app_from_github, update_build_status

build_bp = Blueprint('build', __name__)

@build_bp.route('/github_build', methods=['GET', 'POST'])
@admin_or_developer_required
def github_build():
    if request.method == 'POST':
        # Validate inputs
        repo_url = request.form.get('repo_url', '').strip()
        branch = request.form.get('branch', 'main').strip()
        app_name = request.form.get('app_name', '').strip()
        build_config = request.form.get('build_config', 'Release').strip()
        
        # Basic validation
        if not repo_url:
            flash('Repository URL is required')
            return redirect(url_for('build.github_build'))
            
        if not app_name:
            flash('App name is required')
            return redirect(url_for('build.github_build'))
            
        # Verify GitHub token
        token_valid, token_message = verify_github_token()
        if not token_valid:
            flash(f'GitHub token error: {token_message}')
            return redirect(url_for('build.github_build'))
            
        # Generate a unique build ID
        build_id = str(uuid.uuid4())
        
        # Create a build record
        build = {
            'id': build_id,
            'app_name': app_name,
            'repo_url': repo_url,
            'branch': branch,
            'build_config': build_config,
            'status': 'queued',
            'user': session.get('username'),
            'start_time': datetime.now().isoformat(),
            'log': f"Build queued for {app_name} from {repo_url} ({branch})..."
        }
        
        # Save the build
        db.save_build(build)
        
        # Start the build process in the background
        threading.Thread(
            target=build_ios_app_from_github,
            args=(build_id, repo_url, branch, app_name, build_config)
        ).start()
        
        flash(f'Build started for {app_name}')
        return redirect(url_for('build.build_log', build_id=build_id))
        
    # GET request - show the form
    # Fetch branches if repo is provided
    repo_url = request.args.get('repo_url', '')
    branches = []
    
    if repo_url:
        branches = fetch_branches(repo_url)
        
    # Fetch user's previous builds for repo suggestions
    user_builds = []
    if 'username' in session:
        # Get builds for the current user
        all_builds = db.get_builds()
        seen_repos = set()
        
        for build in all_builds:
            if build.get('user') == session.get('username'):
                repo = build.get('repo_url')
                if repo and repo not in seen_repos:
                    seen_repos.add(repo)
                    user_builds.append({
                        'repo_url': repo,
                        'app_name': build.get('app_name'),
                        'branch': build.get('branch')
                    })
    
    # Get all builds for display
    all_builds = db.get_builds()
    # Filter builds based on user access
    user_role = db.get_user(session.get('username')).get('role')
    filtered_builds = []
    for build in all_builds:
        # Admin can see all builds
        if user_role == 'admin':
            filtered_builds.append(build)
        # Users can see their own builds
        elif build.get('user') == session.get('username'):
            filtered_builds.append(build)
    
    # Sort builds by start time descending (newest first)
    filtered_builds.sort(key=lambda x: x.get('start_time', ''), reverse=True)
    
    return render_template('github_build.html', 
                          branches=branches, 
                          repo_url=repo_url,
                          user_builds=user_builds,
                          builds=filtered_builds)

@build_bp.route('/download_build/<build_id>')
@login_required
def download_build(build_id):
    build = db.get_build(build_id)
    
    if not build:
        flash('Build not found')
        return redirect(url_for('app.index'))
        
    # Check if user has access
    if build.get('user') != session.get('username') and not db.get_user(session.get('username')).get('role') == 'admin':
        flash('You do not have access to this build')
        return redirect(url_for('app.index'))
        
    # Check if build is completed and has a file
    if build.get('status') != 'completed':
        flash('Build is not completed yet')
        return redirect(url_for('build.build_log', build_id=build_id))
        
    # Get the file
    file_data = db.get_build_file(build_id)
    
    if not file_data:
        flash('Build output file not found')
        return redirect(url_for('build.build_log', build_id=build_id))
        
    # Get filename
    filename = build.get('output_filename', 'app.ipa')
    
    # Create a response with the file data
    return send_file(
        io.BytesIO(file_data['data']),
        download_name=filename,
        as_attachment=True,
        mimetype='application/octet-stream'
    )

@build_bp.route('/build_log/<build_id>')
@login_required
def build_log(build_id):
    build = db.get_build(build_id)
    
    if not build:
        flash('Build not found')
        return redirect(url_for('app.index'))
        
    # Check if user has access
    if build.get('user') != session.get('username') and not db.get_user(session.get('username')).get('role') == 'admin':
        flash('You do not have access to this build')
        return redirect(url_for('app.index'))
        
    # For API requests, return JSON
    if request.headers.get('Accept') == 'application/json':
        return jsonify(build)
        
    # Get build app info if available
    app_info = None
    if build.get('status') == 'completed' and build.get('app_info'):
        app_info = build.get('app_info')
    
    # Get raw log content
    log_content = build.get('log', 'No log content available')
    
    # Process log content to add HTML classes for better formatting
    if log_content:
        processed_lines = []
        
        # Check if log_content is a list or a string
        if isinstance(log_content, list):
            # If it's a list, join it into a string with newlines
            log_content = '\n'.join([str(line) for line in log_content])
            
        # Now we can safely split the string
        for line in log_content.split('\n'):
            line = line.rstrip()
            # Skip empty lines
            if not line:
                processed_lines.append('')
                continue
                
            # Add classes for different log line types
            if any(error_term in line.lower() for error_term in ['error', 'exception', 'fail', 'failed']):
                processed_lines.append(f'<span class="line-error">{line}</span>')
            elif any(warning_term in line.lower() for warning_term in ['warning', 'warn']):
                processed_lines.append(f'<span class="line-warning">{line}</span>')
            elif any(success_term in line.lower() for success_term in ['success', 'completed', 'built', 'installed']):
                processed_lines.append(f'<span class="line-success">{line}</span>')
            else:
                processed_lines.append(line)
                
        # Add log content to the build object for the template with HTML formatting
        build['log_content'] = '\n'.join(processed_lines)
    else:
        build['log_content'] = 'No log content available'
        
    return render_template('build_log.html', build=build, app_info=app_info)

@build_bp.route('/download_build_log/<build_id>')
@login_required
def download_build_log(build_id):
    build = db.get_build(build_id)
    
    if not build:
        flash('Build not found')
        return redirect(url_for('app.index'))
        
    # Check if user has access
    if build.get('user') != session.get('username') and not db.get_user(session.get('username')).get('role') == 'admin':
        flash('You do not have access to this build')
        return redirect(url_for('app.index'))
        
    # Prepare log content
    log_content = build.get('log', 'No log available')
    
    # Add build info
    build_info = f"""
Build ID: {build.get('id')}
App Name: {build.get('app_name')}
Repository: {build.get('repo_url')}
Branch: {build.get('branch')}
Config: {build.get('build_config')}
Status: {build.get('status')}
Started: {build.get('start_time')}
Completed: {build.get('end_time', 'Not completed')}

LOG:
=====
{log_content}
"""
    
    # Create a response with the log content
    return send_file(
        io.BytesIO(build_info.encode('utf-8')),
        download_name=f"build-{build_id}.log",
        as_attachment=True,
        mimetype='text/plain'
    )

@build_bp.route('/stop_build/<build_id>', methods=['GET'])
@admin_required
def stop_build(build_id):
    build = db.get_build(build_id)
    
    if not build:
        flash('Build not found')
        return redirect(url_for('app.index'))
        
    # Can only stop builds that are in progress
    if build.get('status') not in ('queued', 'in_progress'):
        flash('Build is not in progress')
        return redirect(url_for('build.build_log', build_id=build_id))
        
    # Update build status
    update_build_status(
        build_id, 
        'cancelled', 
        "Build cancelled by admin",
        datetime.now().isoformat()
    )
    
    # Try to clean up GitHub fork if it exists
    if 'fork_info' in build:
        from utils.github_utils import cleanup_fork_on_failure
        cleanup_fork_on_failure(build)
        
    flash('Build cancelled')
    return redirect(url_for('build.build_log', build_id=build_id))

@build_bp.route('/delete_build/<build_id>', methods=['POST'])
@admin_required
def delete_build(build_id):
    build = db.get_build(build_id)
    
    if not build:
        flash('Build not found')
        return redirect(url_for('app.index'))
        
    # Delete the build and associated files
    db.delete_build(build_id)
    
    # Try to clean up GitHub fork if it exists
    if build.get('fork_info'):
        owner = build.get('fork_info', {}).get('owner')
        repo = build.get('fork_info', {}).get('repo')
        
        if owner and repo:
            cleanup_fork(owner, repo)
    
    flash('Build deleted')
    return redirect(url_for('app.index'))

@build_bp.route('/cleanup_repository/<build_id>', methods=['POST'])
@admin_required
def cleanup_repository(build_id):
    build = db.get_build(build_id)
    
    if not build:
        flash('Build not found')
        return redirect(url_for('app.index'))
        
    # Check if the build has fork info
    if not build.get('fork_info'):
        flash('No GitHub fork information found for this build')
        return redirect(url_for('build.build_log', build_id=build_id))
        
    # Get fork info
    fork_info = build.get('fork_info')
    owner = fork_info.get('owner')
    repo = fork_info.get('repo')
    
    if not owner or not repo:
        flash('Invalid fork information')
        return redirect(url_for('build.build_log', build_id=build_id))
        
    # Try to delete the fork
    success = cleanup_fork(owner, repo)
    
    if success:
        # Update build to indicate fork was cleaned up
        build['fork_cleaned'] = True
        db.save_build(build)
        flash('GitHub fork repository cleaned up successfully')
    else:
        flash('Failed to clean up GitHub fork repository')
        
    return redirect(url_for('build.build_log', build_id=build_id)) 