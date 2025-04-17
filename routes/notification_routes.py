from flask import Blueprint, request, jsonify, session, render_template, flash, redirect, url_for, Response, stream_with_context
import database as db
from utils.decorators import login_required
from utils.file_utils import format_datetime
from bson import ObjectId
from datetime import datetime
import json
import time
import queue
import threading

notification_bp = Blueprint('notification', __name__)

# Create a global message queue for each user
notification_queues = {}
queue_lock = threading.Lock()

def get_queue_for_user(user_id):
    """Get or create a message queue for a user"""
    with queue_lock:
        if user_id not in notification_queues:
            notification_queues[user_id] = queue.Queue()
        return notification_queues[user_id]

def send_notification_to_user(username, notification):
    """
    Send a notification to a specific user's queue
    
    Args:
        username (str): Username to notify
        notification (dict): Notification data
        
    Returns:
        bool: True if notification was sent, False otherwise
    """
    from database import db
    user = db.get_user(username)
    if not user:
        return False
        
    try:
        # Get the user ID or use username if ID is not available
        user_id = user.get('id', username)
        user_queue = get_queue_for_user(user_id)
        user_queue.put(notification)
        return True
    except Exception as e:
        print(f"Error sending notification to user {username}: {e}")
        return False

@notification_bp.route('/notifications')
@login_required
def get_notifications():
    """
    Get notifications for the logged-in user
    
    Query parameters:
        include_read (bool): Whether to include read notifications
        limit (int): Maximum number of notifications to return
    """
    include_read = request.args.get('include_read', 'false').lower() == 'true'
    try:
        limit = int(request.args.get('limit', '20'))
    except ValueError:
        limit = 20
    
    username = session.get('username')
    notifications = db.get_user_notifications(username, limit, include_read)
    
    # Format timestamps for frontend display
    for notification in notifications:
        notification['time_ago'] = format_datetime(notification.get('timestamp'), 'timeago')
    
    return jsonify({
        'notifications': notifications,
        'unread_count': db.get_unread_notification_count(username)
    })

@notification_bp.route('/notifications/count')
@login_required
def get_notification_count():
    """Get the count of unread notifications for the logged-in user"""
    username = session.get('username')
    count = db.get_unread_notification_count(username)
    
    return jsonify({
        'unread_count': count
    })

