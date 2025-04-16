#!/usr/bin/env python3
"""
This script contains code that can be run directly in the Python shell
of the app to update a sample app with release notes.

Usage in Python shell:
```
from update_sample_app import update_first_app_with_release_notes
update_first_app_with_release_notes()
```
"""

import database as db
from datetime import datetime

def update_first_app_with_release_notes():
    """
    Update the first app in the database with test release notes.
    This function is designed to be called directly from the Python shell.
    """
    # Make sure database is initialized
    db.initialize_db()
    
    # Get the first app
    apps = db.get_apps()
    if not apps:
        print("No apps found in database")
        return False
    
    app = apps[0]
    app_id = app.get('id')
    app_name = app.get('name')
    app_version = app.get('version', '1.0.0')
    
    print(f"Adding release notes to app: {app_name} (ID: {app_id})")
    
    # Create release notes
    current_date = datetime.now().strftime("%B %d, %Y")
    release_notes = f"""# {app_name} {app_version} Release Notes

## New in this version:
- Added new features and functionality
- Improved performance and stability
- Enhanced user interface
- Bug fixes and improvements

Released on {current_date}
"""
    
    # Update the app
    app['release_notes'] = release_notes
    db.save_app(app)
    
    # Also add release notes to versions
    updated_versions = 0
    for version in app.get('versions', []):
        if not version.get('release_notes'):
            version_num = version.get('version', 'Unknown')
            version['release_notes'] = f"Release notes for version {version_num}"
            updated_versions += 1
    
    # If versions were updated, save the app again
    if updated_versions > 0:
        db.save_app(app)
        print(f"Updated {updated_versions} version(s) with release notes")
    
    print(f"Successfully updated app {app_name} with release notes")
    print(f"App ID: {app_id}")
    return True

# Code that can be directly copied and pasted into the shell
SHELL_CODE = """
import database as db
from datetime import datetime

# Initialize database
db.initialize_db()

# Get all apps
apps = db.get_apps()
if not apps:
    print("No apps found in database")
else:
    # Get the first app
    app = apps[0]
    app_id = app.get('id')
    app_name = app.get('name')
    app_version = app.get('version', '1.0.0')
    
    print(f"Adding release notes to app: {app_name} (ID: {app_id})")
    
    # Create release notes
    current_date = datetime.now().strftime("%B %d, %Y")
    release_notes = f"# {app_name} {app_version} Release Notes\\n\\n"
    release_notes += "## New in this version:\\n"
    release_notes += "- Added new features and functionality\\n"
    release_notes += "- Improved performance and stability\\n"
    release_notes += "- Enhanced user interface\\n"
    release_notes += "- Bug fixes and improvements\\n\\n"
    release_notes += f"Released on {current_date}"
    
    # Update the app
    app['release_notes'] = release_notes
    db.save_app(app)
    
    print(f"Successfully updated app {app_name} with release notes")
    print(f"App ID: {app_id}")
"""

if __name__ == "__main__":
    print("This script contains helper functions to update apps with release notes.")
    print("It can be imported and used in the Python shell.")
    print("\nTo use directly in Python shell, copy and paste the following code:")
    print("-" * 80)
    print(SHELL_CODE)
    print("-" * 80) 