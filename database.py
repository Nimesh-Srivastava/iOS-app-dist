import os
from pymongo import MongoClient
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import uuid
from datetime import datetime
import certifi  # 👈 NEW

# Load environment variables
load_dotenv()

# MongoDB connection
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = os.environ.get('DB_NAME', 'app_distribution')

# Connect to MongoDB
# Use certifi CA bundle for Atlas / TLS connections
if MONGO_URI.startswith("mongodb+srv://") or "mongodb.net" in MONGO_URI:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
else:
    client = MongoClient(MONGO_URI)

db = client[DB_NAME]

# Collections
users_collection = db['users']
apps_collection = db['apps']
builds_collection = db['builds']
app_shares_collection = db['app_shares']  # New collection for tracking app sharing
files_collection = db['files']  # New collection for storing IPA files
comments_collection = db['comments']  # New collection for app version comments
notifications_collection = db['notifications']  # New collection for user notifications
organizations_collection = db['organizations']  # Collection for organizations


def initialize_db():
    """Initialize database with default data if empty"""
    # Create indexes for better performance
    users_collection.create_index('username', unique=True)
    users_collection.create_index('org_id')  # Index for organization filtering
    apps_collection.create_index('id', unique=True)
    apps_collection.create_index('org_id')  # Index for organization filtering
    builds_collection.create_index('id', unique=True)
    builds_collection.create_index('org_id')  # Index for organization filtering
    app_shares_collection.create_index([('app_id', 1), ('username', 1)], unique=True)  # Composite index
    files_collection.create_index('file_id', unique=True)  # Index for file storage
    comments_collection.create_index([('app_id', 1), ('version', 1)])  # Index for comments by app version
    comments_collection.create_index('org_id')  # Index for organization filtering
    notifications_collection.create_index('username')  # Index for notifications by username
    notifications_collection.create_index([('username', 1), ('read', 1)])  # Index for unread notifications
    notifications_collection.create_index('org_id')  # Index for organization filtering
    organizations_collection.create_index('id', unique=True)  # Index for organization ID
    try:
        organizations_collection.create_index('name', unique=True)  # Index for organization name
    except Exception:
        # Index might already exist, that's okay
        pass

    
    # Create default admin user if no users exist
    if users_collection.count_documents({}) == 0:
        default_admin = {
            'username': 'admin',
            'password': generate_password_hash('admin123'),
            'role': 'primary_admin',  # Changed from 'admin' to 'primary_admin'
            'org_id': None,  # Primary admin has no org
            'org_role': None
        }
        users_collection.insert_one(default_admin)
        print("Created default admin user (username: admin, password: admin123)")
    else:
        # Migrate existing admin user to primary_admin if needed
        admin_user = users_collection.find_one({'username': 'admin'})
        if admin_user:
            # Update existing admin user to primary_admin role
            update_needed = False
            update_data = {}
            
            if admin_user.get('role') != 'primary_admin':
                update_data['role'] = 'primary_admin'
                update_needed = True
            
            if 'org_id' not in admin_user or admin_user.get('org_id') is not None:
                update_data['org_id'] = None
                update_needed = True
            
            if 'org_role' not in admin_user or admin_user.get('org_role') is not None:
                update_data['org_role'] = None
                update_needed = True
            
            if update_needed:
                users_collection.update_one(
                    {'username': 'admin'},
                    {'$set': update_data}
                )
                print("Updated existing admin user to primary_admin role")

# User operations
def get_users(org_id=None):
    """Get all users, optionally filtered by organization"""
    query = {}
    if org_id is not None:
        query['org_id'] = org_id
    return list(users_collection.find(query, {'_id': 0}))

def get_user(username):
    """Get a user by username"""
    return users_collection.find_one({'username': username}, {'_id': 0})

def save_user(user_data):
    """Create or update a user"""
    username = user_data['username']
    users_collection.update_one(
        {'username': username},
        {'$set': user_data},
        upsert=True
    )

