from flask import jsonify, session
from .database import get_db_connection, get_user

def copy_lease(lease_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get the original lease data
        cursor.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,))
        original_lease = cursor.fetchone()

        if not original_lease:
            return jsonify({'success': False, 'message': 'Lease not found'}), 404

        # Create a new lease by copying the original data
        new_lease_data = dict(original_lease)
        del new_lease_data['lease_id']  # Remove the original lease ID

        # Set the status of the new lease to 'draft' if the user is not an admin or reviewer
        user_id = session.get('user_id')
        user = get_user(user_id)
        if user['role'] not in ['admin', 'reviewer']:
            new_lease_data['status'] = 'draft'

        # Create a new agreement title for the copied lease
        new_lease_data['agreement_title'] = f"Copy of {new_lease_data['agreement_title']}"


        # Insert the new lease into the database
        columns = ', '.join(new_lease_data.keys())
        placeholders = ', '.join('?' for _ in new_lease_data)
        cursor.execute(f"INSERT INTO leases ({columns}) VALUES ({placeholders})", tuple(new_lease_data.values()))
        new_lease_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'new_lease_id': new_lease_id})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500