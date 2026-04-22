from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app import mysql
from utils.decorators import login_required
from utils.email_service import send_booking_confirmation
from utils.sms_service import send_booking_sms
import random
import string
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from flask import current_app

user_bp = Blueprint('user', __name__)

def generate_booking_id():
    return 'BK-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

@user_bp.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    cursor = mysql.connection.cursor()
    
    # User's bookings
    cursor.execute("""
        SELECT bookings.*, travel_packages.title, travel_packages.destination, travel_packages.price, travel_packages.image_url 
        FROM bookings 
        JOIN travel_packages ON bookings.package_id = travel_packages.id 
        WHERE user_id = %s 
        ORDER BY booking_date DESC
    """, (user_id,))
    my_bookings = cursor.fetchall()
    
    # Calculate stats with direct SQL for maximum precision
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) as confirmed,
            SUM(CASE WHEN LOWER(status) = 'pending' THEN 1 ELSE 0 END) as pending
        FROM bookings 
        WHERE user_id = %s
    """, (user_id,))
    stats = cursor.fetchone()
    
    total_bookings = stats['total'] if stats else 0
    confirmed_bookings = stats['confirmed'] if stats and stats['confirmed'] else 0
    pending_bookings = stats['pending'] if stats and stats['pending'] else 0
    
    # Sorting filter logic for Available Travel Packages
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
    return render_template('user/dashboard.html', 
                           bookings=my_bookings, 
                           packages=available_packages,
                           total_bookings=total_bookings,
                           confirmed_bookings=confirmed_bookings,
                           pending_bookings=pending_bookings)

@user_bp.route('/profile')
@login_required
def profile():
    user_id = session['user_id']
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, full_name, email, phone, traveler_id FROM users WHERE id = %s", (user_id,))
    user_data = cursor.fetchone()
    profile_pic = None
    pic_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
    pic_path = os.path.join(pic_dir, f'user_{user_id}.jpg')
    if os.path.exists(pic_path):
        profile_pic = f"/static/uploads/profiles/user_{user_id}.jpg?t={int(os.path.getmtime(pic_path))}"
        
    cursor.execute("SELECT COUNT(*) as count FROM bookings WHERE user_id = %s", (user_id,))
    total_bookings = cursor.fetchone()['count']
    
    cursor.execute("SELECT SUM(travel_packages.price) as total_spent FROM bookings JOIN travel_packages ON bookings.package_id = travel_packages.id WHERE bookings.user_id = %s AND bookings.status = 'confirmed'", (user_id,))
    total_spent_res = cursor.fetchone()
    total_spent = total_spent_res['total_spent'] if total_spent_res and total_spent_res['total_spent'] else 0
    
    cursor.close()
    # Calculate feedback submissions
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM website_feedback WHERE user_id = %s", (user_id,))
    res = cursor.fetchone()
    feedback_website_count = res['count'] if res else 0
    cursor.close()
    
    # Fetch guides hired by the user
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT guides.id, guides.full_name, guides.experience, guides.daily_rate
        FROM bookings
        JOIN guides ON bookings.guide_id = guides.id
        WHERE bookings.user_id = %s AND bookings.guide_id IS NOT NULL AND bookings.status = 'confirmed'
        GROUP BY guides.id, guides.full_name, guides.experience, guides.daily_rate
        ORDER BY MAX(bookings.booking_date) DESC
    """, (user_id,))
    hired_guides = cursor.fetchall()
    feedback_guide_count = len(hired_guides)
    cursor.close()

    return render_template('user/profile.html', user_data=user_data, profile_pic=profile_pic,
                           total_bookings=total_bookings, total_spent=total_spent,
                           feedback_guide_count=feedback_guide_count, feedback_website_count=feedback_website_count,
                           hired_guides=hired_guides)

@user_bp.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user_id = session['user_id']
    
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        
        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE users SET full_name = %s, phone = %s WHERE id = %s", (full_name, phone, user_id))
        mysql.connection.commit()
        cursor.close()
        
        # Update session username
        session['username'] = full_name
        flash("Profile updated successfully!", "success")
        return redirect(url_for('user.profile'))
        
    # GET request: fetch current data for the form
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, full_name, email, phone, traveler_id FROM users WHERE id = %s", (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    
    return render_template('user/edit_profile.html', user_data=user_data)

