import os
import uuid
import zipfile
import tempfile
import plistlib
import base64
from PIL import Image
import io
from datetime import datetime, timedelta

# File handling utilities
ALLOWED_EXTENSIONS = {'ipa'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_default_icon():
    """
    Loads the default app icon and returns it as a base64 encoded string.
    Tries multiple locations and falls back to a transparent pixel if all fail.
    
    Returns:
        str: A data URL containing the base64 encoded image
    """
    # First try from the root directory using absolute path
    try:
        default_icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'defaultApp.png')
        with open(default_icon_path, 'rb') as f:
            icon_data = f.read()
            icon_b64 = base64.b64encode(icon_data).decode()
            return f"data:image/png;base64,{icon_b64}"
    except Exception as e:
        pass
    
    # Try from the current directory as a fallback
    try:
        with open('defaultApp.png', 'rb') as f:
            icon_data = f.read()
            icon_b64 = base64.b64encode(icon_data).decode()
            return f"data:image/png;base64,{icon_b64}"
    except Exception as e:
        pass
    
    # Last resort fallback to transparent pixel
    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

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
                    bundle_id = plist_data.get('CFBundleIdentifier', 'unknown')
                    version = plist_data.get('CFBundleShortVersionString', 'unknown')
                    build_number = plist_data.get('CFBundleVersion', 'unknown')
                    name = plist_data.get('CFBundleName', os.path.splitext(filename)[0])
                    
                    # Look for app icon
                    icon_data = None
                    
                    # Try to find app icon file - starting with the primary app icons
                    icon_files = []
                    if 'CFBundleIcons' in plist_data:
                        primary_icons = plist_data['CFBundleIcons'].get('CFBundlePrimaryIcon', {})
                        icon_files = primary_icons.get('CFBundleIconFiles', [])
                    
                    # Try each icon file
                    icon_found = False
                    for icon_name in icon_files:
                        if icon_found:
                            break
                        
                        # Search for the icon file in the ZIP
                        for path in ipa.namelist():
                            if icon_name in path and (path.endswith('.png') or '.png/' in path):
                                try:
                                    with ipa.open(path) as icon_file:
                                        icon_data = icon_file.read()
                                        # Try to open it with PIL to confirm it's an image
                                        Image.open(io.BytesIO(icon_data))
                                        icon_found = True
                                        break
                                except:
                                    # If there's an issue, move on to the next file
                                    pass
                    
                    # If no icon was found, use default
                    if icon_data:
                        # Convert to base64 for storage in the database
                        icon_b64 = base64.b64encode(icon_data).decode()
                        icon_data_url = f"data:image/png;base64,{icon_b64}"
                    else:
                        icon_data_url = load_default_icon()
                    
                    return {
                        'id': app_id,
                        'file_id': file_id,
                        'name': name,
                        'bundle_id': bundle_id,
                        'version': version,
                        'build_number': build_number,
                        'filename': filename,
                        'icon': icon_data_url,
                        'upload_date': datetime.now().isoformat()
                    }
    except Exception as e:
        # In case of issues extracting info
        pass
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    # Default response if anything fails
    return {
        'id': app_id,
        'file_id': file_id,
        'name': os.path.splitext(filename)[0],
        'bundle_id': 'unknown',
        'version': 'unknown',
        'build_number': 'unknown',
        'filename': filename,
        'icon': load_default_icon(),
        'upload_date': datetime.now().isoformat()
    }

def extract_minimal_app_info(file_data, filename, build_id):
    """Extract minimal app information from IPA file data for builds"""
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
                    return {
                        'bundle_id': plist_data.get('CFBundleIdentifier', 'unknown'),
                        'version': plist_data.get('CFBundleShortVersionString', 'unknown'),
                        'build_number': plist_data.get('CFBundleVersion', 'unknown'),
                        'name': plist_data.get('CFBundleName', os.path.splitext(filename)[0])
                    }
    except Exception as e:
        pass
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    
    # Default response if anything fails
    return {
        'bundle_id': 'unknown',
        'version': 'unknown',
        'build_number': 'unknown',
        'name': os.path.splitext(filename)[0]
    }

def format_datetime(dt_string, format_type='standard'):
    """
    Format a datetime string in a readable format
    
    Args:
        dt_string (str): ISO format datetime string
        format_type (str): 'standard' for DD-MMM-YYYY, 'timeago' for relative time
        
    Returns:
        str: Formatted datetime string
    """
    if not dt_string:
        return "Unknown"
        
    try:
        dt = datetime.fromisoformat(dt_string)
    except (ValueError, TypeError):
        return dt_string
        
    if format_type == 'standard':
        return dt.strftime('%d-%b-%Y')  # DD-MMM-YYYY
        
    elif format_type == 'timeago':
        now = datetime.now()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 2592000:
            weeks = int(seconds // 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif seconds < 31536000:
            months = int(seconds // 2592000)
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = int(seconds // 31536000)
            return f"{years} year{'s' if years != 1 else ''} ago"
    
    return dt_string  # Default fallback 