from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, abort, jsonify, make_response
from werkzeug.utils import secure_filename
import database as db
import os
import io
import uuid
from datetime import datetime
import plistlib
import logging
import base64
import re

from utils.decorators import login_required, admin_required, admin_or_developer_required
from utils.file_utils import allowed_file, format_datetime
from models import add_app_version

app_bp = Blueprint('app', __name__)

@app_bp.route('/')
def index():
    # Get apps based on user access level
    if 'username' in session:
        apps = db.get_apps_for_user(session['username'])
        
        # For admin users, filter apps by search query
        if request.args.get('q'):
            query = request.args.get('q').lower()
            filtered_apps = []
            for app in apps:
                if (query in app.get('name', '').lower() or 
                    query in app.get('bundle_id', '').lower()):
                    filtered_apps.append(app)
            apps = filtered_apps
            
        return render_template('index.html', apps=apps, query=request.args.get('q', ''))
    else:
        return render_template('login.html')

@app_bp.route('/upload', methods=['GET', 'POST'])
@admin_or_developer_required
def upload():
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
            
        file = request.files['file']
        
        # If the user does not select a file, browser submits an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        # Get release notes
        release_notes = request.form.get('release_notes')
        if not release_notes or release_notes.strip() == '':
            flash('Release notes are required')
            return redirect(request.url)
        
        # Get app description (optional)
        app_description = request.form.get('app_description', '').strip()
        
        if file and allowed_file(file.filename):
            # Save the file data
            file_data = file.read()
            
            # Store the file and create the app
            try:
                filename = secure_filename(file.filename)
                
                # This route is only for new apps now
                # Extract app info and save
                from utils.file_utils import extract_app_info
                app_info = extract_app_info(file_data, filename)
                
                # Set owner to current user
                app_info['owner'] = session.get('username')
                # Set description (if provided)
                if app_description:
                    app_info['description'] = app_description
                
                # Save the file
                db.save_file(app_info['file_id'], filename, file_data)
                
                # Save app to database
                db.save_app(app_info)
                flash(f'App {app_info["name"]} added')
                    
                return redirect(url_for('app.index'))
            
            except Exception as e:
                flash(f'Error processing file: {str(e)}')
                return redirect(request.url)
        else:
            flash('Invalid file type. Only IPA files are allowed.')
            return redirect(request.url)
            
    return render_template('upload.html')

@app_bp.route('/upload_version/<app_id>', methods=['GET', 'POST'])
@admin_or_developer_required
def upload_version(app_id):
    # Get app and verify access
    app = db.get_app(app_id)
    if not app:
        flash('App not found')
        return redirect(url_for('app.index'))
    
    # Make sure user is admin or the app owner
    current_username = session.get('username')
    current_user = db.get_user(current_username)
    if not current_user or (current_user.get('role') != 'admin' and app.get('owner') != current_username):
        flash('You do not have permission to upload a new version for this app')
        return redirect(url_for('app.app_detail', app_id=app_id))
    
    # Format dates for display and add size information for each version
    if app.get('versions'):
        for version in app.get('versions', []):
            if version.get('upload_date'):
                version['formatted_upload_date'] = format_datetime(version.get('upload_date'))
            
            # Add size information for each version
            file_id = version.get('file_id')
            if file_id:
                file_data = db.get_file(file_id)
                if file_data:
                    version['size'] = file_data.get('size', 0)
                else:
                    version['size'] = 0
    
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
            
        file = request.files['file']
        
        # If the user does not select a file, browser submits an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        
        # Get release notes
        release_notes = request.form.get('release_notes')
        if not release_notes or release_notes.strip() == '':
            flash('Release notes are required')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Save the file data
            file_data = file.read()
            version = request.form.get('version')
            
            # Store the file and update the app
            try:
                filename = secure_filename(file.filename)
                
                # Update existing app with new version
                updated_app = add_app_version(app_id, file_data, filename, version, release_notes)
                flash(f'App {updated_app["name"]} updated to version {updated_app["version"]} ({updated_app["build_number"]})')
                return redirect(url_for('app.app_detail', app_id=app_id))
            
            except Exception as e:
                flash(f'Error processing file: {str(e)}')
                return redirect(request.url)
        else:
            flash('Invalid file type. Only IPA files are allowed.')
            return redirect(request.url)
    
    return render_template('upload_version.html', app=app)

