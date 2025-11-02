"""
API Routes for Lease Management
Simplified lease creation and management
"""

from flask import Blueprint, request, jsonify, session
import logging
import database

logger = logging.getLogger(__name__)

# Create API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import require_login decorator
from auth import require_login


@api_bp.route('/leases', methods=['GET'])
@require_login
def get_leases():
    """Get all leases for current user"""
    user_id = session['user_id']
    logger.info(f"📋 GET /api/leases - User {user_id} fetching leases")
    
    try:
        leases = database.get_all_leases(user_id)
        logger.info(f"Found {len(leases)} leases for user {user_id}")
        return jsonify({'success': True, 'leases': leases})
    except Exception as e:
        logger.error(f"Error fetching leases: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/leases', methods=['POST'])
@require_login
def create_lease():
    """Create a new lease"""
    user_id = session['user_id']
    logger.info(f"➕ POST /api/leases - User {user_id} creating lease")
    
    try:
        data = request.json
        # CRITICAL: Log IBR field in incoming data
        logger.info(f"➕ API received create data - IBR: ibr={data.get('ibr')}, borrowing_rate={data.get('borrowing_rate')}")
        lease_id = database.save_lease(user_id, data)
        logger.info(f"✅ Lease saved: lease_id={lease_id}")
        
        return jsonify({
            'success': True,
            'lease_id': lease_id,
            'message': 'Lease saved successfully'
        }), 201
    except Exception as e:
        logger.error(f"Error creating lease: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/leases/<int:lease_id>', methods=['GET'])
@require_login
def get_lease(lease_id):
    """Get a specific lease"""
    user_id = session['user_id']
    logger.info(f"🔍 GET /api/leases/{lease_id} - User {user_id} fetching lease")
    
    try:
        lease = database.get_lease(lease_id, user_id)
        if lease:
            # CRITICAL: Log IBR field in API response
            logger.info(f"🔍 API returning lease - IBR: ibr={lease.get('ibr')}, borrowing_rate={lease.get('borrowing_rate')}")
            return jsonify({'success': True, 'lease': lease})
        else:
            return jsonify({'success': False, 'error': 'Lease not found'}), 404
    except Exception as e:
        logger.error(f"Error fetching lease: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/leases/<int:lease_id>', methods=['PUT'])
@require_login
def update_lease(lease_id):
    """Update an existing lease"""
    user_id = session['user_id']
    logger.info(f"✏️ PUT /api/leases/{lease_id} - User {user_id} updating lease")
    
    try:
        data = request.json
        # CRITICAL: Log IBR field in incoming data
        logger.info(f"✏️ API received update data - IBR: ibr={data.get('ibr')}, borrowing_rate={data.get('borrowing_rate')}")
        data['lease_id'] = lease_id
        updated_id = database.save_lease(user_id, data)
        logger.info(f"✅ Lease updated: lease_id={updated_id}")
        
        return jsonify({
            'success': True,
            'lease_id': updated_id,
            'message': 'Lease updated successfully'
        })
    except Exception as e:
        logger.error(f"Error updating lease: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/leases/<int:lease_id>', methods=['DELETE'])
@require_login
def delete_lease(lease_id):
    """Delete a lease"""
    user_id = session['user_id']
    logger.info(f"🗑️ DELETE /api/leases/{lease_id} - User {user_id} deleting lease")
    
    try:
        success = database.delete_lease(lease_id, user_id)
        if success:
            return jsonify({'success': True, 'message': 'Lease deleted'})
        else:
            return jsonify({'success': False, 'error': 'Lease not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting lease: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