def update_user_password(username, new_password_hash):
    """Update a user's password"""
    result = users_collection.update_one(
        {'username': username},
        {'$set': {'password': new_password_hash}}
    )
    return result.modified_count > 0

def update_user_github_token(username, token):
    """Update a user's GitHub token"""
    result = users_collection.update_one(
        {'username': username},
        {'$set': {'github_token': token}}
    )
    return result.modified_count > 0 or result.matched_count > 0

def get_user_github_token(username):
    """Get a user's GitHub token"""
    user = get_user(username)
    if user:
        return user.get('github_token')
    return None

def update_user_profile_picture(username, picture_data, content_type='image/jpeg'):
    """Update a user's profile picture
    
    Args:
        username (str): Username to update
        picture_data (bytes): Binary image data
        content_type (str): Image MIME type
        
    Returns:
        bool: True if successful
    """
    # Generate a unique ID for the profile picture
    file_id = str(uuid.uuid4())
    
    # Store the image in the files collection
    save_file(file_id, f"{username}_profile", picture_data, content_type)
    
    # Update the user document with the file_id
    result = users_collection.update_one(
        {'username': username},
        {'$set': {'profile_picture_id': file_id}}
    )
    
    return result.modified_count > 0

def get_user_profile_picture(username):
    """Get a user's profile picture
    
    Args:
        username (str): Username to get profile picture for
        
    Returns:
        dict or None: File document if found
    """
    user = get_user(username)
    if not user or 'profile_picture_id' not in user:
        return None
    
    return get_file(user['profile_picture_id'])

def delete_user(username):
    """Delete a user"""
    # Delete profile picture if exists
    user = get_user(username)
    if user and 'profile_picture_id' in user:
        delete_file(user['profile_picture_id'])
    
    # Delete user document
    users_collection.delete_one({'username': username})
    
    # Remove any app shares for this user
    app_shares_collection.delete_many({'username': username})
    
    # Delete all notifications for this user
    delete_user_notifications(username)

# Organization operations
def get_organizations():
    """Get all organizations"""
    return list(organizations_collection.find({}, {'_id': 0}))

def get_organization(org_id):
    """Get an organization by ID"""
    return organizations_collection.find_one({'id': org_id}, {'_id': 0})

def save_organization(org_data):
    """Create or update an organization"""
    org_id = org_data['id']
    organizations_collection.update_one(
        {'id': org_id},
        {'$set': org_data},
        upsert=True
    )

def delete_organization(org_id):
    """Delete an organization and all associated data"""
    # Delete all users in this org (or set their org_id to None)
    users_collection.update_many(
        {'org_id': org_id},
        {'$set': {'org_id': None, 'org_role': None}}
    )
    
    # Delete all apps in this org
    apps = apps_collection.find({'org_id': org_id}, {'_id': 0, 'id': 1})
    for app in apps:
        delete_app(app['id'])
    
    # Delete all builds in this org
    builds_collection.delete_many({'org_id': org_id})
    
    # Delete all comments in this org
    comments_collection.delete_many({'org_id': org_id})
    
    # Delete all notifications in this org
    notifications_collection.delete_many({'org_id': org_id})
    
    # Delete the organization
    organizations_collection.delete_one({'id': org_id})

def get_org_users(org_id):
    """Get all users in an organization"""
    return list(users_collection.find({'org_id': org_id}, {'_id': 0}))

def is_primary_admin(username):
    """Check if a user is the primary admin"""
    user = get_user(username)
    return user and user.get('role') == 'primary_admin'

def get_user_org(username):
    """Get the organization for a user"""
    user = get_user(username)
    if not user or not user.get('org_id'):
        return None
    return get_organization(user.get('org_id'))

# App operations
def get_apps(org_id=None):
    """Get all apps, optionally filtered by organization"""
    query = {}
    if org_id is not None:
        query['org_id'] = org_id
    return list(apps_collection.find(query, {'_id': 0}))

