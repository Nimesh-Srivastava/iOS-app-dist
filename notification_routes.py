from flask import jsonify, Blueprint
from flask_login import login_required, session
from .notification_services import get_notification_details, mark_notification_read, delete_notification

notification_bp = Blueprint('notifications', __name__)

@notification_bp.route('/api/notification/<notification_id>', methods=['GET'])
@login_required
def notification_details(notification_id):
    """
    Get details for a notification and navigate to the related item if applicable
    
    Args:
        notification_id (str): The notification ID
        
    Returns:
        json: Notification details with navigation info
    """
    username = session.get('username')
    details = get_notification_details(notification_id, username)
    
    if not details:
        return jsonify({'success': False, 'message': 'Notification not found'}), 404
        
    # Mark as read when details are viewed
    mark_notification_read(notification_id, username)
    
    return jsonify({'success': True, 'details': details})

@notification_bp.route('/api/notification/<notification_id>', methods=['DELETE'])
@login_required
def delete_notification_route(notification_id):
    """
    Delete a notification
    
    Args:
        notification_id (str): The notification ID
        
    Returns:
        json: Status of deletion
    """
    username = session.get('username')
    result = delete_notification(notification_id, username)
    
    if result:
        return jsonify({'success': True, 'message': 'Notification deleted'})
    else:
        return jsonify({'success': False, 'message': 'Failed to delete notification'}), 404 