from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import mysql, bcrypt
from utils.security import hash_password, check_password

guide_bp = Blueprint('guide', __name__)

@guide_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        experience = request.form.get('experience')
        bio = request.form.get('bio')

        cursor = mysql.connection.cursor()
        
        # Check if email exists
        cursor.execute("SELECT * FROM guides WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("Email already registered!", "warning")
            return redirect(url_for('guide.register'))

        hashed_pwd = hash_password(password)

        cursor.execute("INSERT INTO guides (full_name, email, phone, password_hash, experience, bio, is_approved) VALUES (%s, %s, %s, %s, %s, %s, FALSE)",
                       (full_name, email, phone, hashed_pwd, experience, bio))
        mysql.connection.commit()
        cursor.close()
        
        flash("Application submitted successfully! Our admins will review your profile.", "success")
        return redirect(url_for('guide.login'))

    return render_template('auth/guide_register.html')

@guide_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM guides WHERE email = %s", (email,))
        guide = cursor.fetchone()
        
        if guide and check_password(guide['password_hash'], password):
            session['guide_id'] = guide['id']
            session['guide_name'] = guide['full_name']
            session['role'] = 'guide'
            flash(f"Welcome to your Guide Portal, {guide['full_name']}!", "success")
            return redirect(url_for('guide.dashboard'))
        else:
            flash("Invalid email or password!", "danger")
            
    return render_template('auth/guide_login.html')

@guide_bp.route('/dashboard')
def dashboard():
    if session.get('role') != 'guide':
        flash("Please login as a guide first.", "danger")
        return redirect(url_for('guide.login'))
        
    guide_id = session['guide_id']
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM guides WHERE id = %s", (guide_id,))
    guide = cursor.fetchone()
    
    cursor.execute("SELECT * FROM guide_feedback WHERE guide_id = %s ORDER BY created_at DESC", (guide_id,))
    feedbacks = cursor.fetchall()
    
    # Quick Stats
    cursor.execute("SELECT COUNT(*) as times_hired FROM bookings WHERE guide_id = %s AND status = 'confirmed'", (guide_id,))
    times_hired = cursor.fetchone()['times_hired'] or 0
    
    guide_rate = guide.get('daily_rate', 0)
    total_earnings = times_hired * float(guide_rate) if guide_rate else 0
    
    # Assigned Bookings
    cursor.execute("""
        SELECT bookings.booking_id, bookings.booking_date, 
               travel_packages.title AS package_title, travel_packages.duration,
               users.full_name AS user_name, users.email AS user_email, users.phone AS user_phone
        FROM bookings
        JOIN travel_packages ON bookings.package_id = travel_packages.id
        JOIN users ON bookings.user_id = users.id
        WHERE bookings.guide_id = %s AND bookings.status = 'confirmed'
        ORDER BY bookings.booking_date DESC
    """, (guide_id,))
    assigned_bookings = cursor.fetchall()
    
    cursor.close()
    
    return render_template('guide/dashboard.html', guide=guide, feedbacks=feedbacks, times_hired=times_hired, total_earnings=total_earnings, assigned_bookings=assigned_bookings)

@guide_bp.route('/update_profile', methods=['POST'])
def update_profile():
    if session.get('role') != 'guide':
        return redirect(url_for('guide.login'))
        
    experience = request.form.get('experience')
    bio = request.form.get('bio')
    daily_rate = request.form.get('daily_rate', 0)
    guide_id = session['guide_id']
    
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE guides SET experience = %s, bio = %s, daily_rate = %s WHERE id = %s", (experience, bio, daily_rate, guide_id))
    mysql.connection.commit()
    cursor.close()
    
    flash("Profile updated successfully!", "success")
    return redirect(url_for('guide.dashboard'))

@guide_bp.route('/profile/<int:guide_id>')
def profile(guide_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM guides WHERE id = %s", (guide_id,))
    guide = cursor.fetchone()
    cursor.close()
    
    if not guide:
        flash("Guide not found.", "danger")
        return redirect(url_for('index'))
        
    return render_template('guide/profile.html', guide=guide)

# Public route to leave feedback
@guide_bp.route('/feedback/<int:guide_id>', methods=['POST'])
def submit_feedback(guide_id):
    user_name = session.get('username') or request.form.get('user_name') or 'Anonymous Traveler'
    text = request.form.get('feedback_text')
    rating = request.form.get('rating')
    
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO guide_feedback (guide_id, user_name, feedback_text, rating) VALUES (%s, %s, %s, %s)",
                   (guide_id, user_name, text, rating))
    mysql.connection.commit()
    cursor.close()
    
    flash("Thank you for your feedback!", "success")
    # Normally we would redirect back to the guide's public profile page,
    # but for now, if they are logged in, dashboard... else home.
    return redirect(request.referrer or url_for('index'))