def get_apps_for_user(username):
    """
    Get apps that a specific user has access to
    - Primary admin sees all apps
    - Org admins see all apps in their org
    - Org developers see their own apps plus shared apps in their org
    - Org testers see only shared apps in their org
    """
    user = get_user(username)
    if not user:
        return []
    
    # Primary admin sees all apps
    if user.get('role') == 'primary_admin':
        return get_apps()
    
    # Get user's org_id
    org_id = user.get('org_id')
    if not org_id:
        return []  # User without org has no apps
    
    # Org admins see all apps in their org
    if user.get('org_role') == 'admin':
        return get_apps(org_id=org_id)
    
    # Get apps shared with the user (within the same org)
    shared_app_ids = [
        share['app_id'] 
        for share in app_shares_collection.find({'username': username}, {'_id': 0, 'app_id': 1})
    ]
    
    # For org developers, include apps they own plus shared apps (all within org)
    if user.get('org_role') == 'developer':
        return list(apps_collection.find({
            'org_id': org_id,
            '$or': [
                {'id': {'$in': shared_app_ids}},
                {'owner': username}
            ]
        }, {'_id': 0}))
    
    # For org testers, only show shared apps (within org)
    return list(apps_collection.find({
        'org_id': org_id,
        'id': {'$in': shared_app_ids}
    }, {'_id': 0}))

def get_app(app_id):
    """Get an app by ID"""
    return apps_collection.find_one({'id': app_id}, {'_id': 0})

def save_app(app_data):
    """Create or update an app"""
    app_id = app_data['id']
    apps_collection.update_one(
        {'id': app_id},
        {'$set': app_data},
        upsert=True
    )

def delete_app(app_id):
    """Delete an app and all associated files"""
    # Delete files first
    delete_app_files(app_id)
    
    # Delete all comments for this app
    delete_app_comments(app_id)
    
    # Then delete the app
    apps_collection.delete_one({'id': app_id})
    
    # Remove any shares for this app
    app_shares_collection.delete_many({'app_id': app_id})

def save_apps(apps):
    """Save multiple apps (used for batch operations)"""
    for app in apps:
        save_app(app)

# App sharing operations
def share_app(app_id, username):
    """Share an app with a specific user (must be in same org)"""
    # Check if app exists
    app = get_app(app_id)
    if not app:
        return False, "App not found"
        
    # Check if user exists
    user = get_user(username)
    if not user:
        return False, "User not found"
    
    # Check if user is primary admin (they already have access to all apps)
    if user.get('role') == 'primary_admin':
        return False, "No need to share with primary admin (they have full access)"
    
    # Check if app and user are in the same org
    app_org_id = app.get('org_id')
    user_org_id = user.get('org_id')
    
    if app_org_id != user_org_id:
        return False, "Cannot share app with users from different organizations"
    
    # Org admins already have access to all apps in their org
    if user.get('org_role') == 'admin':
        return False, "No need to share with org admin users (they have full access to org apps)"
    
    # Create or update share record
    app_shares_collection.update_one(
        {'app_id': app_id, 'username': username},
        {'$set': {
            'app_id': app_id,
            'username': username,
            'app_name': app.get('name', 'Unknown App')
        }},
        upsert=True
    )
    
    return True, f"App {app.get('name', app_id)} shared with {username}"

def unshare_app(app_id, username, requesting_user=None):
    """Remove app sharing for a specific user"""
    # Get app details
    app = get_app(app_id)
    if not app:
        return False, "App not found"
        
    # Don't allow developers to unshare themselves
    if requesting_user and username == requesting_user and get_user(requesting_user).get('role') == 'developer':
        return False, "Developers cannot remove their own app access"

    result = app_shares_collection.delete_one({'app_id': app_id, 'username': username})
    if result.deleted_count > 0:
        return True, "Access removed successfully"
    else:
        return False, "Share not found"

