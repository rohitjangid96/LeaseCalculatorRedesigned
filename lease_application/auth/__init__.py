"""
Authentication Module
Handles user authentication, registration, and session management

VBA Source: None (new functionality)
"""

from flask import Blueprint, request, jsonify, session
from functools import wraps
import logging
from .. import database

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
        
        # Return the full user object, similar to /api/user
        user_info = database.get_user(user['user_id'])
        user_info.pop('password_hash', None) # Ensure password hash is not sent

        return jsonify({
            'success': True,
            'user': user_info
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


# Expose decorators from auth.auth
from .auth import require_login, require_admin


@auth_bp.route('/users', methods=['GET'])
@require_login
@require_admin
def list_users():
    users = database.list_users()
    return jsonify({'success': True, 'users': users})


@auth_bp.route('/users/<int:user_id>/role', methods=['PUT'])
@require_login
@require_admin
def set_role(user_id):
    role = (request.json or {}).get('role', 'user')
    database.set_user_role(user_id, role)
    return jsonify({'success': True})


@auth_bp.route('/users/<int:user_id>/active', methods=['PUT'])
@require_login
@require_admin
def set_active(user_id):
    is_active = bool((request.json or {}).get('is_active', True))
    database.set_user_active(user_id, is_active)
    return jsonify({'success': True})
