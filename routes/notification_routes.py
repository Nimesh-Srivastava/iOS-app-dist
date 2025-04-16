from flask import Blueprint, request, jsonify, session
import database as db
from utils.decorators import login_required
from utils.file_utils import format_datetime

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