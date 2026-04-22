from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from app import mysql
from utils.decorators import admin_required
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    cursor = mysql.connection.cursor()
    
    # Stats for the dashboard
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM travel_packages")
    total_packages = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM bookings")
    total_bookings = cursor.fetchone()['count']
    
    cursor.execute("SELECT SUM(price) as revenue FROM bookings JOIN travel_packages ON bookings.package_id = travel_packages.id WHERE status = 'confirmed'")
    total_revenue = cursor.fetchone()['revenue'] or 0
    
    # Real-time Stats for Chart.js
    cursor.execute("SELECT status, COUNT(*) as count FROM bookings GROUP BY status")
    booking_stats = cursor.fetchall()
    
    cursor.execute("SELECT SUM(total_slots) as total, SUM(available_slots) as available FROM travel_packages")
    slots = cursor.fetchone()
    system_total_slots = slots['total'] or 0
    system_available_slots = slots['available'] or 0
    
    # Date Range Filter
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')
    
    if from_date and to_date:
        date_filter_query = "AND DATE(bookings.booking_date) BETWEEN %s AND %s"
        params = (from_date, to_date)
        
        # Group by day
        cursor.execute("SELECT DATE_FORMAT(bookings.booking_date, '%%Y-%%m-%%d') AS label, COUNT(*) AS total_bookings, SUM(travel_packages.price) AS revenue FROM bookings JOIN travel_packages ON bookings.package_id = travel_packages.id WHERE bookings.status = 'confirmed' " + date_filter_query + " GROUP BY label ORDER BY label ASC", params)
        monthly_sales = list(cursor.fetchall())
        
        top_pkg_q = "SELECT travel_packages.title, COUNT(*) as bookings, SUM(travel_packages.price) as revenue FROM bookings JOIN travel_packages ON bookings.package_id = travel_packages.id WHERE bookings.status = 'confirmed' " + date_filter_query + " GROUP BY travel_packages.id ORDER BY bookings DESC LIMIT 3"
        cursor.execute(top_pkg_q, params)
        top_packages_period = cursor.fetchall()
    else:
        # Default to last 12 months
        cursor.execute("SELECT DATE_FORMAT(bookings.booking_date, '%%Y-%%m') AS label, COUNT(*) AS total_bookings, SUM(travel_packages.price) AS revenue FROM bookings JOIN travel_packages ON bookings.package_id = travel_packages.id WHERE bookings.status = 'confirmed' GROUP BY label ORDER BY label DESC LIMIT 12")
        monthly_sales = list(cursor.fetchall())
        monthly_sales.reverse()  # chronological order
        
        top_pkg_q = "SELECT travel_packages.title, COUNT(*) as bookings, SUM(travel_packages.price) as revenue FROM bookings JOIN travel_packages ON bookings.package_id = travel_packages.id WHERE bookings.status = 'confirmed' GROUP BY travel_packages.id ORDER BY bookings DESC LIMIT 3"
        cursor.execute(top_pkg_q)
        top_packages_period = cursor.fetchall()
    
    # Cancelled bookings revenue (lost)
    cursor.execute("SELECT SUM(price) as lost FROM bookings JOIN travel_packages ON bookings.package_id = travel_packages.id WHERE status = 'cancelled'")
    lost_revenue = cursor.fetchone()['lost'] or 0
    
    # Pending bookings revenue
    cursor.execute("SELECT SUM(price) as pending FROM bookings JOIN travel_packages ON bookings.package_id = travel_packages.id WHERE status = 'pending'")
    pending_revenue = cursor.fetchone()['pending'] or 0
    
    # Pending guides
    cursor.execute("SELECT id, full_name, email, created_at FROM guides WHERE is_approved = FALSE ORDER BY created_at ASC")
    pending_guides = cursor.fetchall()
    
    # Active guides count
    cursor.execute("SELECT COUNT(*) as count FROM guides WHERE is_approved = TRUE")
    active_guides = cursor.fetchone()['count']
    
    cursor.close()
    return render_template('admin/dashboard.html', 
                          total_users=total_users, 
                          total_packages=total_packages, 
                          total_bookings=total_bookings, 
                          total_revenue=total_revenue,
                          booking_stats=booking_stats,
                          system_total_slots=system_total_slots,
                          system_available_slots=system_available_slots,
                          monthly_sales=monthly_sales,
                          lost_revenue=lost_revenue,
                          pending_revenue=pending_revenue,
                          active_guides=active_guides,
                          from_date=from_date,
                          to_date=to_date,
                          top_packages_period=top_packages_period,
                          pending_guides=pending_guides)

