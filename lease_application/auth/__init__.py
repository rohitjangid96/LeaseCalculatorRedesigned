"""
Authentication Module
Handles user authentication, registration, and session management

VBA Source: None (new functionality)
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
import logging
import database

logger = logging.getLogger(__name__)

# Create authentication blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/api')


@auth_bp.route('/register', methods=['POST'])
def register():
    """User registration endpoint"""
    logger.info("📝 POST /api/register - User registration request")
    data = request.json
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    if not username or not password:
        logger.warning("❌ Registration failed: Missing username/password")
        return jsonify({'error': 'Username and password required'}), 400
    
    try:
        user_id = database.create_user(username, password, email)
        logger.info(f"✅ User created successfully: user_id={user_id}")
        return jsonify({
            'success': True,
            'user_id': user_id,
            'message': 'User created successfully'
        }), 201
    except Exception as e:
        logger.error(f"❌ Registration error: {str(e)}")
        return jsonify({'error': str(e)}), 400


@auth_bp.route('/login', methods=['POST'])
def login():
    """User login endpoint"""
    logger.info("🔐 POST /api/login - Login request")
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = database.authenticate_user(username, password)
    
    if user:
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        logger.info(f"✅ Login successful: user_id={user['user_id']}, username={username}")
        return jsonify({
            'success': True,
            'user': {
                'user_id': user['user_id'],
                'username': user['username'],
                'email': user.get('email')
            }
        })
    else:
        logger.warning(f"❌ Login failed: Invalid credentials for username={username}")
        return jsonify({'error': 'Invalid credentials'}), 401


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """User logout endpoint"""
    user_id = session.get('user_id')
    logger.info(f"🚪 POST /api/logout - User {user_id} logging out")
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out'})


@auth_bp.route('/user', methods=['GET'])
def get_current_user():
    """Get current logged-in user"""
    logger.debug("👤 GET /api/user - Checking user session")
    if 'user_id' in session:
        user = database.get_user(session['user_id'])
        if user:
            logger.debug(f"User {user['username']} session valid")
            return jsonify({'success': True, 'user': user})
    
    logger.debug("No valid session")
    return jsonify({'success': False, 'message': 'Not logged in'}), 401


# require_login decorator is defined in auth/auth.py
# Import it here for convenience, but other modules should import from auth.auth
from functools import wraps
from flask import session, jsonify

def require_login(f):
    """
    Decorator to require authentication
    Use this decorator on routes that need authentication
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            logger.warning("❌ Unauthorized access attempt")
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

