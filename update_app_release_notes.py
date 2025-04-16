#!/usr/bin/env python3
# Script to update release notes for a specific app by providing its ID

import database as db
import sys
import argparse
from datetime import datetime

def update_app_release_notes(app_id, release_notes=None):
    """
    Update release notes for a specific app by ID
    
    Args:
        app_id (str): The ID of the app to update
        release_notes (str, optional): The release notes to set. If None, use default test notes.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        db.initialize_db()
        
        # Get the app
        app = db.get_app(app_id)
        if not app:
            print(f"App with ID {app_id} not found")
            return False
        
        app_name = app.get('name')
        app_version = app.get('version', '1.0.0')
        
        print(f"Updating release notes for app: {app_name} (v{app_version})")
        
        # If no release notes provided, create a detailed test release note
        if not release_notes:
            current_date = datetime.now().strftime("%B %d, %Y")
            release_notes = f"""# {app_name} v{app_version} - Release Notes ({current_date})

## What's New
- Enhanced user experience and performance improvements
- Added support for latest iOS features
- Redesigned user interface for better usability
- Optimized for better battery life

## Bug Fixes
- Fixed various minor issues and stability improvements
- Improved compatibility with iOS {app_version}

Thank you for using {app_name}!"""
        
        # Update the app with the release notes
        app['release_notes'] = release_notes
        db.save_app(app)
        
        print(f"\nSuccessfully updated release notes for {app_name}")
        print("Check the app_detail page to see how the release notes are displayed")
        return True
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Update release notes for a specific app')
    parser.add_argument('app_id', help='The ID of the app to update')
    parser.add_argument('--notes', '-n', help='Release notes to set (optional)')
    
    args = parser.parse_args()
    
    # Update the release notes
    success = update_app_release_notes(args.app_id, args.notes)
    
    if success:
        print("Script completed successfully.")
        return 0
    else:
        print("Script failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 