def get_app_shares(app_id=None):
    """
    Get app sharing information
    If app_id is provided, return shares for that app only
    Otherwise, return all shares
    """
    query = {'app_id': app_id} if app_id else {}
    return list(app_shares_collection.find(query, {'_id': 0}))

def get_shared_users(app_id):
    """Get list of usernames that an app is shared with"""
    shares = app_shares_collection.find({'app_id': app_id}, {'_id': 0, 'username': 1})
    return [share['username'] for share in shares]

def get_user_app_access(username, app_id):
    """Check if a user has access to a specific app"""
    user = get_user(username)
    if not user:
        return False
    
    # Primary admin has access to all apps
    if user.get('role') == 'primary_admin':
        return True
    
    # Get the app
    app = get_app(app_id)
    if not app:
        return False
    
    # Check if app and user are in the same org
    app_org_id = app.get('org_id')
    user_org_id = user.get('org_id')
    
    if app_org_id != user_org_id:
        return False  # Different orgs, no access
    
    # Org admins have access to all apps in their org
    if user.get('org_role') == 'admin':
        return True
    
    # Org developers have access to apps they own or that are shared with them
    if user.get('org_role') == 'developer':
        if app.get('owner') == username:
            return True
        share = app_shares_collection.find_one({'app_id': app_id, 'username': username})
        return share is not None
    
    # Org testers only have access to shared apps
    share = app_shares_collection.find_one({'app_id': app_id, 'username': username})
    return share is not None

# Build operations
def get_builds(org_id=None):
    """Get all builds, optionally filtered by organization"""
    query = {}
    if org_id is not None:
        query['org_id'] = org_id
    return list(builds_collection.find(query, {'_id': 0}))

def get_build(build_id):
    """Get a build by ID"""
    return builds_collection.find_one({'id': build_id}, {'_id': 0})

def save_build(build_data):
    """Create or update a build"""
    build_id = build_data['id']
    builds_collection.update_one(
        {'id': build_id},
        {'$set': build_data},
        upsert=True
    )

def update_build_status(build_id, status, log=None, end_time=None):
    """Update build status and optional fields"""
    update_data = {'status': status}
    
    if log is not None:
        # First check if the log field exists and what type it is
        build = get_build(build_id)
        if build and 'log' in build:
            if isinstance(build['log'], list):
                # If it's already an array, append to it
                builds_collection.update_one(
                    {'id': build_id},
                    {'$push': {'log': log}}
                )
            else:
                # If it's a string, convert to array with both old and new content
                builds_collection.update_one(
                    {'id': build_id},
                    {'$set': {'log': [build['log'], log]}}
                )
        else:
            # If log field doesn't exist, create it as an array
            builds_collection.update_one(
                {'id': build_id},
                {'$set': {'log': [log]}}
            )
    
    if end_time is not None:
        update_data['end_time'] = end_time
    
    builds_collection.update_one(
        {'id': build_id},
        {'$set': update_data}
    )
    return True

def delete_build(build_id):
    """
    Delete a build by ID
    
    Args:
        build_id (str): Build identifier
        
    Returns:
        bool: True if the build was deleted, False otherwise
    """
    # Get the build to check if it exists
    build = get_build(build_id)
    if not build:
        return False
    
    # Delete any associated build files first
    delete_build_files(build_id)
    
    # Delete the build
    result = builds_collection.delete_one({'id': build_id})
    return result.deleted_count > 0

# File storage operations
def save_file(file_id, filename, file_data, content_type='application/octet-stream'):
    """
    Store a file in MongoDB
    
    Args:
        file_id (str): Unique identifier for the file
        filename (str): Original filename
        file_data (bytes): Binary content of the file
        content_type (str): MIME type of the file
        
    Returns:
        str: The file_id
    """
    file_doc = {
        'file_id': file_id,
        'filename': filename,
        'content_type': content_type,
        'size': len(file_data),
        'data': file_data,
        'upload_date': os.environ.get('TZ', 'UTC')
    }
    
    files_collection.update_one(
        {'file_id': file_id},
        {'$set': file_doc},
        upsert=True
    )
    
    return file_id

