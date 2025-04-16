"""
This module contains a function to update release notes for apps.
It is designed to be used within the Flask shell context.

To use in Flask shell:
1. Start Flask shell:
   $ flask shell

2. Execute the following:
   >>> from flask_shell_update import update_release_notes_in_db
   >>> update_release_notes_in_db()
"""

import database as db
from datetime import datetime

def update_release_notes_in_db():
    """
    Add release notes to all apps in the database that don't have them.
    This function is meant to be run from the Flask shell.
    """
    # Get all apps
    apps = db.get_apps()
    print(f"Found {len(apps)} apps in database")
    
    # Track statistics
    updated_apps = 0
    updated_versions = 0
    
    # Generate a timestamp for the release notes
    current_date = datetime.now().strftime("%B %d, %Y")
    
    # Process each app
    for app in apps:
        app_id = app.get('id')
        app_name = app.get('name', 'Unknown App')
        app_version = app.get('version', '1.0.0')
        
        # Update the main app release notes if not present
        if not app.get('release_notes'):
            release_notes = f"""# {app_name} {app_version}

## Release Highlights
- Initial release
- Core functionality included
- Basic features implemented

Released on {current_date}"""
            
            app['release_notes'] = release_notes
            updated_apps += 1
            print(f"Added release notes to app: {app_name}")
        
        # Update version release notes if not present
        for version in app.get('versions', []):
            if not version.get('release_notes'):
                version_num = version.get('version', 'Unknown')
                version_date = version.get('upload_date', '').split('T')[0] if version.get('upload_date') else 'Unknown date'
                
                version['release_notes'] = f"""Version {version_num}

- Release date: {version_date}
- Maintenance update
- Bug fixes and improvements"""
                
                updated_versions += 1
        
        # Save the updated app
        db.save_app(app)
    
    # Print summary
    print(f"\nUpdate complete!")
    print(f"- Updated {updated_apps} apps with release notes")
    print(f"- Updated {updated_versions} individual versions with release notes")
    
    return updated_apps + updated_versions

# If running directly (not in Flask shell), show instructions
if __name__ == "__main__":
    print(__doc__)
    print("\nThis script is meant to be imported in Flask shell.")
    print("Please run 'flask shell' and follow the instructions in the docstring.") 