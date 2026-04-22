import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super-secret-key-12345'
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'localhost'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or 'root'
    MYSQL_DB = os.environ.get('MYSQL_DB') or 'safar_db'
    MYSQL_CURSORCLASS = 'DictCursor'
    
    # Session config
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    
    # Gmail SMTP Configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    
    # Enter your Gmail username and 16-character App Password below
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'mr.patil6012@gmail.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'qirwgaydtwqylzdt'

    # Google Gemini AI Config
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY') or 'AIzaSyBoXcP4bo_7w4K1ICIBVdzTyFIBVNer_Ec'