def get_file(file_id):
    """
    Retrieve a file from MongoDB
    
    Args:
        file_id (str): Unique identifier for the file
        
    Returns:
        dict or None: The file document if found, None otherwise
    """
    return files_collection.find_one({'file_id': file_id}, {'_id': 0})

def delete_file(file_id):
    """
    Delete a file from MongoDB
    
    Args:
        file_id (str): Unique identifier for the file
        
    Returns:
        bool: True if the file was deleted, False otherwise
    """
    result = files_collection.delete_one({'file_id': file_id})
    return result.deleted_count > 0

def delete_app_files(app_id):
    """
    Delete all files associated with an app
    
    Args:
        app_id (str): App identifier
        
    Returns:
        int: Number of files deleted
    """
    # First, find all file IDs associated with this app
    app = get_app(app_id)
    files_to_delete = []
    
    if app:
        # Add main app file if exists
        if 'file_id' in app:
            files_to_delete.append(app['file_id'])
        
        # Add versions files if exist
        if 'versions' in app:
            for version in app['versions']:
                if 'file_id' in version:
                    files_to_delete.append(version['file_id'])
    
    # Delete all files found
    deleted_count = 0
    for file_id in files_to_delete:
        if delete_file(file_id):
            deleted_count += 1
    
    return deleted_count

# Build file storage operations
def save_build_file(build_id, file_path, file_data, content_type='application/octet-stream'):
    """
    Store a build file in MongoDB
    
    Args:
        build_id (str): The build ID this file belongs to
        file_path (str): Relative path within the build (simulates file system hierarchy)
        file_data (bytes): Binary content of the file
        content_type (str): MIME type of the file
        
    Returns:
        str: Generated file_id
    """
    file_id = str(uuid.uuid4())
    
    # Create a document that includes build reference and path
    file_doc = {
        'file_id': file_id,
        'build_id': build_id,
        'file_path': file_path,
        'content_type': content_type,
        'size': len(file_data),
        'data': file_data,
        'upload_date': datetime.now().isoformat()
    }
    
    files_collection.insert_one(file_doc)
    
    # Update the build to reference this file
    builds_collection.update_one(
        {'id': build_id},
        {'$push': {'build_files': file_id}}
    )
    
    return file_id

def get_build_file(build_id, file_path=None, file_id=None):
    """
    Retrieve a build file from MongoDB
    
    Args:
        build_id (str): The build ID to get files for
        file_path (str, optional): Specific file path to retrieve
        file_id (str, optional): Specific file ID to retrieve
        
    Returns:
        dict or list: The file document if file_path or file_id is specified,
                     otherwise a list of all file documents for the build
    """
    if file_id:
        # Get specific file by ID
        return files_collection.find_one({
            'file_id': file_id, 
            'build_id': build_id
        }, {'_id': 0})
    
    if file_path:
        # Get specific file by path
        return files_collection.find_one({
            'build_id': build_id,
            'file_path': file_path
        }, {'_id': 0})
    
    # Get all files for this build
    return list(files_collection.find(
        {'build_id': build_id}, 
        {'_id': 0}
    ))

def delete_build_files(build_id):
    """
    Delete all files associated with a build
    
    Args:
        build_id (str): Build identifier
        
    Returns:
        int: Number of files deleted
    """
    # Delete all files for this build
    result = files_collection.delete_many({'build_id': build_id})
    
    # Update the build to remove file references
    builds_collection.update_one(
        {'id': build_id},
        {'$unset': {'build_files': ""}}
    )
    
    return result.deleted_count > 0