@user_bp.route('/upload_profile_picture', methods=['POST'])
@login_required
def upload_profile_picture():
    user_id = session['user_id']
    if 'profile_pic' not in request.files:
        flash("No file selected", "danger")
        return redirect(url_for('user.dashboard'))
        
    file = request.files['profile_pic']
    if file.filename == '':
        flash("No file selected", "danger")
        return redirect(url_for('user.dashboard'))
        
    if file:
        pic_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
        os.makedirs(pic_dir, exist_ok=True)
        file_path = os.path.join(pic_dir, f'user_{user_id}.jpg')
        file.save(file_path)
        flash("Profile picture updated!", "success")
        
    return redirect(url_for('user.profile'))

@user_bp.route('/api/edit_profile', methods=['POST'])
@login_required
def api_edit_profile():
    user_id = session['user_id']
    full_name = request.form.get('full_name')
    phone = request.form.get('phone')
    
    if not full_name:
        return {'status': 'error', 'message': 'Name is required'}, 400
        
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET full_name = %s, phone = %s WHERE id = %s", (full_name, phone, user_id))
    mysql.connection.commit()
    cursor.close()
    
    session['username'] = full_name
    return {'status': 'success', 'message': 'Profile updated!', 'full_name': full_name, 'phone': phone}

@user_bp.route('/api/upload_picture', methods=['POST'])
@login_required
def api_upload_picture():
    user_id = session['user_id']
    file = request.files.get('profile_pic')
    
    if file:
        pic_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
        os.makedirs(pic_dir, exist_ok=True)
        file_path = os.path.join(pic_dir, f'user_{user_id}.jpg')
        file.save(file_path)
        new_url = f"/static/uploads/profiles/user_{user_id}.jpg?t={int(datetime.now().timestamp())}"
        return {'status': 'success', 'url': new_url}
    return {'status': 'error', 'message': 'No file found'}, 400

@user_bp.route('/bookings')
@login_required
def my_bookings():
    user_id = session['user_id']
    cursor = mysql.connection.cursor()
    
    # Fetch all bookings with full package info
    cursor.execute("""
        SELECT bookings.*, 
               travel_packages.title, 
               travel_packages.destination, 
               travel_packages.price, 
               travel_packages.duration,
               travel_packages.image_url,
               travel_packages.description
        FROM bookings 
        JOIN travel_packages ON bookings.package_id = travel_packages.id 
        WHERE user_id = %s 
        ORDER BY booking_date DESC
    """, (user_id,))
    all_bookings = cursor.fetchall()
    cursor.close()
    
    return render_template('user/my_bookings.html', bookings=all_bookings)

