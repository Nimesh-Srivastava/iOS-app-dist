#!/usr/bin/env python3
# Script to add release notes to all existing apps in the database

import database as db
import sys

def add_release_notes_to_apps():
    """Add default release notes to all apps that don't have them"""
    try:
        db.initialize_db()
        apps = db.get_apps()
        
        print(f"Found {len(apps)} apps in database")
        
        updated_count = 0
        for app in apps:
            # Check if the app already has release notes
            if not app.get('release_notes'):
                app_id = app.get('id')
                app_name = app.get('name')
                app_version = app.get('version', '1.0.0')
                
                # Generate default release notes
                release_notes = f"Initial release of {app_name} {app_version}."
                app['release_notes'] = release_notes
                
                # Update app in database
                db.save_app(app)
                updated_count += 1
                print(f"Added release notes to {app_name} (v{app_version})")
            
            # Also check all versions for release notes
            versions = app.get('versions', [])
            for version in versions:
                if not version.get('release_notes'):
                    version_num = version.get('version', 'Unknown')
                    
                    # Generate default release notes for this version
                    version['release_notes'] = f"Update to version {version_num}."
            
            # Save the app with updated versions
            if versions:
                db.save_app(app)
                print(f"Updated {len(versions)} version(s) for {app.get('name')}")
        
        print(f"\nUpdate complete. Added release notes to {updated_count} apps.")
        return True
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("Starting script to add release notes to existing apps...")
    success = add_release_notes_to_apps()
    
    if success:
        print("Script completed successfully.")
    else:
        print("Script failed.")
        sys.exit(1) 