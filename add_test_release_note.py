#!/usr/bin/env python3
# Script to add detailed test release notes to the first app in the database

import database as db
import sys
from datetime import datetime

def add_test_release_note():
    """Add detailed test release notes to the first app in the database for testing purposes"""
    try:
        db.initialize_db()
        apps = db.get_apps()
        
        if not apps:
            print("No apps found in database")
            return False
        
        # Get the first app
        app = apps[0]
        app_id = app.get('id')
        app_name = app.get('name')
        app_version = app.get('version', '1.0.0')
        
        print(f"Adding test release notes to app: {app_name} (v{app_version})")
        
        # Create a detailed test release note
        current_date = datetime.now().strftime("%B %d, %Y")
        test_release_notes = f"""# {app_name} v{app_version} - Test Release Notes ({current_date})

## New Features
- Added enhanced user authentication system
- Improved UI with new dark mode support
- Added offline mode functionality
- Performance optimizations for large datasets

## Bug Fixes
- Fixed crash when opening settings screen on iOS 16
- Resolved layout issues on iPad devices
- Fixed memory leak in background processes
- Corrected text alignment in RTL languages

## Known Issues
- Bluetooth connectivity may be unstable on some devices
- Video playback on external displays needs further optimization

Thank you for using {app_name}! Please report any issues to our support team."""

        # Update the app with the test release notes
        app['release_notes'] = test_release_notes
        db.save_app(app)
        
        # Also add test release notes to the first version if available
        versions = app.get('versions', [])
        if versions:
            version = versions[0]
            version_num = version.get('version', 'Unknown')
            
            # Create a different release note for the version
            version_date = datetime.now().strftime("%b %d")
            version['release_notes'] = f"""Version {version_num} ({version_date})
            
- Initial version release
- Core functionality implemented
- Basic user interface
- Essential features only"""
            
            # Save the app with updated version
            db.save_app(app)
            print(f"Updated release notes for version {version_num}")
        
        print(f"\nSuccessfully added test release notes to {app_name}")
        print("Check the app_detail page to see how the release notes are displayed")
        return True
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("Adding test release notes to the first app in the database...")
    success = add_test_release_note()
    
    if success:
        print("Script completed successfully.")
    else:
        print("Script failed.")
        sys.exit(1) 