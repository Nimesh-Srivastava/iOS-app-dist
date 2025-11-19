from functools import wraps
from flask import session, redirect, url_for, flash, request

import database as db

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def primary_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page')
            return redirect(url_for('auth.login', next=request.url))
        
        user = db.get_user(session['username'])
        if not user or user.get('role') != 'primary_admin':
            flash('Primary admin privileges required')
            return redirect(url_for('app.index'))
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page')
            return redirect(url_for('auth.login', next=request.url))
        
        user = db.get_user(session['username'])
        if not user:
            flash('User not found')
            return redirect(url_for('app.index'))
        
        # Primary admin or org admin can access
        if user.get('role') == 'primary_admin' or user.get('org_role') == 'admin':
            return f(*args, **kwargs)
        
        flash('Admin privileges required')
        return redirect(url_for('app.index'))
    return decorated_function

def admin_or_developer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page')
            return redirect(url_for('auth.login'))
        
        user = db.get_user(session['username'])
        if not user:
            flash('User not found')
            return redirect(url_for('app.index'))
        
        # Primary admin, org admin, or org developer can access
        if (user.get('role') == 'primary_admin' or 
            user.get('org_role') in ['admin', 'developer']):
            return f(*args, **kwargs)
        
        flash('Admin or developer privileges required')
        return redirect(url_for('app.index'))
    return decorated_function 