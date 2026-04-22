from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import mysql, bcrypt
from utils.security import generate_traveler_id, hash_password, check_password
from utils.email_service import send_otp_email, send_smtp_email
from utils.otp_service import generate_otp, save_otp, verify_otp, mark_user_verified
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('auth.register'))

        cursor = mysql.connection.cursor()
        
        # Check if email exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("Email already exists!", "warning")
            return redirect(url_for('auth.register'))

        # Generate unique Traveler ID and Hash password
        traveler_id = generate_traveler_id()
        hashed_pwd = hash_password(password)

        cursor.execute("INSERT INTO users (traveler_id, full_name, email, phone, password_hash, is_verified) VALUES (%s, %s, %s, %s, %s, TRUE)",
                       (traveler_id, full_name, email, phone, hashed_pwd))
        mysql.connection.commit()
        
        user_id = cursor.lastrowid
        
        flash("Registration successful! You can now login.", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'pending_user_id' not in session:
        return redirect(url_for('auth.register'))
    
    if request.method == 'POST':
        otp_input = request.form.get('otp')
        user_id = session['pending_user_id']
        
        if verify_otp(user_id, otp_input, mysql):
            mark_user_verified(user_id, mysql)
            session.pop('pending_user_id')
            session.pop('pending_user_email')
            flash("Email verified successfully! You can now login.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash("Invalid or expired OTP!", "danger")
    
    return render_template('auth/verify.html', email=session.get('pending_user_email'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user and check_password(user['password_hash'], password):
            session['user_id'] = user['id']
            session['traveler_id'] = user['traveler_id']
            session['username'] = user['full_name']
            session['role'] = 'user'
            flash(f"Welcome back, {user['full_name']}!", "success")
            return redirect(url_for('user.dashboard'))
        else:
            flash("Invalid email or password!", "danger")
            
    return render_template('auth/login.html')

@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM admin WHERE username = %s", (username,))
        admin = cursor.fetchone()
        
        # Hardcoded for initial setup if not hashed in SQL
        if admin and (admin['password_hash'] == password or check_password(admin['password_hash'], password)):
            session['admin_id'] = admin['id']
            session['username'] = admin['username']
            session['role'] = 'admin'
            flash("Admin Login Successful!", "success")
            return redirect(url_for('admin.dashboard'))
        else:
            flash("Invalid Admin Credentials!", "danger")
    
    return render_template('auth/admin_login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Successfully logged out.", "info")
    return redirect(url_for('index'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, full_name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user:
            otp = generate_otp()
            save_otp(user['id'], otp, mysql)
            
            if send_otp_email(email, otp):
                session['reset_user_id'] = user['id']
                session['reset_user_email'] = email
                flash("A reset OTP has been sent to your email.", "success")
                return redirect(url_for('auth.reset_password'))
            else:
                flash("Failed to send reset email. Please try again.", "danger")
        else:
            flash("Email not found in our records.", "warning")
            
    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_user_id' not in session:
        flash("Unauthorized access!", "danger")
        return redirect(url_for('auth.forgot_password'))
    
    # Capture email for display
    email = session.get('reset_user_email')
    
    if request.method == 'POST':
        otp_input = request.form.get('otp')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        user_id = session['reset_user_id']
        
        if new_password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('auth.reset_password'))
            
        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "warning")
            return redirect(url_for('auth.reset_password'))

        if verify_otp(user_id, otp_input, mysql):
            hashed_pwd = hash_password(new_password)
            cursor = mysql.connection.cursor()
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (hashed_pwd, user_id))
            mysql.connection.commit()
            
            # Clear sessions
            session.pop('reset_user_id', None)
            session.pop('reset_user_email', None)
            
            flash("Password has been reset successfully! You can now login.", "success")
            return redirect(url_for('auth.login'))
        else:
            flash("Invalid or expired OTP!", "danger")
            
    return render_template('auth/reset_password.html', email=email)