@app_bp.route('/app/<app_id>')
def app_detail(app_id):
    # Check if user has access to this app
    if 'username' not in session:
        flash('Please log in to view app details')
        return redirect(url_for('auth.login'))
        
    app = db.get_app(app_id)
    if not app:
        flash('App not found')
        return redirect(url_for('app.index'))
        
    # Check if the current user has access to this app
    if not db.get_user_app_access(session['username'], app_id):
        flash('You do not have access to this app')
        return redirect(url_for('app.index'))
        
    # Get shared users for this app
    shared_users = db.get_shared_users(app_id)
    
    # Get comments for all versions
    all_comments = db.get_comments_for_version(app_id)
    
    # Organize comments by version
    comments_by_version = {}
    for comment in all_comments:
        version = comment.get('version')
        if version not in comments_by_version:
            comments_by_version[version] = []
        comments_by_version[version].append(comment)
    
    # Format dates in the app object to DD-MMM-YYYY
    if app.get('upload_date'):
        app['formatted_upload_date'] = format_datetime(app.get('upload_date'))
    
    if app.get('creation_date'):
        app['formatted_creation_date'] = format_datetime(app.get('creation_date'))
    
    # Format dates in versions
    if app.get('versions'):
        for version in app.get('versions', []):
            if version.get('upload_date'):
                version['formatted_upload_date'] = format_datetime(version.get('upload_date'))
    
    return render_template('app_detail.html', 
                           app=app, 
                           shared_users=shared_users, 
                           comments_by_version=comments_by_version,
                           format_datetime=format_datetime)

@app_bp.route('/edit/<app_id>', methods=['GET', 'POST'])
@admin_required
def edit_app(app_id):
    app = db.get_app(app_id)
    if not app:
        flash('App not found')
        return redirect(url_for('app.index'))
        
    if request.method == 'POST':
        # Update app data
        app['name'] = request.form['name']
        app['bundle_id'] = request.form['bundle_id']
        # Version and build number should not be updated from form - they're set from latest version in history
        app['description'] = request.form['app_description']
        
        # Save to database
        db.save_app(app)
        flash(f'App {app["name"]} updated')
        return redirect(url_for('app.app_detail', app_id=app_id))
        
    return render_template('edit_app.html', app=app)

@app_bp.route('/download/<app_id>/<filename>')
def download_app(app_id, filename):
    # Check if user has access to this app
    if 'username' not in session:
        # For direct downloads, redirect to login
        return redirect(url_for('auth.login', next=request.url))
        
    app = db.get_app(app_id)
    if not app or not db.get_user_app_access(session['username'], app_id):
        flash('You do not have access to this app')
        return redirect(url_for('app.index'))
        
    # Get the file
    file_id = app.get('file_id')
    file_data = db.get_file(file_id)
    
    if not file_data:
        flash('File not found')
        return redirect(url_for('app.app_detail', app_id=app_id))
        
    # Create a response with the file data
    return send_file(
        io.BytesIO(file_data['data']),
        download_name=filename,
        as_attachment=True,
        mimetype='application/octet-stream'
    )

@app_bp.route('/install/<app_id>')
def install(app_id):
    # Check if user has access to this app
    if 'username' not in session:
        # For direct installs, redirect to login
        return redirect(url_for('auth.login', next=request.url))
        
    app = db.get_app(app_id)
    if not app or not db.get_user_app_access(session['username'], app_id):
        flash('You do not have access to this app')
        return redirect(url_for('app.index'))
        
    # Generate manifest URL
    host = request.host_url.rstrip('/')
    manifest_url = f"{host}{url_for('app.app_manifest', app_id=app_id)}"
    
    # Generate the iOS installation URL using the itms-services protocol
    install_url = f"itms-services://?action=download-manifest&url={manifest_url}"
    
    return render_template('install.html', app=app, manifest_url=manifest_url, install_url=install_url)

@app_bp.route('/direct_install/<app_id>')
def direct_install(app_id):
    # Check if user has access to this app
    if 'username' not in session:
        # For direct installs, redirect to login
        return redirect(url_for('auth.login', next=request.url))
        
    app = db.get_app(app_id)
    if not app or not db.get_user_app_access(session['username'], app_id):
        flash('You do not have access to this app')
        return redirect(url_for('app.index'))
    
    # Generate download URL for the IPA file
    host = request.host_url.rstrip('/')
    download_url = f"{host}{url_for('app.download_app', app_id=app_id, filename=app.get('filename', 'app.ipa'))}"
    
    return render_template('direct_install.html', app=app, download_url=download_url)

