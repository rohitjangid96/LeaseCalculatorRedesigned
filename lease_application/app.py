"""
Simplified Lease Management Application
Login, Signup, and Blank Home Screen
"""

from flask import Flask, render_template, redirect, session
from flask_cors import CORS
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Import configuration
from lease_application.config import Config, config

# Import blueprints
from lease_application.auth import auth_bp
from lease_application.auth.auth import require_login, require_admin
from lease_application.api import api_bp
from lease_application.pdf_upload_backend import pdf_bp
from lease_application.calculate_backend import calc_bp
from lease_application.lease_management import copy_lease

# Import database
from lease_application import database


def setup_logging(log_dir: Path):
    """Setup application logging"""
    log_dir.mkdir(exist_ok=True)
    
    log_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation
    log_file = log_dir / 'lease_app.log'
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=Config.LOG_MAX_BYTES, 
        backupCount=Config.LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Suppress noisy pdfminer DEBUG logs
    pdfminer_loggers = [
        'pdfminer.cmapdb',
        'pdfminer.psparser',
        'pdfminer.pdfparser',
        'pdfminer.pdfinterp',
        'pdfminer.converter',
        'pdfminer.layout',
    ]
    for logger_name in pdfminer_loggers:
        pdfminer_logger = logging.getLogger(logger_name)
        pdfminer_logger.setLevel(logging.WARNING)  # Only show WARNING and above
    
    return root_logger


def create_app(config_name=None):
    """Application factory pattern"""
    app = Flask(__name__,
                template_folder='frontend/templates',
                static_folder='frontend/static',
                static_url_path='/static')
    
    # Load configuration
    config_name = config_name or os.environ.get('FLASK_ENV', 'default')
    app.config.from_object(config[config_name])
    
    # Setup logging
    logger = setup_logging(Path(app.config['LOG_DIR']))
    logger.info("🚀 Initializing Lease Management Application...")
    
    # Initialize CORS
    cors_origins = app.config.get('CORS_ORIGINS', ['*'])
    if isinstance(cors_origins, str):
        cors_origins = cors_origins.split(',')
    
    CORS(app, 
         resources={r"/api/*": {"origins": cors_origins, "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type"]}}, 
         supports_credentials=True)
    
    # Initialize database (only users table)
    database.init_database()
    logger.info("✅ Database initialized")
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(pdf_bp)
    app.register_blueprint(calc_bp)
    logger.info("✅ Blueprints registered")

    # Bootstrap: make user 'Rohit' admin if exists
    try:
        user = database.get_user_by_username('Rohit')
        if user and user.get('role') != 'admin':
            database.set_user_role(user['user_id'], 'admin')
            logger.info("👑 Bootstrapped user 'Rohit' to admin role")
    except Exception as e:
        logger.warning(f"Admin bootstrap skipped: {e}")
    
    # Session configuration
    @app.before_request
    def make_session_permanent():
        session.permanent = False
    
    # Root route - redirect to login
    @app.route('/')
    def index():
        return redirect('/login.html')
    
    # Login page
    @app.route('/login')
    @app.route('/login.html')
    def login_page():
        try:
            return render_template('login.html')
        except Exception as e:
            logger.error(f"Error rendering login.html: {e}")
            return f"Error loading login page: {e}", 500
    
    # Dashboard/Home page (blank screen)
    @app.route('/dashboard')
    @app.route('/dashboard.html')
    def dashboard_page():
        # Check if user is logged in
        if 'user_id' not in session:
            return redirect('/login.html')
        try:
            return render_template('dashboard.html')
        except Exception as e:
            logger.error(f"Error rendering dashboard.html: {e}")
            return f"Error loading dashboard: {e}", 500
    
    @app.route('/api/leases/<int:lease_id>/copy', methods=['POST'])
    @require_login
    def copy_lease_route(lease_id):
        return copy_lease(lease_id)

    # Lease Form page
    @app.route('/lease_form')
    @app.route('/lease_form.html')
    def lease_form_page():
        # Check if user is logged in
        if 'user_id' not in session:
            return redirect('/login.html')
        try:
            return render_template('lease_form.html')
        except Exception as e:
            logger.error(f"Error rendering lease_form.html: {e}")
            return f"Error loading lease form: {e}", 500
    
    # Calculate page
    @app.route('/calculate')
    @app.route('/calculate.html')
    def calculate_page():
        # Check if user is logged in
        if 'user_id' not in session:
            return redirect('/login.html')
        try:
            return render_template('calculate.html')
        except Exception as e:
            logger.error(f"Error rendering calculate.html: {e}")
            return f"Error loading calculate page: {e}", 500
    
    # Consolidate Reports page
    @app.route('/consolidate')
    @app.route('/consolidate.html')
    def consolidate_page():
        # Check if user is logged in
        if 'user_id' not in session:
            return redirect('/login.html')
        try:
            return render_template('consolidate.html')
        except Exception as e:
            logger.error(f"Error rendering consolidate.html: {e}")
            return f"Error loading consolidate page: {e}", 500

    # Approvals page (maker-checker queue)
    @app.route('/approvals')
    @app.route('/approvals.html')
    def approvals_page():
        if 'user_id' not in session:
            return redirect('/login.html')
        try:
            return render_template('approvals.html')
        except Exception as e:
            logger.error(f"Error rendering approvals.html: {e}")
            return f"Error loading approvals page: {e}", 500

    # Admin page (users & roles)
    @app.route('/admin')
    @app.route('/admin.html')
    @require_login
    @require_admin
    def admin_page():
        try:
            return render_template('admin.html')
        except Exception as e:
            logger.error(f"Error rendering admin.html: {e}")
            return f"Error loading admin page: {e}", 500

    # Audit Log page
    @app.route('/audit_log')
    @app.route('/audit_log.html')
    @require_login
    def audit_log_page():
        try:
            return render_template('audit_log.html')
        except Exception as e:
            logger.error(f"Error rendering audit_log.html: {e}")
            return f"Error loading audit log page: {e}", 500
    
    logger.info("✅ Application created successfully")
    return app


# Create app instance
app = create_app()


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    
    logger.info("══════════════════════════════════════════════════════════════")
    logger.info("   📊 Lease Management System - Starting Server")
    logger.info("══════════════════════════════════════════════════════════════")
    logger.info(f"📍 API Endpoint: http://localhost:{Config.API_PORT}/api/")
    logger.info("   - /api/register - User registration")
    logger.info("   - /api/login - User login")
    logger.info("   - /api/logout - User logout")
    logger.info(f"📝 Logs: {Config.LOG_DIR}/lease_app.log")
    logger.info("══════════════════════════════════════════════════════════════")
    
    app.run(
        debug=Config.DEBUG,
        host=Config.API_HOST,
        port=Config.API_PORT
    )