@admin_bp.route('/monthly-report')
@admin_required
def monthly_report():
    cursor = mysql.connection.cursor()
    
    # Current month stats
    cursor.execute("""
        SELECT COUNT(*) as total_bookings,
               SUM(travel_packages.price) as total_revenue
        FROM bookings
        JOIN travel_packages ON bookings.package_id = travel_packages.id
        WHERE bookings.status = 'confirmed'
        AND MONTH(bookings.booking_date) = MONTH(CURDATE())
        AND YEAR(bookings.booking_date) = YEAR(CURDATE())
    """)
    current = cursor.fetchone()
    
    cursor.execute("""
        SELECT COUNT(*) as cancelled
        FROM bookings
        WHERE status = 'cancelled'
        AND MONTH(booking_date) = MONTH(CURDATE())
        AND YEAR(booking_date) = YEAR(CURDATE())
    """)
    cancelled = cursor.fetchone()['cancelled']
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE MONTH(created_at) = MONTH(CURDATE()) AND YEAR(created_at) = YEAR(CURDATE())")
    new_users = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM guides WHERE is_approved = TRUE")
    active_guides = cursor.fetchone()['count']
    
    # Top 5 packages this month
    cursor.execute("""
        SELECT travel_packages.title, travel_packages.destination, COUNT(*) as bookings, SUM(travel_packages.price) as revenue
        FROM bookings
        JOIN travel_packages ON bookings.package_id = travel_packages.id
        WHERE bookings.status = 'confirmed'
        AND MONTH(bookings.booking_date) = MONTH(CURDATE())
        AND YEAR(bookings.booking_date) = YEAR(CURDATE())
        GROUP BY bookings.package_id
        ORDER BY bookings DESC
        LIMIT 5
    """)
    top_packages = cursor.fetchall()
    
    cursor.close()
    return render_template('admin/monthly_report.html',
                          current_bookings=current['total_bookings'] or 0,
                          current_revenue=current['total_revenue'] or 0,
                          cancelled=cancelled,
                          new_users=new_users,
                          active_guides=active_guides,
                          top_packages=top_packages)

@admin_bp.route('/packages')
@admin_required
def manage_packages():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM travel_packages")
    packages = cursor.fetchall()
    cursor.close()
    return render_template('admin/packages.html', packages=packages)

@admin_bp.route('/package/add', methods=['GET', 'POST'])
@admin_required
def add_package():
    if request.method == 'POST':
        title = request.form.get('title')
        destination = request.form.get('destination')
        price = request.form.get('price')
        duration = request.form.get('duration')
        total_slots = request.form.get('total_slots')
        image_url = request.form.get('image_url')
        description = request.form.get('description')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')

        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO travel_packages 
            (title, destination, price, duration, total_slots, available_slots, image_url, description, booking_start_date, booking_end_date) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (title, destination, price, duration, total_slots, total_slots, image_url, description, start_date, end_date))
        mysql.connection.commit()
        cursor.close()
        
        flash("Travel Package added successfully!", "success")
        return redirect(url_for('admin.manage_packages'))
        
    return render_template('admin/add_package.html')