@user_bp.route('/package/<int:id>')
@login_required
def package_details(id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM travel_packages WHERE id = %s", (id,))
    package = cursor.fetchone()
    cursor.close()
    
    if not package:
        flash("Package not found!", "danger")
        return redirect(url_for('user.dashboard'))
    
    # Check if booking is available
    is_available = package['available_slots'] > 0 and package['booking_start_date'] <= datetime.now() <= package['booking_end_date']
    
    return render_template('user/package_view.html', package=package, is_available=is_available)

@user_bp.route('/suggest_guide/<int:id>', methods=['POST'])
@login_required
def suggest_guide(id):
    special_requests = request.form.get('special_requests', '')
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM travel_packages WHERE id = %s", (id,))
    package = cursor.fetchone()
    
    # Fetch approved guides
    cursor.execute("SELECT * FROM guides WHERE is_approved = TRUE")
    guides = cursor.fetchall()
    cursor.close()
    
    if not package or package['available_slots'] <= 0:
        flash("Package unavailable for booking.", "danger")
        return redirect(url_for('user.dashboard'))
        
    return render_template('user/suggest_guide.html', package=package, guides=guides, special_requests=special_requests)

@user_bp.route('/payment/<int:id>', methods=['POST'])
@login_required
def payment(id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM travel_packages WHERE id = %s", (id,))
    package = cursor.fetchone()
    
    if not package or package['available_slots'] <= 0:
        cursor.close()
        flash("Package unavailable for booking.", "danger")
        return redirect(url_for('user.dashboard'))
        
    special_requests = request.form.get('special_requests', '')
    guide_id = request.form.get('guide_id')
    
    guide = None
    total_price = float(package['price'])
    
    if guide_id:
        cursor.execute("SELECT * FROM guides WHERE id = %s", (guide_id,))
        guide = cursor.fetchone()
        if guide:
            total_price += float(guide['daily_rate'])
            
    cursor.close()
    return render_template('user/payment.html', package=package, special_requests=special_requests, guide=guide, total_price=total_price)

@user_bp.route('/book/<int:id>', methods=['POST'])
@login_required
def book_package(id):
    user_id = session['user_id']
    cursor = mysql.connection.cursor()
    
    # 1. Check if package exists and has slots
    cursor.execute("SELECT * FROM travel_packages WHERE id = %s FOR UPDATE", (id,))
    package = cursor.fetchone()
    
    if not package or package['available_slots'] <= 0:
        flash("Sorry, this package is no longer available!", "danger")
        return redirect(url_for('user.dashboard'))

    # 2. Check if user already booked this package
    cursor.execute("SELECT * FROM bookings WHERE user_id = %s AND package_id = %s", (user_id, id))
    if cursor.fetchone():
        flash("You have already booked this package!", "warning")
        return redirect(url_for('user.dashboard'))

    # 3. Create booking
    guide_id = request.form.get('guide_id') or None
    booking_id = generate_booking_id()
    cursor.execute("INSERT INTO bookings (booking_id, user_id, package_id, status, guide_id) VALUES (%s, %s, %s, %s, %s)",
                   (booking_id, user_id, id, 'pending', guide_id))
    
    # 4. Update available slots
    cursor.execute("UPDATE travel_packages SET available_slots = available_slots - 1 WHERE id = %s", (id,))
    
    mysql.connection.commit()
    
    # 5. Email will be sent upon admin approval
    cursor.close()
    flash("Booking successful! It is currently pending approval. A confirmation message will be sent once approved by an admin.", "success")
    return redirect(url_for('user.dashboard'))

@user_bp.route('/cancel-booking/<int:id>')
@login_required
def cancel_booking(id):
    user_id = session['user_id']
    cursor = mysql.connection.cursor()
    
    # Check if booking exists and belongs to user
    cursor.execute("SELECT * FROM bookings WHERE id = %s AND user_id = %s", (id, user_id))
    booking = cursor.fetchone()
    
    if booking:
        package_id = booking['package_id']
        # Increment available slots
        cursor.execute("UPDATE travel_packages SET available_slots = available_slots + 1 WHERE id = %s", (package_id,))
        # Delete booking or Mark cancelled
        cursor.execute("DELETE FROM bookings WHERE id = %s", (id,))
        mysql.connection.commit()
        flash("Booking cancelled successfully.", "info")
    
    cursor.close()
    return redirect(url_for('user.dashboard'))

@user_bp.route('/ticket/<int:id>')
@login_required
def ticket(id):
    user_id = session['user_id']
    cursor = mysql.connection.cursor()
    
    # Verify booking belongs to user
    cursor.execute("""
        SELECT bookings.*, travel_packages.title, travel_packages.destination, travel_packages.duration, travel_packages.price, users.full_name, users.traveler_id
        FROM bookings 
        JOIN travel_packages ON bookings.package_id = travel_packages.id 
        JOIN users ON bookings.user_id = users.id
        WHERE bookings.id = %s AND user_id = %s
    """, (id, user_id))
    booking = cursor.fetchone()
    cursor.close()
    
    if not booking:
        flash("Ticket not found or unauthorized access.", "danger")
        return redirect(url_for('user.dashboard'))
        
    return render_template('user/ticket.html', booking=booking)

@user_bp.route('/submit_feedback', methods=['POST'])
@login_required
def submit_feedback():
    user_id = session['user_id']
    subject = request.form.get('subject')
    message = request.form.get('message')
    rating = request.form.get('rating', 5)
    
    if not subject or not message:
        flash('Subject and message are required.', 'danger')
        return redirect(url_for('user.profile'))
        
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO website_feedback (user_id, subject, message, rating) VALUES (%s, %s, %s, %s)",
                       (user_id, subject, message, rating))
        mysql.connection.commit()
        cursor.close()
        flash('Thank you! Your feedback has been sent to the admin platform.', 'success')
    except Exception as e:
        flash(f'An error occurred: {str(e)}', 'danger')
        
    return redirect(url_for('user.profile'))

@user_bp.route('/support', methods=['GET'])
@login_required
def support():
    return render_template('user/support.html')

@user_bp.route('/api/chatbot', methods=['POST'])
@login_required
def api_chatbot():
    user_input = request.json.get('message')
    if not user_input:
        return {'status': 'error', 'message': 'Empty message'}, 400
        
    try:
        import google.generativeai as genai
        # Try to get API key from config first
        api_key = current_app.config.get('GOOGLE_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if not api_key:
            return {'status': 'success', 'response': 'The AI service is not fully configured yet. Please ask the administrator to add GOOGLE_API_KEY to the environment variables or config files.'}
            
        genai.configure(api_key=api_key)
        # Using gemini-pro as it has the widest compatibility with various API keys
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""You are Safar AI Assistant, a fast and efficient travel support bot.

Your goal is to respond quickly with short, clear, and helpful answers.

Guidelines:
- Keep responses concise (3–5 lines max unless user asks for details)
- Avoid long introductions and unnecessary text
- Provide direct step-by-step answers when needed
- Use simple and clear language
- Prioritize speed over explanation depth
- If the query is common (like booking), give a quick summary first, then optional details

User query:
{user_input}"""
        
        response = model.generate_content(prompt)
        # Remove any unwanted markdown artifacts if necessary, but returning text is fine
        return {'status': 'success', 'response': response.text}
    except ImportError:
        return {'status': 'success', 'response': 'The "google-generativeai" package is missing. The administrator needs to install it.'}
    except Exception as e:
        error_msg = str(e)
        # Check if it's a 403/Blocked key error to provide a more helpful "Mock" fallback for testing
        if "403" in error_msg or "blocked" in error_msg.lower() or "leaked" in error_msg.lower():
            # Standard helpful responses for common travel queries when AI is down
            mock_responses = {
                "booking": "To book a package, browse our 'Explore' section, select your dream destination, and click 'Details & Book'. Once confirmed, you can track it in your dashboard.",
                "payment": "We currently support secure payments via credit/debit cards and UPI. You will be redirected to our secure payment gateway during the final booking step.",
                "guide": "You can choose a professional guide during the booking process. Guides are verified experts who will help make your journey unforgettable.",
                "cancel": "You can cancel any pending booking directly from your 'My Bookings' page. For confirmed bookings, please reach out via our contact form."
            }
            
            # Simple keyword matching for the mock response
            query = user_input.lower()
            response_text = "I'm currently in 'Offline Mode' due to a configuration issue with my AI brain. How can I help you with booking, payment, or finding a guide?"
            
            for key, val in mock_responses.items():
                if key in query:
                    response_text = val
                    break
            
            return {'status': 'success', 'response': f"[OFFLINE ASSISTANT]: {response_text}"}
            
        return {'status': 'error', 'message': f'AI Interaction Failed: {error_msg}'}, 500

@user_bp.route('/recommend', methods=['GET', 'POST'])
@login_required
def recommend():
    ai_response = None
    if request.method == 'POST':
        budget = request.form.get('budget', '')
        location = request.form.get('location', '')
        travel_type = request.form.get('travel_type', '')
        user_id = session.get('user_id')
        
        # Local import to prevent circular dependencies
        from models.package import get_available_packages_for_ai, get_user_history_for_ai
        
        history_data = get_user_history_for_ai(user_id)
        if history_data:
            history = ", ".join([f"{h['title']} ({h['destination']})" for h in history_data])
        else:
            history = "No previous bookings."
            
        packages_data = get_available_packages_for_ai()
        if packages_data:
            package_list = "\n".join([f"- Name: {p['title']} | Destination: {p['destination']} | Duration: {p['duration']} | Price: ₹{p['price']} | Desc: {p['description'][:100]}..." for p in packages_data])
        else:
            package_list = "No packages currently available."
            
        try:
            import google.generativeai as genai
            api_key = current_app.config.get('GOOGLE_API_KEY') or os.environ.get('GOOGLE_API_KEY')
            
            if not api_key:
                flash('The AI service is not fully configured yet.', 'warning')
            else:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-pro')
                
                prompt = f"""You are a travel recommendation assistant.

User details:
- Budget: {budget}
- Preferred location: {location}
- Travel type: {travel_type}
- Past bookings: {history}

Available packages:
{package_list}

Suggest the top 3 packages with reasons why they match the user. 
Important Formatting Rule: Use proper HTML markup (<h3>, <ul>, <li>, <strong>, <br>) instead of markdown. Never use ```html markdown code block syntax. Just return the raw HTML!"""
                
                response = model.generate_content(prompt)
                ai_response = response.text
                
                if ai_response.startswith('```html'):
                    ai_response = ai_response[7:-3].strip()
                elif ai_response.startswith('```'):
                    ai_response = ai_response[3:-3].strip()
                    
        except Exception as e:
            flash(f'An error occurred while fetching AI recommendations: {str(e)}', 'danger')
            
    return render_template('user/ai_recommendation.html', ai_response=ai_response)
