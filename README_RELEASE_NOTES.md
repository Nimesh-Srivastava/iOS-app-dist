# Release Notes Update Scripts

This directory contains scripts to update and add release notes to existing apps in the database.

## Overview

The following scripts are available:

1. `add_release_notes.py` - Adds default release notes to all apps that don't have them
2. `add_test_release_note.py` - Adds a detailed test release note to the first app in the database
3. `update_app_release_notes.py` - Updates release notes for a specific app by ID
4. `update_sample_app.py` - Contains code that can be run directly in the Python shell

## Requirements

- Python 3.x
- Access to the MongoDB database
- Necessary permissions to modify apps

## Usage

### Adding release notes to all apps

```bash
python3 ./add_release_notes.py
```

This will scan all apps in the database and add default release notes to any app that doesn't already have them.

### Adding test release notes to the first app

```bash
python3 ./add_test_release_note.py
```

This will add a detailed test release note to the first app found in the database. Useful for testing how release notes appear in the UI.

### Updating release notes for a specific app

```bash
python3 ./update_app_release_notes.py <APP_ID>
```

Replace `<APP_ID>` with the ID of the app you want to update.

You can also provide custom release notes:

```bash
python3 ./update_app_release_notes.py <APP_ID> --notes "Your release notes here"
```

### Using in Python Shell

If the above methods do not work, you can use the `update_sample_app.py` script in the Python shell:

1. Start the Python shell in your application environment
2. Run the following code:

```python
from update_sample_app import update_first_app_with_release_notes
update_first_app_with_release_notes()
```

Alternatively, you can copy and paste the code from the `SHELL_CODE` variable in `update_sample_app.py` directly into your Python shell.

### Using in Flask Shell (Recommended)

The most reliable way to update release notes is through the Flask shell, which has the correct application context:

1. Navigate to the root directory of the application
2. Start the Flask shell:
   ```bash
   flask shell
   ```
3. Run the update function:
   ```python
   from flask_shell_update import update_release_notes_in_db
   update_release_notes_in_db()
   ```

This method ensures that the database connection is properly configured within the Flask application context.

## Verifying

After running any of these scripts, visit the app detail page to verify that the release notes are being displayed correctly.

## Troubleshooting

If you encounter database connection issues:

1. Make sure MongoDB is running
2. Check that your database credentials are correct
3. Verify that you have the correct permissions to access and modify the database

For any other issues, please check the application logs for more details. 