# Comment operations
def add_comment(app_id, version, username, text, parent_id=None):
    """
    Add a comment to an app version
    
    Args:
        app_id (str): The app ID
        version (str): The app version
        username (str): The commenting user
        text (str): The comment text
        parent_id (str, optional): Parent comment ID if this is a reply
        
    Returns:
        dict: The comment data with success status
    """
    user = get_user(username)
    if not user:
        return {'success': False, 'message': 'User not found'}
    
    # Get app to get org_id
    app = get_app(app_id)
    if not app:
        return {'success': False, 'message': 'App not found'}
        
    comment_data = {
        'id': str(uuid.uuid4()),
        'app_id': app_id,
        'version': version,
        'username': username,
        'user_role': user.get('role', 'user'),
        'text': text,
        'timestamp': datetime.now().isoformat(),
        'parent_id': parent_id,
        'org_id': app.get('org_id')  # Store org_id for filtering
    }
    
    comments_collection.insert_one(comment_data)
    return {'success': True, 'comment': comment_data}

def get_comments_for_version(app_id, version=None):
    """
    Get comments for an app version
    
    Args:
        app_id (str): The app ID
        version (str, optional): The app version. If None, get comments for all versions.
        
    Returns:
        list: List of comments
    """
    query = {'app_id': app_id}
    if version:
        query['version'] = version
        
    comments = list(comments_collection.find(
        query, 
        {'_id': 0}
    ).sort('timestamp', -1))  # Newest first
    
    # Organize comments into threads (parent comments with replies)
    comment_threads = []
    replies_map = {}
    
    # First, separate parent comments from replies
    for comment in comments:
        if comment.get('parent_id'):
            parent_id = comment.get('parent_id')
            if parent_id not in replies_map:
                replies_map[parent_id] = []
            replies_map[parent_id].append(comment)
        else:
            # This is a parent comment
            comment['replies'] = []
            comment_threads.append(comment)
    
    # Then, add replies to their parent comments
    for comment in comment_threads:
        if comment['id'] in replies_map:
            # Sort replies by timestamp (oldest first for conversation flow)
            comment['replies'] = sorted(replies_map[comment['id']], key=lambda x: x['timestamp'])
    
    # Sort parent comments by timestamp (newest first)
    return sorted(comment_threads, key=lambda x: x['timestamp'], reverse=True)

def delete_comment(comment_id, username=None, is_admin=False):
    """
    Delete a comment
    
    Args:
        comment_id (str): The comment ID
        username (str, optional): The username of the user trying to delete
        is_admin (bool): Whether the user is an admin
        
    Returns:
        bool: True if the comment was deleted, False otherwise
    """
    # Find the comment first
    comment = comments_collection.find_one({'id': comment_id}, {'_id': 0})
    if not comment:
        return False
        
    # Check permission - only comment author or admin can delete
    if not is_admin and username != comment.get('username'):
        return False
        
    # Delete the comment and all its replies
    if comment.get('parent_id') is None:
        # This is a parent comment, delete all replies too
        comments_collection.delete_many({'parent_id': comment_id})
    
    # Delete the comment itself
    result = comments_collection.delete_one({'id': comment_id})
    return result.deleted_count > 0

def delete_app_comments(app_id):
    """
    Delete all comments for an app (used when deleting an app)
    
    Args:
        app_id (str): The app ID
        
    Returns:
        int: Number of comments deleted
    """
    result = comments_collection.delete_many({'app_id': app_id})
    return result.deleted_count

