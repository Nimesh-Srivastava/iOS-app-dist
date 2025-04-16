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

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page')
            return redirect(url_for('auth.login', next=request.url))
        
        user = db.get_user(session['username'])
        if not user or user['role'] != 'admin':
            flash('Admin privileges required')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function

def admin_or_developer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please log in to access this page')
            return redirect(url_for('auth.login'))
        
        user = db.get_user(session['username'])
        if not user or user['role'] not in ['admin', 'developer']:
            flash('Admin or developer privileges required')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function 