@notification_bp.route('/notifications/mark_read/<notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    username = session.get('username')
    success = db.mark_notification_read(notification_id, username)
    
    return jsonify({
        'success': success,
        'unread_count': db.get_unread_notification_count(username)
    })

@notification_bp.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_read():
    """Mark all notifications as read for the logged-in user"""
    username = session.get('username')
    count = db.mark_all_notifications_read(username)
    
    return jsonify({
        'success': True,
        'marked_count': count,
        'unread_count': 0
    })

@notification_bp.route('/notifications/<notification_id>/details')
@login_required
def notification_details(notification_id):
    """Get detailed information about a notification for navigation"""
    username = session.get('username')
    
    # Fetch the notification
    notification = db.notifications_collection.find_one({
        'id': notification_id,
        'username': username
    }, {'_id': 0})
    
    if not notification:
        return jsonify({'success': False, 'message': 'Notification not found'})
    
    response_data = {'success': True}
    
    # For comment notifications, get the associated app_id
    if notification.get('reference_type') == 'comment' and notification.get('reference_id'):
        comment = db.comments_collection.find_one({'id': notification.get('reference_id')}, {'_id': 0})
        if comment:
            response_data['app_id'] = comment.get('app_id')
            response_data['version'] = comment.get('version')
    
    return jsonify(response_data)

@notification_bp.route('/notifications/delete/<notification_id>', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """Delete a notification"""
    username = session.get('username')
    
    # Delete the notification
    result = db.notifications_collection.delete_one({
        'id': notification_id,
        'username': username
    })
    
    success = result.deleted_count > 0
    
    return jsonify({
        'success': success,
        'unread_count': db.get_unread_notification_count(username)
    })

@notification_bp.route('/all-notifications')
@login_required
def all_notifications():
    """Display all notifications for the current user"""
    username = session.get('username')
    
    # Get all notifications (both read and unread, with no limit)
    notifications = db.notifications_collection.find(
        {'username': username}, 
        {'_id': 0}
    ).sort('timestamp', -1)
    
    # Format timestamps
    formatted_notifications = []
    for notification in notifications:
        notification['time_ago'] = format_datetime(notification.get('timestamp'), 'timeago')
        notification['formatted_date'] = format_datetime(notification.get('timestamp'))
        formatted_notifications.append(notification)
    
    return render_template(
        'all_notifications.html',
        notifications=formatted_notifications,
        unread_count=db.get_unread_notification_count(username)
    )

@notification_bp.route('/notifications/list')
@login_required
def list_notifications():
    """Get a list of notifications for the current user"""
    user_id = session.get('user_id')
    limit = request.args.get('limit', 5, type=int)
    notifications = db.get_user_notifications(user_id, limit=limit)
    
    # Format the date for each notification
    for notification in notifications:
        created_at = notification.get('created_at', datetime.now())
        notification['formatted_date'] = created_at.strftime('%B %d, %Y at %I:%M %p')
    
    # Count unread notifications
    unread_count = db.get_unread_notification_count(user_id)
    
    return jsonify({
        'notifications': notifications,
        'unread_count': unread_count
    })

@notification_bp.route('/notifications/mark_read/<notification_id>', methods=['POST'])
@login_required
def mark_read(notification_id):
    """Mark a notification as read"""
    user_id = session.get('user_id')
    
    try:
        # Convert string ID to ObjectId if needed
        if isinstance(notification_id, str):
            notification_id = ObjectId(notification_id)
        
        success = db.mark_notification_read(notification_id, user_id)
        unread_count = db.get_unread_notification_count(user_id)
        
        return jsonify({
            'success': success,
            'unread_count': unread_count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@notification_bp.route('/notifications/mark_all_read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read for the current user"""
    user_id = session.get('user_id')
    
    try:
        count = db.mark_all_notifications_read(user_id)
        return jsonify({
            'success': True,
            'count': count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@notification_bp.route('/notifications/delete/<notification_id>', methods=['POST'])
@login_required
def delete(notification_id):
    """Delete a notification"""
    user_id = session.get('user_id')
    
    try:
        # Convert string ID to ObjectId if needed
        if isinstance(notification_id, str):
            notification_id = ObjectId(notification_id)
        
        success = db.delete_notification(notification_id, user_id)
        unread_count = db.get_unread_notification_count(user_id)
        
        return jsonify({
            'success': success,
            'unread_count': unread_count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@notification_bp.route('/notifications/<notification_id>/details')
@login_required
def get_details(notification_id):
    """Get detailed information about a notification for navigation purposes"""
    user_id = session.get('user_id')
    
    try:
        # Convert string ID to ObjectId if needed
        if isinstance(notification_id, str):
            notification_id = ObjectId(notification_id)
        
        # Get the notification details
        details = db.get_notification_details(notification_id, user_id)
        
        return jsonify({
            'success': True,
            **details
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@notification_bp.route('/api/notifications/stream')
@login_required
def notification_stream():
    """
    Server-Sent Events endpoint for real-time notifications
    
    Returns:
        Response: SSE stream for the current user
    """
    def generate():
        user_id = session.get('user_id')
        if not user_id:
            return
            
        user_queue = get_queue_for_user(user_id)
        
        # Send initial ping to establish connection
        yield "event: ping\ndata: {}\n\n"
        
        try:
            while True:
                try:
                    # Try to get a message from the queue, with a timeout
                    message = user_queue.get(block=True, timeout=30)
                    
                    # Format as SSE event
                    data_str = json.dumps(message)
                    yield f"event: notification\ndata: {data_str}\n\n"
                except queue.Empty:
                    # No message for 30 seconds, send keepalive
                    yield "event: ping\ndata: {}\n\n"
                    
        except GeneratorExit:
            # Client disconnected
            pass
            
    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'  # Disable Nginx buffering
        }
    )

# Helper function to push notification - call this when creating notifications
def push_real_time_notification(username, notification):
    """
    Push a real-time notification to a user's SSE stream
    
    Args:
        username (str): Username to notify
        notification (dict): Notification data
    """
    # Add any needed processing to the notification
    if 'timestamp' in notification:
        # Add time_ago field
        from datetime import datetime
        timestamp = datetime.fromisoformat(notification['timestamp'])
        now = datetime.now()
        delta = now - timestamp
        
        if delta.days > 0:
            notification['time_ago'] = f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            notification['time_ago'] = f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            notification['time_ago'] = f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            notification['time_ago'] = "just now"
    
    # Use the new function that handles usernames
    return send_notification_by_username(username, notification)

def send_app_refresh_notification(app_id, refresh_type):
    """
    Send app refresh notification to all users who have access to the app
    
    Args:
        app_id (str): ID of the app that needs to be refreshed
        refresh_type (str): Type of refresh ('share', 'unshare', 'comment_add', 'comment_delete')
    """
    # Import here to avoid circular imports
    from database import db
    
    # Get the app to check which users have access
    app = db.get_app(app_id)
    if not app:
        return False
        
    # Get all users who have access to this app
    shared_users = db.get_shared_users(app_id)
    
    # Add the owner to the list of users
    if 'owner' in app:
        shared_users.append(app['owner'])
        
    # Add admin users who have access to all apps
    admin_users = [user['username'] for user in db.get_users() if user.get('role') == 'admin']
    for admin in admin_users:
        if admin not in shared_users:
            shared_users.append(admin)
    
    # Create and send the refresh notification to each user
    for username in shared_users:
        notification = {
            'type': 'app_refresh',
            'app_id': app_id,
            'app_name': app.get('name', 'Unknown App'),
            'refresh_type': refresh_type,
            'timestamp': datetime.now().isoformat()
        }
        
        # Send notification to user's queue by username
        send_notification_by_username(username, notification)
    
    return True

def send_notification_to_user(user_id, notification):
    """Send a notification to a specific user's queue"""
    if not user_id:
        return False
        
    with queue_lock:
        if user_id in notification_queues:
            try:
                notification_queues[user_id].put_nowait(notification)
                return True
            except queue.Full:
                return False
        return False

def send_notification_by_username(username, notification):
    """
    Send a notification to a specific user's queue using their username
    
    Args:
        username (str): Username to notify
        notification (dict): Notification data
        
    Returns:
        bool: True if notification was sent, False otherwise
    """
    from database import db
    user = db.get_user(username)
    if not user:
        return False
        
    try:
        # Get the user ID or use username if ID is not available
        user_id = user.get('id', username)
        user_queue = get_queue_for_user(user_id)
        user_queue.put(notification)
        return True
    except Exception as e:
        print(f"Error sending notification to user {username}: {e}")
        return False 