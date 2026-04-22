from flask import Flask, render_template, redirect, url_for, session, request, flash, current_app
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_session import Session
from config import Config
import os
from datetime import datetime

# Initialize database and security extensions
mysql = MySQL()
bcrypt = Bcrypt()
sess = Session()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions with app
    mysql.init_app(app)
    bcrypt.init_app(app)
    sess.init_app(app)

    # Import and register blueprints
    from routes.auth import auth_bp
    from routes.user import user_bp
    from routes.admin import admin_bp
    from routes.guide import guide_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(guide_bp, url_prefix='/guide')

    @app.route('/')
    def index():
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM travel_packages WHERE available_slots > 0 AND booking_end_date > %s AND is_active = TRUE ORDER BY id DESC LIMIT 6", (datetime.now(),))
        packages = cursor.fetchall()
        cursor.close()
        return render_template('index.html', packages=packages)

    @app.route('/packages')
    def packages():
        cursor = mysql.connection.cursor()
        
        sort_by = request.args.get('sort', 'recent')
        search_query = request.args.get('search', '').strip()
        
        order_clause = "ORDER BY id DESC"
        if sort_by == 'price_low':
            order_clause = "ORDER BY price ASC"
        elif sort_by == 'price_high':
            order_clause = "ORDER BY price DESC"
            
        query = "SELECT * FROM travel_packages WHERE available_slots > 0 AND booking_end_date > %s AND is_active = TRUE"
        params = [datetime.now()]
        
        if search_query:
            query += " AND (title LIKE %s OR destination LIKE %s)"
            params.extend([f"%{search_query}%", f"%{search_query}%"])
            
        query += " " + order_clause
        
        cursor.execute(query, tuple(params))
        available_packages = cursor.fetchall()
        cursor.close()
        
        if 'user_id' in session:
            return render_template('user/explore.html', packages=available_packages)
        return render_template('packages.html', packages=available_packages)

    @app.route('/about')
    def about():
        return render_template('about.html')

    @app.route('/contact', methods=['GET', 'POST'])
    def contact():
        if request.method == 'POST':
            # Collect form data (for future use or logging)
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            email = request.form.get('email')
            subject = request.form.get('subject')
            message = request.form.get('message')
            
            # Here you would typically save to DB or send an email
            # For now, we'll just show a success message
            flash('Your message has been sent successfully! We will get back to you soon.', 'success')
            return redirect(url_for('contact', success=1))
            
        return render_template('contact.html')

    # Custom context processor for session checks and utilities
    @app.context_processor
    def inject_helpers():
        current_user = None
        if 'user_id' in session:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT id, full_name, email, phone, traveler_id FROM users WHERE id = %s", (session['user_id'],))
            row = cursor.fetchone()
            cursor.close()
            if row:
                current_user = row
                pic_path = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles', f"user_{session['user_id']}.jpg")
                if os.path.exists(pic_path):
                    current_user['profile_pic'] = f"/static/uploads/profiles/user_{session['user_id']}.jpg?t={int(os.path.getmtime(pic_path))}"
                else:
                    current_user['profile_pic'] = f"https://ui-avatars.com/api/?name={row['full_name']}&background=334155&color=fff&size=128"
                    
        return dict(
            is_logged_in='user_id' in session,
            is_admin='admin_id' in session,
            is_guide='guide_id' in session,
            username=session.get('username') or session.get('guide_name'),
            now_date=lambda: datetime.now(),
            current_user=current_user
        )

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