# Notification operations
def create_notification(username, type, content, reference_id=None, reference_type=None, from_user=None):
    """
    Create a notification for a user
    
    Args:
        username (str): The username to notify
        type (str): Notification type (mention, reply, access)
        content (str): Notification content
        reference_id (str, optional): ID of the referenced object (comment, app, etc.)
        reference_type (str, optional): Type of the referenced object
        from_user (str, optional): Username of the user who triggered the notification
        
    Returns:
        dict: The notification data
    """
    # Get user to get org_id
    user = get_user(username)
    org_id = user.get('org_id') if user else None
    
    notification = {
        'id': str(uuid.uuid4()),
        'username': username,
        'type': type,  # mention, reply, access
        'content': content,
        'timestamp': datetime.now().isoformat(),
        'read': False,
        'reference_id': reference_id,
        'reference_type': reference_type,
        'from_user': from_user,
        'org_id': org_id  # Store org_id for filtering
    }
    
    # Insert the notification into the database
    notifications_collection.insert_one(notification)
    
    # Send real-time notification if possible
    try:
        # Import here to avoid circular imports
        from routes.notification_routes import push_real_time_notification
        push_real_time_notification(username, notification)
    except Exception as e:
        print(f"Error sending real-time notification: {e}")
    
    return notification

def get_user_notifications(username, limit=20, include_read=False):
    """
    Get notifications for a user
    
    Args:
        username (str): The username to get notifications for
        limit (int): Maximum number of notifications to return
        include_read (bool): Whether to include read notifications
        
    Returns:
        list: List of notifications
    """
    query = {'username': username}
    if not include_read:
        query['read'] = False
        
    notifications = list(notifications_collection.find(
        query, 
        {'_id': 0}
    ).sort('timestamp', -1).limit(limit))
    
    return notifications

def mark_notification_read(notification_id, username=None):
    """
    Mark a notification as read
    
    Args:
        notification_id (str): The notification ID
        username (str, optional): Username for permission check
        
    Returns:
        bool: True if successful, False otherwise
    """
    query = {'id': notification_id}
    if username:
        query['username'] = username
        
    result = notifications_collection.update_one(
        query,
        {'$set': {'read': True}}
    )
    
    return result.modified_count > 0

def mark_all_notifications_read(username):
    """
    Mark all notifications as read for a user
    
    Args:
        username (str): The username
        
    Returns:
        int: Number of notifications marked as read
    """
    result = notifications_collection.update_many(
        {'username': username, 'read': False},
        {'$set': {'read': True}}
    )
    
    return result.modified_count

def get_unread_notification_count(username):
    """
    Get count of unread notifications for a user
    
    Args:
        username (str): The username
        
    Returns:
        int: Count of unread notifications
    """
    return notifications_collection.count_documents({
        'username': username,
        'read': False
    })

def delete_user_notifications(username):
    """
    Delete all notifications for a user
    
    Args:
        username (str): The username
        
    Returns:
        int: Number of notifications deleted
    """
    result = notifications_collection.delete_many({'username': username})
    return result.deleted_count

def delete_notification(notification_id, username=None):
    """
    Delete a specific notification
    
    Args:
        notification_id (str): The notification ID
        username (str, optional): Username for permission check
        
    Returns:
        bool: True if successful, False otherwise
    """
    query = {'id': notification_id}
    if username:
        query['username'] = username
        
    result = notifications_collection.delete_one(query)
    return result.deleted_count > 0

def get_notification_details(notification_id, username=None):
    """
    Get detailed information about a notification for navigation
    
    Args:
        notification_id (str): The notification ID
        username (str, optional): Username for permission check
        
    Returns:
        dict: Notification details with navigation information
    """
    query = {'id': notification_id}
    if username:
        query['username'] = username
        
    notification = notifications_collection.find_one(query, {'_id': 0})
    
    if not notification:
        return None
    
    details = {'notification': notification}
    
    # For comment notifications, get the associated app and version
    if notification.get('reference_type') == 'comment' and notification.get('reference_id'):
        comment = comments_collection.find_one({'id': notification.get('reference_id')}, {'_id': 0})
        if comment:
            details['app_id'] = comment.get('app_id')
            details['version'] = comment.get('version')
    
    # For access notifications, get the app details
    if notification.get('reference_type') == 'app' and notification.get('reference_id'):
        app = apps_collection.find_one({'id': notification.get('reference_id')}, {'_id': 0})
        if app:
            details['app_id'] = app.get('id')
    
    return details