"""
Authentication Utilities
Helper functions for authentication
"""

from functools import wraps
from flask import session, jsonify
import logging

logger = logging.getLogger(__name__)


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


def require_admin(f):
    """
    Decorator to require admin role
    Must be used after @require_login
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from database import get_user
        
        user_id = session.get('user_id')
        user = get_user(user_id)
        
        if not user or user.get('role') != 'admin':
            logger.warning(f"❌ Admin access denied for user_id={user_id}")
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function


def require_reviewer(f):
    """
    Decorator to require reviewer or admin role
    Must be used after @require_login
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from database import get_user
        
        user_id = session.get('user_id')
        user = get_user(user_id)
        
        if not user or user.get('role') not in ['admin', 'reviewer']:
            logger.warning(f"❌ Reviewer access denied for user_id={user_id}")
            return jsonify({'error': 'Reviewer access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

