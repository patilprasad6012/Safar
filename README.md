# Safar Management System

A clean, secure, and user-friendly Full-Stack Travel Management Web Application built for the final year BCA project.

## 🚀 Features

### 👤 User Features
- **Modern Registration & Login**: Secure account creation with unique Traveler ID.
- **OTP Verification**: Email-based OTP for account activation and security.
- **Simple Tour Catalog**: Browse curated travel packages with clean, minimalist cards.
- **Real-time Booking**: Instant booking with seat availability checks.
- **Booking History**: Manage reservations and download status updates.
- **Responsive UI**: Fully mobile-responsive design with light-themed aesthetics.

### 🛠️ Admin Features
- **Secure Control Panel**: Protected admin dashboard with master credentials.
- **Live Analytics**: Visualized booking stats using Chart.js.
- **Full CRUD Management**: Add, Update, and Delete travel packages with image support.
- **User Management**: Oversee registered travelers and monitor activities.
- **Booking Control**: Approve, pending, or cancel traveler reservations.
- **Slot Tracking**: Real-time monitoring of available vs total slots across the system.

## 🛡️ Security
- **Bcrypt Hashing**: All passwords are encrypted using strong Bcrypt salt.
- **Session Protection**: Role-based access control using Flask sessions and custom decorators.
- **Safe Queries**: SQL Injection prevention using parameterized queries.
- **Verification**: mandatory OTP verification for all new travelers.

## 💻 Tech Stack
- **Backend**: Python Flask
- **Database**: MySQL
- **Frontend**: HTML5, CSS3, JavaScript (Bootstrap 5 + Lucide Icons)
- **Visualization**: Chart.js

## ⚙️ Setup Instructions

### 1. Database Setup
- Install MySQL Server and create a database named `safar_db`.
- Import the provided `database.sql` file:
  ```bash
  mysql -u root -p safar_db < database.sql
  ```

### 2. Python Environment
- Clone the repository and navigate to the project folder.
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

### 3. Configuration
- Update `config.py` with your MySQL credentials (Host, User, Password).
- (Optional) Set up `.env` for production keys.

### 4. Run Application
- Start the Flask server:
  ```bash
  python app.py
  ```
- Visit `http://127.0.0.1:5000` in your browser.

## 📂 Project Structure
- `/models`: Database interaction logic.
- `/routes`: Flask Blueprints for Auth, Admin, and User features.
- `/static`: Professional CSS, JS, and image assets.
- `/templates`: Premium Jinja2 templates (Auth, Dashboard, Management).
- `/utils`: Security, OTP, and Email services.

---
**Developed with ❤️ for BCA Final Year Project**