@app_bp.route('/manifest/<app_id>')
def app_manifest(app_id):
    app = db.get_app(app_id)
    if not app:
        abort(404)
        
    host = request.host_url.rstrip('/')
    download_url = f"{host}{url_for('app.download_app', app_id=app_id, filename=app.get('filename', 'app.ipa'))}"
    
    # Create a Property List (plist) for iOS app installation
    manifest = {
        'items': [{
            'assets': [{
                'kind': 'software-package',
                'url': download_url
            }],
            'metadata': {
                'bundle-identifier': app.get('bundle_id', 'com.example.app'),
                'bundle-version': app.get('version', '1.0'),
                'kind': 'software',
                'title': app.get('name', 'App')
            }
        }]
    }
    
    # Set content type for plist
    response = make_response(plistlib.dumps(manifest))
    response.headers['Content-Type'] = 'application/xml'
    return response

@app_bp.route('/delete/<app_id>', methods=['POST'])
@admin_required
def delete_app(app_id):
    app = db.get_app(app_id)
    if not app:
        flash('App not found')
        return redirect(url_for('app.index'))
        
    # Delete app and associated files
    db.delete_app(app_id)
    flash(f'App {app.get("name", app_id)} deleted')
    return redirect(url_for('app.index'))

@app_bp.route('/manage_sharing/<app_id>', methods=['GET', 'POST'])
@admin_or_developer_required
def manage_sharing(app_id):
    app = db.get_app(app_id)
    if not app:
        flash('App not found')
        return redirect(url_for('app.index'))
        
    # Get all users for sharing
    users = db.get_users()
    
    # Get currently shared users
    shared_users = db.get_shared_users(app_id)
    
    # Filter out admin users and the app owner (they already have access)
    filterable_users = []
    current_user = session.get('username')
    current_user_role = db.get_user(current_user).get('role')
    
    for user in users:
        username = user.get('username')
        
        # Skip admins
        if user.get('role') == 'admin':
            continue
        
        # If current user is a developer (not admin),
        # they can only manage sharing for apps they own
        if (current_user_role == 'developer' and 
            user.get('role') == 'developer' and 
            current_user != user.get('username') and
            app.get('owner') != current_user):
            continue
        
        # Add user to list with sharing status
        filterable_users.append({
            'username': username,
            'role': user.get('role'),
            'is_shared': username in shared_users
        })
    
    if request.method == 'POST':
        # Check for individual share action
        if request.form.get('action') == 'share':
            # Handle individual share
            username = request.form.get('username')
            if username:
                success, message = db.share_app(app_id, username)
                if success:
                    flash(message)
                else:
                    flash(f'Error sharing app: {message}')
            else:
                flash('Username is required')
        else:
            # Process bulk sharing update
            for username in request.form.getlist('shared_users'):
                if username not in shared_users:
                    db.share_app(app_id, username)
                    
            # Remove sharing for users not in the list
            for username in shared_users:
                if username not in request.form.getlist('shared_users'):
                    db.unshare_app(app_id, username, current_user)
                    
            flash('Sharing settings updated')
            
        return redirect(url_for('app.app_detail', app_id=app_id))
    
    return render_template('manage_sharing.html', app=app, users=filterable_users, shared_users=shared_users)

@app_bp.route('/share_app/<app_id>', methods=['POST'])
@admin_or_developer_required
def share_app(app_id):
    username = request.form.get('username')
    if not username:
        flash('Username is required')
        return redirect(url_for('app.app_detail', app_id=app_id))
        
    success, message = db.share_app(app_id, username)
    if success:
        flash(message)
        
        # Get app details and current user
        app = db.get_app(app_id)
        current_username = session.get('username')
        
        # Create notification for the user who was granted access
        db.create_notification(
            username=username,
            type='access',
            content=f"{current_username} gave you access to {app.get('name')}",
            reference_id=app_id,
            reference_type='app',
            from_user=current_username
        )
        
        # Send app refresh notification to all users with access
        try:
            from routes.notification_routes import send_app_refresh_notification
            send_app_refresh_notification(app_id, 'share')
        except Exception as e:
            print(f"Error sending refresh notification: {e}")
    else:
        flash(f'Error sharing app: {message}')
        
    return redirect(url_for('app.app_detail', app_id=app_id))