@admin_bp.route('/package/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_package(id):
    cursor = mysql.connection.cursor()
    if request.method == 'POST':
        # (similar to add logic but with UPDATE)
        title = request.form.get('title')
        destination = request.form.get('destination')
        # ... and other fields ...
        cursor.execute("UPDATE travel_packages SET title=%s, destination=%s, price=%s, duration=%s, total_slots=%s, available_slots=%s, image_url=%s, description=%s, booking_start_date=%s, booking_end_date=%s WHERE id=%s",
                      (title, destination, request.form.get('price'), request.form.get('duration'), request.form.get('total_slots'), request.form.get('available_slots'), request.form.get('image_url'), request.form.get('description'), request.form.get('start_date'), request.form.get('end_date'), id))
        mysql.connection.commit()
        cursor.close()
        flash("Package updated!", "success")
        return redirect(url_for('admin.manage_packages'))
    
    cursor.execute("SELECT * FROM travel_packages WHERE id = %s", (id,))
    package = cursor.fetchone()
    cursor.close()
    return render_template('admin/edit_package.html', package=package)

@admin_bp.route('/package/delete/<int:id>')
@admin_required
def delete_package(id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM travel_packages WHERE id = %s", (id,))
    mysql.connection.commit()
    cursor.close()
    flash("Package deleted successfully.", "info")
    return redirect(url_for('admin.manage_packages'))

@admin_bp.route('/bookings')
@admin_required
def manage_bookings():
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT bookings.*, users.full_name, users.traveler_id, travel_packages.title 
        FROM bookings 
        JOIN users ON bookings.user_id = users.id 
        JOIN travel_packages ON bookings.package_id = travel_packages.id
        ORDER BY booking_date DESC
    """)
    bookings = cursor.fetchall()
    cursor.close()
    return render_template('admin/bookings.html', bookings=bookings)

@admin_bp.route('/booking/update-status/<int:id>/<string:status>')
@admin_required
def update_booking_status(id, status):
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE bookings SET status = %s WHERE id = %s", (status, id))
    mysql.connection.commit()
    
    if status == 'confirmed':
        cursor.execute("""
            SELECT b.booking_id, u.email, u.full_name, u.phone, p.title 
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN travel_packages p ON b.package_id = p.id
            WHERE b.id = %s
        """, (id,))
        booking_data = cursor.fetchone()
        
        if booking_data:
            from utils.email_service import send_booking_confirmation
            send_booking_confirmation(booking_data['email'], booking_data['full_name'], booking_data['title'], booking_data['booking_id'])
            
            try:
                from utils.sms_service import send_booking_sms
                send_booking_sms(booking_data['phone'], booking_data['full_name'], booking_data['title'], booking_data['booking_id'])
            except ImportError:
                pass
                
    cursor.close()
    flash(f"Booking status updated to {status}!", "success")
    return redirect(url_for('admin.manage_bookings'))

@admin_bp.route('/users')
@admin_required
def manage_users():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, traveler_id, full_name, email, phone, is_verified, created_at FROM users ORDER BY created_at DESC")
    users = cursor.fetchall()
    cursor.close()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/user/delete/<int:id>')
@admin_required
def delete_user(id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (id,))
    mysql.connection.commit()
    cursor.close()
    flash("Traveler account removed.", "info")
    return redirect(url_for('admin.manage_users'))

@admin_bp.route('/guides')
@admin_required
def manage_guides():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM guides ORDER BY created_at DESC")
    guides = cursor.fetchall()
    cursor.close()
    return render_template('admin/guides.html', guides=guides)

@admin_bp.route('/guide/approve/<int:id>')
@admin_required
def approve_guide(id):
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE guides SET is_approved = TRUE WHERE id = %s", (id,))
    mysql.connection.commit()
    cursor.close()
    flash("Guide application approved!", "success")
    return redirect(url_for('admin.manage_guides'))

@admin_bp.route('/guide/reject/<int:id>')
@admin_required
def reject_guide(id):
    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM guides WHERE id = %s", (id,))
    mysql.connection.commit()
    cursor.close()
    flash("Guide application rejected and removed.", "info")
    return redirect(url_for('admin.manage_guides'))

@admin_bp.route('/feedback')
@admin_required
def manage_feedback():
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT website_feedback.*, users.full_name, users.traveler_id, users.email
        FROM website_feedback
        JOIN users ON website_feedback.user_id = users.id
        ORDER BY created_at DESC
    """)
    feedbacks = cursor.fetchall()
    cursor.close()
    return render_template('admin/feedback.html', feedbacks=feedbacks)

@admin_bp.route('/feedback/update/<int:id>/<string:status>')
@admin_required
def update_feedback_status(id, status):
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE website_feedback SET status = %s WHERE id = %s", (status, id))
    mysql.connection.commit()
    cursor.close()
    flash(f"Feedback marked as {status}.", "success")
    return redirect(url_for('admin.manage_feedback'))
