import os
import json
import requests
import logging
import time
import subprocess
from datetime import datetime

# Load environment variables
GITHUB_API_TOKEN = os.environ.get('GITHUB_API_TOKEN', '')
GITHUB_USERNAME = os.environ.get('GITHUB_USERNAME', '')
APPLE_TEAM_ID = os.environ.get('APPLE_TEAM_ID', '')  # Get from environment variable
GITHUB_REPO_URL = os.environ.get('GITHUB_REPO_URL', 'https://github.com/username/app-dist')  # GitHub repository URL

def get_github_repo_url():
    """
    Tries to determine the GitHub repository URL for this project.
    
    Returns:
        str: GitHub repository URL or default value
    """
    try:
        # Try to get from environment variable first (useful for GitHub Actions)
        if 'GITHUB_REPOSITORY' in os.environ:
            return f"https://github.com/{os.environ['GITHUB_REPOSITORY']}"
            
        # Try to get from git config
        result = subprocess.run(
            ['git', 'config', '--get', 'remote.origin.url'], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0 and result.stdout.strip():
            url = result.stdout.strip()
            # Convert SSH URL to HTTPS if needed
            if url.startswith('git@github.com:'):
                url = url.replace('git@github.com:', 'https://github.com/')
            
            # Remove .git suffix if present
            if url.endswith('.git'):
                url = url[:-4]
                
            return url
    except Exception as e:
        logging.warning(f"Could not determine GitHub repository URL: {str(e)}")
        
    # Return default from environment or hardcoded value
    return GITHUB_REPO_URL

def verify_github_token():
    """
    Verify that the GitHub token is valid and has the required permissions
    
    Returns:
        tuple: (bool, str) - (is_valid, message)
    """
    # Skip if no token
    if not GITHUB_API_TOKEN:
        return False, "GitHub API token not configured"
    
    try:
        # Set headers for GitHub API
        headers = {
            'Authorization': f'token {GITHUB_API_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Check token validity by getting user info
        response = requests.get('https://api.github.com/user', headers=headers)
        
        if response.status_code != 200:
            return False, f"GitHub API token is invalid: {response.json().get('message', 'Unknown error')}"
        
        # Check scopes
        scopes = response.headers.get('X-OAuth-Scopes', '').split(', ')
        required_scopes = ['repo']
        
        missing_scopes = [scope for scope in required_scopes if scope not in scopes]
        if missing_scopes:
            return False, f"GitHub token is missing required scopes: {', '.join(missing_scopes)}"
        
        return True, "GitHub token is valid and has required permissions"
    
    except Exception as e:
        return False, f"Error verifying GitHub token: {str(e)}"

def fetch_branches(repo_url):
    """
    Fetch branches from a GitHub repository
    
    Args:
        repo_url (str): The GitHub repository URL
        
    Returns:
        list: A list of branch names
    """
    try:
        # Parse owner and repo from URL
        parts = repo_url.rstrip('/').split('/')
        owner = parts[-2]
        repo = parts[-1]
        
        # Set up headers for GitHub API
        headers = {}
        if GITHUB_API_TOKEN:
            headers['Authorization'] = f'token {GITHUB_API_TOKEN}'
            
        headers['Accept'] = 'application/vnd.github.v3+json'
        
        # Fetch branches
        response = requests.get(
            f'https://api.github.com/repos/{owner}/{repo}/branches',
            headers=headers
        )
        
        if response.status_code != 200:
            logging.error(f"Failed to fetch branches: {response.json().get('message', 'Unknown error')}")
            return []
        
        branches = [branch['name'] for branch in response.json()]
        return branches
    
    except Exception as e:
        logging.error(f"Error fetching branches: {str(e)}")
        return []

def extract_github_repo_info(repo_url):
    """
    Extract owner and repo name from GitHub URL
    
    Args:
        repo_url (str): GitHub repository URL
        
    Returns:
        tuple: (owner, repo)
    """
    # Handle URLs with or without .git extension
    url = repo_url.rstrip('/')
    if url.endswith('.git'):
        url = url[:-4]
        
    # Handle SSH URLs
    if url.startswith('git@github.com:'):
        path = url.split('git@github.com:')[1]
    else:
        # Handle HTTPS URLs
        parts = url.split('github.com/')
        if len(parts) < 2:
            return None, None
        path = parts[1]
    
    # Extract owner and repo
    parts = path.split('/')
    if len(parts) < 2:
        return None, None
        
    return parts[0], parts[1]

def generate_github_workflow(app_name, branch, build_config, build_id):
    """
    Generate GitHub Actions workflow YAML for iOS app build
    
    Args:
        app_name (str): The name of the app
        branch (str): The branch to build from
        build_config (str): The build configuration (Debug/Release)
        build_id (str): The unique ID for this build
        
    Returns:
        str: GitHub workflow YAML content
    """
    # Get team ID from environment
    team_id = APPLE_TEAM_ID
    
    # Sanitize app name for use in filenames
    safe_app_name = app_name.replace(' ', '_').replace("'", '').replace('"', '')
    
    # Generate workflow content
    workflow = f"""name: Build iOS App
on: workflow_dispatch

jobs:
  build:
    name: Build iOS App
    runs-on: macos-latest
    
    steps:
      - name: Checkout Code
        uses: actions/checkout@v2
        with:
          ref: {branch}
      
      - name: Setup Ruby
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: 2.7
          
      - name: Setup Xcode
        uses: maxim-lobanov/setup-xcode@v1
        with:
          xcode-version: latest-stable
          
      - name: Install Cocoapods
        run: |
          gem install cocoapods
          
      - name: Install Dependencies
        run: |
          pod install || pod install --repo-update
        
      - name: Set Build Number
        run: |
          # Get the current build number from Info.plist
          PLIST_PATH=$(find . -name "Info.plist" -path "*/$(echo "{app_name}" | tr '[:upper:]' '[:lower:]')*" | head -n 1)
          if [ -z "$PLIST_PATH" ]; then
            PLIST_PATH=$(find . -name "Info.plist" | head -n 1)
          fi
          echo "Using Info.plist at: $PLIST_PATH"
          
          # Get current version and build number
          CURRENT_VERSION=$(/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" "$PLIST_PATH")
          CURRENT_BUILD=$(/usr/libexec/PlistBuddy -c "Print :CFBundleVersion" "$PLIST_PATH")
          
          # Generate new build number based on timestamp
          NEW_BUILD=$(date +%Y%m%d%H%M)
          
          # Update Info.plist
          /usr/libexec/PlistBuddy -c "Set :CFBundleVersion $NEW_BUILD" "$PLIST_PATH"
          
          echo "Updated build number: $CURRENT_VERSION ($CURRENT_BUILD) -> $CURRENT_VERSION ($NEW_BUILD)"
      
      - name: Build App
        env:
          TEAM_ID: {team_id}
        run: |
          # Find the workspace or project file
          WORKSPACE=$(find . -name "*.xcworkspace" | head -n 1)
          PROJECT=$(find . -name "*.xcodeproj" | head -n 1)
          
          SCHEME=""
          if [ -n "$WORKSPACE" ]; then
            # Get scheme from workspace
            SCHEME=$(xcodebuild -workspace "$WORKSPACE" -list | grep -A 10 "Schemes:" | tail -n +2 | head -n 1 | xargs)
            
            # Build using workspace
            xcodebuild clean archive -workspace "$WORKSPACE" -scheme "$SCHEME" -configuration {build_config} -archivePath ./build/{safe_app_name}.xcarchive CODE_SIGN_IDENTITY="Apple Development" DEVELOPMENT_TEAM="$TEAM_ID"
          else
            # Get scheme from project
            SCHEME=$(xcodebuild -project "$PROJECT" -list | grep -A 10 "Schemes:" | tail -n +2 | head -n 1 | xargs)
            
            # Build using project
            xcodebuild clean archive -project "$PROJECT" -scheme "$SCHEME" -configuration {build_config} -archivePath ./build/{safe_app_name}.xcarchive CODE_SIGN_IDENTITY="Apple Development" DEVELOPMENT_TEAM="$TEAM_ID"
          fi
          
          # Create IPA
          xcodebuild -exportArchive -archivePath ./build/{safe_app_name}.xcarchive -exportPath ./build -exportOptionsPlist ExportOptions.plist || {{
            # If export fails due to missing export options, create a default one
            cat > ExportOptions.plist << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>development</string>
    <key>teamID</key>
    <string>$TEAM_ID</string>
</dict>
</plist>
EOF
            xcodebuild -exportArchive -archivePath ./build/{safe_app_name}.xcarchive -exportPath ./build -exportOptionsPlist ExportOptions.plist
          }}
      
      - name: Notify Build Status
        if: always()
        run: |
          # Find the IPA file
          IPA_FILE=$(find ./build -name "*.ipa" | head -n 1)
          
          if [ -n "$IPA_FILE" ]; then
            echo "Build succeeded. IPA file: $IPA_FILE"
            
            # Convert IPA to base64
            BASE64_IPA=$(base64 -i "$IPA_FILE" | tr -d '\\n')
            
            # Get filename
            FILENAME=$(basename "$IPA_FILE")
            
            # Notify successful build with IPA
            curl -X POST "${{{{ secrets.CALLBACK_URL }}}}/api/build_complete" \\
              -H "Content-Type: application/json" \\
              -d "{{
                \\"build_id\\": \\"{build_id}\\",
                \\"status\\": \\"success\\",
                \\"filename\\": \\"$FILENAME\\",
                \\"ipa_data\\": \\"$BASE64_IPA\\"
              }}"
          else
            echo "Build failed. No IPA file found."
            
            # Notify build failure
            curl -X POST "${{{{ secrets.CALLBACK_URL }}}}/api/build_complete" \\
              -H "Content-Type: application/json" \\
              -d "{{
                \\"build_id\\": \\"{build_id}\\",
                \\"status\\": \\"failed\\",
                \\"error\\": \\"Build failed. No IPA file was generated.\\"
              }}"
          fi
"""
    return workflow

def fork_and_setup_github_workflow(build_id, repo_url, branch, app_name, build_config='Release'):
    """
    Fork a GitHub repository and set up a workflow to build an iOS app
    
    Args:
        build_id (str): The build ID
        repo_url (str): The GitHub repository URL
        branch (str): The branch to build from
        app_name (str): The name of the app
        build_config (str): The build configuration (Debug/Release)
        
    Returns:
        tuple: (status, message, fork_info)
    """
    from models import update_build_status
    
    # Check if GitHub token is available
    if not GITHUB_API_TOKEN:
        update_build_status(build_id, 'failed', "GitHub API token not configured")
        return False, "GitHub API token not configured", None
    
    # Extract owner and repo from URL
    source_owner, source_repo = extract_github_repo_info(repo_url)
    if not source_owner or not source_repo:
        update_build_status(build_id, 'failed', f"Invalid GitHub repository URL: {repo_url}")
        return False, f"Invalid GitHub repository URL: {repo_url}", None
    
    # Get authenticated user
    headers = {
        'Authorization': f'token {GITHUB_API_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        # Get the authenticated user
        user_response = requests.get('https://api.github.com/user', headers=headers)
        if user_response.status_code != 200:
            error_msg = f"GitHub API error: {user_response.json().get('message', 'Unknown error')}"
            update_build_status(build_id, 'failed', error_msg)
            return False, error_msg, None
            
        user = user_response.json()
        fork_owner = user['login']
        
        # Check if a fork already exists
        fork_name = f"{source_repo}-{build_id[:8]}"  # Use part of build ID to ensure uniqueness
        
        # Create a fork with a custom name (by creating a new repo and pushing to it)
        fork_response = requests.post(
            'https://api.github.com/repos/temp/temp',  # This is a placeholder URL
            headers=headers,
            json={
                'name': fork_name,
                'description': f"Temporary fork of {source_owner}/{source_repo} for building",
                'private': True,
                'has_issues': False,
                'has_projects': False,
                'has_wiki': False
            }
        )
        
        # Actually create the empty repo
        create_repo_response = requests.post(
            'https://api.github.com/user/repos',
            headers=headers,
            json={
                'name': fork_name,
                'description': f"Temporary fork of {source_owner}/{source_repo} for building",
                'private': True,
                'has_issues': False,
                'has_projects': False,
                'has_wiki': False
            }
        )
        
        if create_repo_response.status_code not in (201, 422):  # 422 means already exists
            error_msg = f"Failed to create temporary repository: {create_repo_response.json().get('message', 'Unknown error')}"
            update_build_status(build_id, 'failed', error_msg)
            return False, error_msg, None
            
        fork_url = f"https://github.com/{fork_owner}/{fork_name}"
        
        # Clone the source repo to a temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            clone_cmd = ['git', 'clone', '--branch', branch, repo_url, temp_dir]
            clone_process = subprocess.run(clone_cmd, capture_output=True, text=True)
            
            if clone_process.returncode != 0:
                error_msg = f"Failed to clone repository: {clone_process.stderr}"
                update_build_status(build_id, 'failed', error_msg)
                return False, error_msg, None
                
            # Create GitHub Actions workflow file
            workflow_content = generate_github_workflow(app_name, branch, build_config, build_id)
            
            # Ensure workflows directory exists
            os.makedirs(os.path.join(temp_dir, '.github', 'workflows'), exist_ok=True)
            
            # Write workflow file
            with open(os.path.join(temp_dir, '.github', 'workflows', 'build.yml'), 'w') as f:
                f.write(workflow_content)
                
            # Initialize git repo if not initialized
            subprocess.run(['git', 'init'], cwd=temp_dir, capture_output=True)
            
            # Configure git
            subprocess.run(['git', 'config', 'user.email', "actions@github.com"], cwd=temp_dir)
            subprocess.run(['git', 'config', 'user.name', "GitHub Actions"], cwd=temp_dir)
            
            # Add remote for the fork
            subprocess.run(['git', 'remote', 'remove', 'origin'], cwd=temp_dir, capture_output=True)
            subprocess.run(['git', 'remote', 'add', 'origin', 
                           f"https://{fork_owner}:{GITHUB_API_TOKEN}@github.com/{fork_owner}/{fork_name}.git"], 
                           cwd=temp_dir)
            
            # Add workflow file
            subprocess.run(['git', 'add', '.github/workflows/build.yml'], cwd=temp_dir)
            subprocess.run(['git', 'add', '.'], cwd=temp_dir)  # Add all files
            
            # Commit changes
            subprocess.run(['git', 'commit', '-m', f"Add workflow for building {app_name}"], cwd=temp_dir)
            
            # Push to fork
            push_process = subprocess.run(['git', 'push', '-u', 'origin', branch], cwd=temp_dir, capture_output=True, text=True)
            
            if push_process.returncode != 0:
                # Try pushing to main branch instead
                push_process = subprocess.run(['git', 'push', '-u', 'origin', f"{branch}:main"], cwd=temp_dir, capture_output=True, text=True)
                
                if push_process.returncode != 0:
                    error_msg = f"Failed to push to fork repository: {push_process.stderr}"
                    update_build_status(build_id, 'failed', error_msg)
                    return False, error_msg, None
        
        # Trigger the workflow
        dispatch_url = f"https://api.github.com/repos/{fork_owner}/{fork_name}/actions/workflows/build.yml/dispatches"
        dispatch_response = requests.post(
            dispatch_url,
            headers=headers,
            json={'ref': branch}
        )
        
        if dispatch_response.status_code == 404:
            # Try with main branch
            dispatch_response = requests.post(
                dispatch_url,
                headers=headers,
                json={'ref': 'main'}
            )
        
        if dispatch_response.status_code not in (204, 200):
            error_msg = f"Failed to trigger workflow: {dispatch_response.text}"
            update_build_status(build_id, 'failed', error_msg)
            return False, error_msg, None
            
        # Store fork info for later cleanup
        fork_info = {
            'owner': fork_owner,
            'repo': fork_name,
            'url': fork_url
        }
        
        return True, "Build started", fork_info
        
    except Exception as e:
        error_msg = f"Error setting up GitHub workflow: {str(e)}"
        update_build_status(build_id, 'failed', error_msg)
        return False, error_msg, None

def cleanup_fork(owner, repo, headers=None):
    """
    Delete a forked repository
    
    Args:
        owner (str): The owner of the fork
        repo (str): The name of the fork
        headers (dict, optional): GitHub API headers
        
    Returns:
        bool: True if successful, False otherwise
    """
    if headers is None:
        headers = {
            'Authorization': f'token {GITHUB_API_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
    try:
        # Delete the fork
        response = requests.delete(
            f'https://api.github.com/repos/{owner}/{repo}',
            headers=headers
        )
        
        if response.status_code in (204, 404):  # 204: Success, 404: Already deleted
            return True
            
        logging.error(f"Failed to delete fork: {response.json().get('message', 'Unknown error')}")
        return False
    except Exception as e:
        logging.error(f"Error deleting fork: {str(e)}")
        return False

def monitor_github_workflow(build_id, fork_info):
    """
    Monitor a GitHub Actions workflow for completion
    This is meant to be run in a separate thread
    
    Args:
        build_id (str): The build ID
        fork_info (dict): Information about the forked repository
    """
    from models import update_build_status
    
    owner = fork_info['owner']
    repo = fork_info['repo']
    
    headers = {
        'Authorization': f'token {GITHUB_API_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    # Monitor for up to 30 minutes (checking every 30 seconds)
    max_checks = 60
    current_check = 0
    
    while current_check < max_checks:
        current_check += 1
        
        try:
            # Check workflow runs
            runs_response = requests.get(
                f'https://api.github.com/repos/{owner}/{repo}/actions/runs',
                headers=headers
            )
            
            if runs_response.status_code != 200:
                time.sleep(30)
                continue
                
            runs = runs_response.json().get('workflow_runs', [])
            
            if not runs:
                update_build_status(build_id, 'in_progress', "Waiting for GitHub Actions workflow to start...")
                time.sleep(30)
                continue
                
            # Get the latest run
            latest_run = runs[0]
            status = latest_run.get('status')
            conclusion = latest_run.get('conclusion')
            
            # Update build status based on workflow status
            if status == 'completed':
                if conclusion == 'success':
                    # Wait for webhook callback
                    update_build_status(build_id, 'in_progress', "Build completed in GitHub Actions. Waiting for artifact...")
                elif conclusion in ('failure', 'cancelled', 'timed_out'):
                    update_build_status(build_id, 'failed', f"GitHub Actions workflow {conclusion}")
                    cleanup_fork(owner, repo, headers)
                    return
            else:
                update_build_status(build_id, 'in_progress', f"GitHub Actions workflow {status}...")
                
            # Wait 30 seconds before checking again
            time.sleep(30)
            
        except Exception as e:
            logging.error(f"Error monitoring GitHub workflow: {str(e)}")
            time.sleep(30)
    
    # If we get here, the build timed out
    update_build_status(build_id, 'failed', "Build timed out after 30 minutes")
    cleanup_fork(owner, repo, headers)

def cleanup_fork_on_failure(build):
    """
    Clean up fork for a failed build
    
    Args:
        build (dict): The build data
    """
    # Check if fork info exists
    if not build or 'fork_info' not in build:
        return
    
    fork_info = build['fork_info']
    if not isinstance(fork_info, dict) or 'owner' not in fork_info or 'repo' not in fork_info:
        return
    
    # Clean up the fork
    cleanup_fork(fork_info['owner'], fork_info['repo']) 