@app_bp.route('/unshare_app/<app_id>/<username>', methods=['POST'])
@admin_or_developer_required
def unshare_app(app_id, username):
    current_username = session.get('username')
    success, message = db.unshare_app(app_id, username, current_username)
    
    if success:
        flash(message)
        
        # Get app details
        app = db.get_app(app_id)
        
        # Create notification for the user who lost access
        db.create_notification(
            username=username,
            type='access',
            content=f"{current_username} removed your access to {app.get('name')}",
            reference_id=app_id,
            reference_type='app',
            from_user=current_username
        )
        
        # Send app refresh notification to all users with access
        try:
            from routes.notification_routes import send_app_refresh_notification
            send_app_refresh_notification(app_id, 'unshare')
        except Exception as e:
            print(f"Error sending refresh notification: {e}")
    else:
        flash(f'Error removing share: {message}')
        
    return redirect(url_for('app.app_detail', app_id=app_id))

def extract_mentions(text):
    """
    Extract mentions from text
    
    Args:
        text (str): The text to search for mentions
        
    Returns:
        list: List of usernames mentioned
    """
    # Match @username pattern
    mentions = re.findall(r'@(\w+)', text)
    return mentions

@app_bp.route('/add_comment/<app_id>', methods=['POST'])
@login_required
def add_comment(app_id):
    version = request.form.get('version')
    text = request.form.get('comment_text')
    parent_id = request.form.get('parent_id')
    
    if not version or not text:
        flash('Version and comment text are required')
        return redirect(url_for('app.app_detail', app_id=app_id))
    
    # Make sure the app exists and user has access
    app = db.get_app(app_id)
    if not app or not db.get_user_app_access(session.get('username'), app_id):
        flash('You do not have access to this app')
        return redirect(url_for('app.index'))
    
    # Get the current user
    current_username = session.get('username')
    current_user = db.get_user(current_username)
    
    # Add the comment
    result = db.add_comment(app_id, version, current_username, text, parent_id)
    
    if result.get('success'):
        comment = result.get('comment')
        
        # Handle notifications for replies
        if parent_id:
            # This is a reply, notify the parent comment author
            parent_comment = db.comments_collection.find_one({'id': parent_id}, {'_id': 0})
            if parent_comment and parent_comment.get('username') != current_username:
                parent_author = parent_comment.get('username')
                
                # Create notification for the parent comment author
                db.create_notification(
                    username=parent_author,
                    type='reply',
                    content=f"{current_username} replied to your comment on {app.get('name')} v{version}",
                    reference_id=comment.get('id'),
                    reference_type='comment',
                    from_user=current_username
                )
        
        # Handle notifications for mentions
        mentions = extract_mentions(text)
        for mentioned_username in mentions:
            # Make sure the mentioned user exists and is not the commenter
            mentioned_user = db.get_user(mentioned_username)
            if mentioned_user and mentioned_username != current_username:
                # Create notification for the mentioned user
                db.create_notification(
                    username=mentioned_username,
                    type='mention',
                    content=f"{current_username} mentioned you in a comment on {app.get('name')} v{version}",
                    reference_id=comment.get('id'),
                    reference_type='comment',
                    from_user=current_username
                )
        
        # Send app refresh notification to all users with access
        try:
            from routes.notification_routes import send_app_refresh_notification
            send_app_refresh_notification(app_id, 'comment_add')
        except Exception as e:
            print(f"Error sending refresh notification: {e}")
        
        flash('Comment added successfully')
    else:
        flash(f'Error adding comment: {result.get("message")}')
    
    return redirect(url_for('app.app_detail', app_id=app_id))

@app_bp.route('/delete_comment/<app_id>/<comment_id>', methods=['POST'])
@login_required
def delete_comment(app_id, comment_id):
    username = session.get('username')
    user = db.get_user(username)
    is_admin = user and user.get('role') == 'admin'
    
    # Delete the comment
    success = db.delete_comment(comment_id, username, is_admin)
    
    if success:
        flash('Comment deleted successfully')
        
        # Send app refresh notification to all users with access
        try:
            from routes.notification_routes import send_app_refresh_notification
            send_app_refresh_notification(app_id, 'comment_delete')
        except Exception as e:
            print(f"Error sending refresh notification: {e}")
    else:
        flash('Error deleting comment. You can only delete your own comments.')
    
    return redirect(url_for('app.app_detail', app_id=app_id)) 