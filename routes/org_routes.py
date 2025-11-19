from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import database as db
import uuid
from datetime import datetime
from utils.decorators import primary_admin_required, login_required

org_bp = Blueprint('org', __name__)

@org_bp.route('/organizations')
@primary_admin_required
def list_organizations():
    """List all organizations (primary admin only)"""
    organizations = db.get_organizations()
    # Get user count for each org
    for org in organizations:
        org['user_count'] = len(db.get_org_users(org['id']))
    return render_template('organizations.html', organizations=organizations)

@org_bp.route('/organizations/create', methods=['GET', 'POST'])
@primary_admin_required
def create_organization():
    """Create a new organization (primary admin only)"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        if not name:
            flash('Organization name is required')
            return redirect(request.url)
        
        # Check if org with same name exists
        existing_orgs = db.get_organizations()
        if any(org.get('name') == name for org in existing_orgs):
            flash('An organization with this name already exists')
            return redirect(request.url)
        
        # Create organization
        org_id = str(uuid.uuid4())
        org_data = {
            'id': org_id,
            'name': name,
            'description': description,
            'created_at': datetime.now().isoformat()
        }
        
        db.save_organization(org_data)
        flash(f'Organization {name} created successfully')
        return redirect(url_for('org.list_organizations'))
    
    return render_template('create_organization.html')

@org_bp.route('/organizations/<org_id>/edit', methods=['GET', 'POST'])
@primary_admin_required
def edit_organization(org_id):
    """Edit an organization (primary admin only)"""
    org = db.get_organization(org_id)
    if not org:
        flash('Organization not found')
        return redirect(url_for('org.list_organizations'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description', '')
        
        if not name:
            flash('Organization name is required')
            return redirect(request.url)
        
        # Check if another org with same name exists
        existing_orgs = db.get_organizations()
        if any(org.get('name') == name and org.get('id') != org_id for org in existing_orgs):
            flash('An organization with this name already exists')
            return redirect(request.url)
        
        # Update organization
        org['name'] = name
        org['description'] = description
        db.save_organization(org)
        flash(f'Organization {name} updated successfully')
        return redirect(url_for('org.list_organizations'))
    
    return render_template('edit_organization.html', org=org)

@org_bp.route('/organizations/<org_id>/delete', methods=['POST'])
@primary_admin_required
def delete_organization(org_id):
    """Delete an organization (primary admin only)"""
    org = db.get_organization(org_id)
    if not org:
        flash('Organization not found')
        return redirect(url_for('org.list_organizations'))
    
    db.delete_organization(org_id)
    flash(f'Organization {org.get("name")} deleted successfully')
    return redirect(url_for('org.list_organizations'))

@org_bp.route('/organizations/<org_id>/users')
@primary_admin_required
def manage_org_users(org_id):
    """Manage users in an organization (primary admin only)"""
    org = db.get_organization(org_id)
    if not org:
        flash('Organization not found')
        return redirect(url_for('org.list_organizations'))
    
    org_users = db.get_org_users(org_id)
    all_users = db.get_users()  # Get all users (primary admin can see all)
    
    # Separate users by whether they're in this org
    users_in_org = []
    users_not_in_org = []
    
    org_usernames = {u['username'] for u in org_users}
    
    for user in all_users:
        # Skip primary admin
        if user.get('role') == 'primary_admin':
            continue
        
        if user['username'] in org_usernames:
            users_in_org.append(user)
        else:
            users_not_in_org.append(user)
    
    return render_template('manage_org_users.html', 
                         org=org, 
                         users_in_org=users_in_org,
                         users_not_in_org=users_not_in_org)

@org_bp.route('/organizations/<org_id>/users/add', methods=['POST'])
@primary_admin_required
def add_user_to_org(org_id):
    """Add a user to an organization (primary admin only)"""
    org = db.get_organization(org_id)
    if not org:
        flash('Organization not found')
        return redirect(url_for('org.list_organizations'))
    
    username = request.form.get('username')
    org_role = request.form.get('org_role')  # admin, developer, tester
    
    if not username or not org_role:
        flash('Username and role are required')
        return redirect(url_for('org.manage_org_users', org_id=org_id))
    
    user = db.get_user(username)
    if not user:
        flash('User not found')
        return redirect(url_for('org.manage_org_users', org_id=org_id))
    
    # Check if user is primary admin
    if user.get('role') == 'primary_admin':
        flash('Cannot add primary admin to an organization')
        return redirect(url_for('org.manage_org_users', org_id=org_id))
    
    # Check if user is already in another org
    if user.get('org_id') and user.get('org_id') != org_id:
        flash(f'User is already in another organization')
        return redirect(url_for('org.manage_org_users', org_id=org_id))
    
    # Add user to org
    user['org_id'] = org_id
    user['org_role'] = org_role
    db.save_user(user)
    
    flash(f'User {username} added to organization as {org_role}')
    return redirect(url_for('org.manage_org_users', org_id=org_id))

@org_bp.route('/organizations/<org_id>/users/<username>/update_role', methods=['POST'])
@primary_admin_required
def update_user_role(org_id, username):
    """Update a user's role in an organization (primary admin only)"""
    org = db.get_organization(org_id)
    if not org:
        flash('Organization not found')
        return redirect(url_for('org.list_organizations'))
    
    user = db.get_user(username)
    if not user or user.get('org_id') != org_id:
        flash('User not found in this organization')
        return redirect(url_for('org.manage_org_users', org_id=org_id))
    
    new_role = request.form.get('org_role')
    if not new_role:
        flash('Role is required')
        return redirect(url_for('org.manage_org_users', org_id=org_id))
    
    user['org_role'] = new_role
    db.save_user(user)
    
    flash(f'User {username} role updated to {new_role}')
    return redirect(url_for('org.manage_org_users', org_id=org_id))

@org_bp.route('/organizations/<org_id>/users/<username>/remove', methods=['POST'])
@primary_admin_required
def remove_user_from_org(org_id, username):
    """Remove a user from an organization (primary admin only)"""
    org = db.get_organization(org_id)
    if not org:
        flash('Organization not found')
        return redirect(url_for('org.list_organizations'))
    
    user = db.get_user(username)
    if not user or user.get('org_id') != org_id:
        flash('User not found in this organization')
        return redirect(url_for('org.manage_org_users', org_id=org_id))
    
    # Remove user from org
    user['org_id'] = None
    user['org_role'] = None
    db.save_user(user)
    
    flash(f'User {username} removed from organization')
    return redirect(url_for('org.manage_org_users', org_id=org_id))

