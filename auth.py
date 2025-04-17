from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
import database as db
from utils.decorators import admin_required, login_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.before_request
def load_logged_in_user():
    username = session.get('username')
    if username is None:
        g.user = None
    else:
        g.user = db.get_user(username)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = db.get_user(username)
        error = None
        
        if user is None:
            error = 'Invalid username or password'
        elif not check_password_hash(user['password'], password):
            error = 'Invalid username or password'
            
        if error is None:
            session.clear()
            session['username'] = username
            next_page = request.args.get('next', url_for('app.index'))
            return redirect(next_page)
            
        flash(error)
    
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    # Clear the session
    session.clear()
    flash('Successfully logged out')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
@admin_required
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        
        error = None
        
        if not username:
            error = 'Username is required'
        elif not password:
            error = 'Password is required'
        elif db.get_user(username) is not None:
            error = f'User {username} is already registered'
            
        if error is None:
            db.save_user({
                'username': username,
                'password': generate_password_hash(password),
                'role': role
            })
            flash(f'User {username} created with {role} role')
            return redirect(url_for('auth.manage_users'))
            
        flash(error)
    
    return render_template('register.html')

@auth_bp.route('/manage_users')
@admin_required
def manage_users():
    users = db.get_users()
    return render_template('manage_users.html', users=users)

@auth_bp.route('/delete_user/<username>', methods=['POST'])
@admin_required
def delete_user(username):
    if session.get('username') == username:
        flash('You cannot delete your own account')
        return redirect(url_for('auth.manage_users'))
        
    db.delete_user(username)
    flash(f'User {username} deleted')
    return redirect(url_for('auth.manage_users'))

@auth_bp.route('/account', methods=['GET'])
@login_required
def account_management():
    user = db.get_user(session.get('username'))
    if not user:
        flash('User not found')
        return redirect(url_for('app.index'))
        
    return render_template('account.html', user=user)

@auth_bp.route('/account/change-password', methods=['POST'])
@login_required
def change_password():
    user = db.get_user(session.get('username'))
    if not user:
        flash('User not found')
        return redirect(url_for('app.index'))
        
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Check current password
    if not check_password_hash(user['password'], current_password):
        flash('Current password is incorrect')
        return redirect(url_for('auth.account_management'))
        
    # Check new password
    if not new_password:
        flash('New password is required')
        return redirect(url_for('auth.account_management'))
        
    # Check password confirmation
    if new_password != confirm_password:
        flash('New passwords do not match')
        return redirect(url_for('auth.account_management'))
        
    # Update password
    db.update_user_password(user['username'], generate_password_hash(new_password))
    flash('Password updated successfully')
    return redirect(url_for('auth.account_management'))

@auth_bp.route('/account/profile-picture', methods=['POST'])
@login_required
def update_profile_picture():
    # Check if we have cropped image data
    cropped_image = request.form.get('cropped_image')
    
    if cropped_image and cropped_image.startswith('data:image'):
        # Process cropped image data (base64)
        try:
            from PIL import Image
            import io
            import base64
            
            # Extract the actual image data from the data URL
            image_format, image_data = cropped_image.split(';base64,')
            image_data = base64.b64decode(image_data)
            
            # Open image from binary data
            img = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if it's not
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            # Save as JPEG to a buffer
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85)
            output.seek(0)
            
            # Store in database
            db.update_user_profile_picture(
                session.get('username'),
                output.read(),
                'image/jpeg'
            )
            
            flash('Profile picture updated')
            return redirect(url_for('auth.account_management'))
        except Exception as e:
            flash(f'Error processing cropped image: {str(e)}')
            return redirect(url_for('auth.account_management'))
    
    # Fallback to direct file processing if no cropped data
    if 'profile_picture' not in request.files:
        flash('No file part')
        return redirect(url_for('auth.account_management'))
        
    file = request.files['profile_picture']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('auth.account_management'))
        
    if file:
        # Process and store the image
        try:
            from PIL import Image
            import io
            
            # Read uploaded image
            img_data = file.read()
            img = Image.open(io.BytesIO(img_data))
            
            # Resize to a standard size if needed
            max_size = (256, 256)
            img.thumbnail(max_size)
            
            # Convert to RGB if it's not
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            # Save as JPEG to a buffer
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85)
            output.seek(0)
            
            # Store in database
            db.update_user_profile_picture(
                session.get('username'),
                output.read(),
                'image/jpeg'
            )
            
            flash('Profile picture updated')
        except Exception as e:
            flash(f'Error processing image: {str(e)}')
            
    return redirect(url_for('auth.account_management'))

@auth_bp.route('/user/<username>/profile-picture')
def user_profile_picture(username):
    from flask import send_file, abort
    import io
    
    picture = db.get_user_profile_picture(username)
    if not picture:
        # Return default image
        try:
            return send_file('defaultProf.jpg', mimetype='image/jpeg')
        except:
            abort(404)
    
    # Return from database
    return send_file(
        io.BytesIO(picture['data']),
        mimetype=picture['content_type'],
        download_name=f"{username}_profile.jpg"
    ) 