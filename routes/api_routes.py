from flask import Blueprint, jsonify, request, session, abort
import database as db
import base64
import logging
from datetime import datetime
import json
import os

from utils.decorators import login_required, admin_required
from utils.github_utils import fetch_branches
from utils.file_utils import extract_minimal_app_info
from models import update_build_status

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/apps')
@login_required
def api_apps():
    apps = db.get_apps_for_user(session['username'])
    return jsonify(apps)

@api_bp.route('/api/app/<app_id>')
@login_required
def api_app(app_id):
    app = db.get_app(app_id)
    if not app or not db.get_user_app_access(session['username'], app_id):
        abort(404)
    return jsonify(app)

@api_bp.route('/api/builds')
@login_required
def api_builds():
    builds = []
    all_builds = db.get_builds()
    
    # Filter builds based on user role
    user = db.get_user(session['username'])
    if user and user.get('role') == 'admin':
        builds = all_builds
    else:
        # Only show builds created by the user
        builds = [b for b in all_builds if b.get('user') == session['username']]
        
    return jsonify(builds)

@api_bp.route('/api/build/<build_id>')
@login_required
def api_build(build_id):
    build = db.get_build(build_id)
    if not build or (build.get('user') != session['username'] and 
                     db.get_user(session['username']).get('role') != 'admin'):
        abort(404)
    return jsonify(build)

@api_bp.route('/api/app_status')
def api_app_status():
    # Public API to get basic app status for a QR code link
    app_id = request.args.get('id')
    if not app_id:
        return jsonify({'error': 'App ID required'}), 400
        
    app = db.get_app(app_id)
    if not app:
        return jsonify({'error': 'App not found'}), 404
        
    # Return minimal app info
    return jsonify({
        'id': app.get('id'),
        'name': app.get('name'),
        'version': app.get('version'),
        'build_number': app.get('build_number'),
        'install_url': f"{request.host_url.rstrip('/')}/direct_install/{app_id}"
    })

@api_bp.route('/api/build_status')
@login_required
def api_build_status():
    build_id = request.args.get('id')
    if not build_id:
        return jsonify({'error': 'Build ID required'}), 400
        
    build = db.get_build(build_id)
    if not build:
        return jsonify({'error': 'Build not found'}), 404
        
    # Check if user has access
    if build.get('user') != session['username'] and db.get_user(session['username']).get('role') != 'admin':
        return jsonify({'error': 'Access denied'}), 403
        
    # Return minimal build info
    return jsonify({
        'id': build.get('id'),
        'status': build.get('status'),
        'app_name': build.get('app_name'),
        'log_preview': build.get('log', '')[-500:] if build.get('log') else '',
        'start_time': build.get('start_time'),
        'end_time': build.get('end_time')
    })

@api_bp.route('/api/branches')
@admin_required
def api_branches():
    repo_url = request.args.get('repo_url', '')
    if not repo_url:
        return jsonify([])
        
    branches = fetch_branches(repo_url)
    return jsonify(branches)

@api_bp.route('/api/build_complete', methods=['POST'])
def api_build_complete():
    """
    Webhook callback from GitHub Actions to signal a completed build
    
    Expected JSON payload:
    {
        "build_id": "uuid",
        "status": "success|failed",
        "filename": "app.ipa",  # Only for success
        "ipa_data": "base64_encoded_ipa",  # Only for success
        "error": "error message"  # Only for failed
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Invalid JSON payload'}), 400
            
        build_id = data.get('build_id')
        status = data.get('status')
        
        if not build_id or not status:
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Get build from database
        build = db.get_build(build_id)
        if not build:
            return jsonify({'error': 'Build not found'}), 404
            
        # Handle success
        if status == 'success':
            filename = data.get('filename')
            ipa_data_b64 = data.get('ipa_data')
            
            if not filename or not ipa_data_b64:
                return jsonify({'error': 'Missing IPA data for successful build'}), 400
                
            try:
                # Decode IPA data
                ipa_data = base64.b64decode(ipa_data_b64)
                
                # Save the IPA file
                db.save_build_file(build_id, filename, ipa_data, 'application/octet-stream')
                
                # Extract app info from IPA
                app_info = extract_minimal_app_info(ipa_data, filename, build_id)
                
                # Update build
                build['status'] = 'completed'
                build['end_time'] = datetime.now().isoformat()
                build['output_filename'] = filename
                build['app_info'] = app_info
                build['log'] = (build.get('log', '') + 
                               f"\n\nBuild completed successfully.\nOutput: {filename}\n" +
                               f"App: {app_info.get('name')} {app_info.get('version')} ({app_info.get('build_number')})")
                
                db.save_build(build)
                
                # Clean up GitHub fork if configured to do so
                if os.environ.get('AUTO_CLEANUP_FORKS', 'false').lower() == 'true':
                    if build.get('fork_info'):
                        from utils.github_utils import cleanup_fork
                        owner = build.get('fork_info').get('owner')
                        repo = build.get('fork_info').get('repo')
                        if owner and repo:
                            cleanup_fork(owner, repo)
                            build['fork_cleaned'] = True
                            db.save_build(build)
                
                return jsonify({'status': 'success'})
                
            except Exception as e:
                logging.error(f"Error processing build result: {str(e)}")
                update_build_status(
                    build_id, 
                    'failed', 
                    f"Error processing build result: {str(e)}",
                    datetime.now().isoformat()
                )
                return jsonify({'error': f'Error processing build: {str(e)}'}), 500
        
        # Handle failure
        elif status == 'failed':
            error = data.get('error', 'Unknown error')
            update_build_status(
                build_id, 
                'failed', 
                f"Build failed: {error}",
                datetime.now().isoformat()
            )
            
            # Clean up GitHub fork
            if build.get('fork_info'):
                from utils.github_utils import cleanup_fork
                owner = build.get('fork_info').get('owner')
                repo = build.get('fork_info').get('repo')
                if owner and repo:
                    cleanup_fork(owner, repo)
                    build['fork_cleaned'] = True
                    db.save_build(build)
            
            return jsonify({'status': 'failure recorded'})
            
        else:
            return jsonify({'error': 'Invalid status'}), 400
            
    except Exception as e:
        logging.error(f"Error in build_complete webhook: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500 