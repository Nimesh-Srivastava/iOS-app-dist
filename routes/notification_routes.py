from flask import Blueprint, request, jsonify, session, render_template, flash, redirect, url_for
import database as db
from utils.decorators import login_required
from utils.file_utils import format_datetime
from bson import ObjectId
from datetime import datetime

notification_bp = Blueprint('notification', __name__)

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