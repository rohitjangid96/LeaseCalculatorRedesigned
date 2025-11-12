"""
API Routes for Lease Management
Simplified lease creation and management
"""

from flask import Blueprint, request, jsonify, session, send_from_directory, url_for, current_app, abort
from werkzeug.utils import secure_filename
import os
import tempfile
import logging
import base64
from . import database
from datetime import datetime, date
from lease_application.config import Config

logger = logging.getLogger(__name__)

# Create API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import require_login decorator
from .auth import require_login
from .auth.auth import require_admin, require_reviewer

# Use permanent storage location from config
DOC_UPLOAD_DIR = Config.DOC_UPLOAD_FOLDER
os.makedirs(DOC_UPLOAD_DIR, exist_ok=True)


@api_bp.route('/leases/<int:lease_id>/documents', methods=['POST'])
@require_login
def upload_document(lease_id):
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    filename = secure_filename(file.filename)
    # Add a timestamp or UUID to make the filename unique
    unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    file_path = os.path.join(DOC_UPLOAD_DIR, unique_filename)
    
    try:
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        document_type = request.form.get('document_type', 'contract') # Default to 'contract'
        
        database.save_document_metadata(
            lease_id=lease_id,
            file_name=filename,
            file_path=file_path,
            file_size=file_size,
            uploaded_by=session['user_id'],
            document_type=document_type
        )
        
        return jsonify({'success': True, 'message': 'File uploaded successfully'}), 201
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/leases/<int:lease_id>/documents', methods=['GET'])
@require_login
def get_documents(lease_id):
    try:
        documents = database.get_documents_by_lease(lease_id)
        return jsonify({'success': True, 'documents': documents})
    except Exception as e:
        logger.error(f"Error getting documents: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/documents/<int:doc_id>/download', methods=['GET'])
@require_login
def download_document(doc_id):
    try:
        document = database.get_document_by_id(doc_id)
        if not document:
            return jsonify({'success': False, 'error': 'Document not found'}), 404
        
        directory = os.path.dirname(document['file_path'])
        filename = os.path.basename(document['file_path'])
        
        return send_from_directory(directory, filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Error downloading document: {e}")
        abort(500)


@api_bp.route('/leases', methods=['GET'])
@require_login
def get_leases():
    """Get all leases for current user"""
    user_id = session['user_id']
    logger.info(f"📋 GET /api/leases - User {user_id} fetching leases")
    
    try:
        user = database.get_user(user_id)
        # If the user is an admin or reviewer, return all leases.
        # Otherwise, only return leases created by the user.
        if user and (user['role'] == 'admin' or user['role'] == 'reviewer'):
            leases = database.get_all_leases()
        else:
            leases = database.get_leases_by_user(user_id)
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
        data = request.json or {}
        # Auto-approval logic based on role
        try:
            user = database.get_user(user_id)
            creator_role = (user or {}).get('role', 'user')
            # Per requirement: admin and reviewer's leases auto-approved; users need review
            if not data.get('status'):
                data['status'] = 'approved' if creator_role in ['admin', 'reviewer'] else 'submitted'
        except Exception:
            pass
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
        user = database.get_user(user_id)
        # Admins can get any lease, others are restricted to their own.
        if user and user['role'] == 'admin':
            lease = database.get_lease(lease_id)
        else:
            lease = database.get_lease(lease_id, user_id)
            
        if lease:
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
        user = database.get_user(user_id)
        role = user.get('role', 'user') if user else 'user'
        data = request.json or {}
        data['lease_id'] = lease_id
        updated_id, _ = database.save_lease(user_id, data, role=role)
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


@api_bp.route('/leases/<int:lease_id>/copy', methods=['POST'])
@require_login
def copy_lease(lease_id):
    """Copy an existing lease"""
    user_id = session['user_id']
    logger.info(f"📋 POST /api/leases/{lease_id}/copy - User {user_id} copying lease")
    
    try:
        user = database.get_user(user_id)
        # Admins can copy any lease, others are restricted to their own.
        if user and user['role'] == 'admin':
            original_lease = database.get_lease(lease_id)
        else:
            original_lease = database.get_lease(lease_id, user_id)

        if not original_lease:
            return jsonify({'success': False, 'error': 'Original lease not found or unauthorized'}), 404
        
        # Create a new lease dictionary from the original
        new_lease_data = dict(original_lease)
        new_lease_data.pop('lease_id', None) # Remove original ID
        new_lease_data['status'] = 'draft' # New lease starts as draft
        new_lease_data['agreement_title'] = f"Copy of {original_lease.get('agreement_title', 'Untitled Lease')}"
        new_lease_data['created_by'] = user_id
        new_lease_data['created_at'] = datetime.now().isoformat() # Update creation timestamp
        new_lease_data['updated_at'] = datetime.now().isoformat() # Update update timestamp
        
        copied_lease_id = database.save_lease(user_id, new_lease_data)
        logger.info(f"✅ Lease copied: original_id={lease_id}, new_id={copied_lease_id}")
        
        return jsonify({
            'success': True,
            'lease_id': copied_lease_id,
            'message': 'Lease copied successfully'
        }), 201
    except Exception as e:
        logger.error(f"Error copying lease: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/leases/<int:lease_id>/submit', methods=['POST'])
@require_login
def submit_lease(lease_id):
    """Submit a lease for review (maker action)"""
    user_id = session['user_id']
    logger.info(f"📤 POST /api/leases/{lease_id}/submit - User {user_id} submitting lease")
    try:
        database.submit_lease_for_review(lease_id, user_id)
        # Optional: send email to reviewers/admins
        _notify_on_status_change(lease_id, 'submitted')
        return jsonify({'success': True, 'message': 'Lease submitted for review'})
    except Exception as e:
        logger.error(f"Error submitting lease: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/leases/<int:lease_id>/approve', methods=['POST'])
@require_login
@require_reviewer
def approve_lease(lease_id):
    """Approve a submitted lease (checker action)"""
    approver_user_id = session['user_id']
    logger.info(f"✅ POST /api/leases/{lease_id}/approve - Approver {approver_user_id}")
    try:
        database.approve_lease(lease_id, approver_user_id)
        _notify_on_status_change(lease_id, 'approved')
        return jsonify({'success': True, 'message': 'Lease approved'})
    except Exception as e:
        logger.error(f"Error approving lease: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/leases/<int:lease_id>/reject', methods=['POST'])
@require_login
@require_reviewer
def reject_lease(lease_id):
    """Reject a submitted lease with reason"""
    approver_user_id = session['user_id']
    reason = (request.json or {}).get('reason', '')
    logger.info(f"❌ POST /api/leases/{lease_id}/reject - Approver {approver_user_id}")
    try:
        database.reject_lease(lease_id, approver_user_id, reason)
        _notify_on_status_change(lease_id, 'rejected', reason)
        return jsonify({'success': True, 'message': 'Lease rejected'})
    except Exception as e:
        logger.error(f"Error rejecting lease: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/leases/<int:lease_id>/status', methods=['POST'])
@require_login
@require_admin
def set_lease_status(lease_id):
    """Admin override to set any lease status, including approved."""
    try:
        body = request.json or {}
        status = body.get('status')
        if status not in ['draft','submitted','approved','rejected']:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400
        with database.get_db_connection() as conn:
            conn.execute("UPDATE leases SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE lease_id = ?", (status, lease_id))
        try:
            username = session.get('username')
            database.add_lease_audit(lease_id, username or 'admin', f'status_set_{status}', None)
        except Exception:
            pass
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error setting lease status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def _notify_on_status_change(lease_id: int, status: str, reason: str = ''):
    """Best-effort email notification on status changes (silent on failure)."""
    try:
        # Load lease and a basic recipient set (admin/reviewer). Simplified for now.
        with database.get_db_connection() as conn:
            lease = conn.execute("SELECT agreement_title, company_name FROM leases WHERE lease_id = ?", (lease_id,)).fetchone()
            users = conn.execute("SELECT email FROM users WHERE role IN ('admin','reviewer') AND is_active = 1 AND email IS NOT NULL").fetchall()
        to_addrs = [u['email'] for u in users if u['email']]
        if not to_addrs:
            return
        subject = f"Lease {status.title()}: #{lease_id} - {lease['agreement_title'] or 'Untitled'}"
        details = f"<p>Company: <strong>{lease['company_name'] or '-'}" + "</strong></p>"
        if status == 'rejected' and reason:
            details += f"<p>Rejection Reason: {reason}</p>"
        html = f"""
            <h3>Lease {status.title()}</h3>
            <p>Lease ID: <strong>{lease_id}</strong></p>
            {details}
            <p>View in app: <a href=\"{url_for('dashboard_page', _external=True)}\">Dashboard</a></p>
        """
        from config import Config
        database.send_email(
            smtp_host=Config.SMTP_HOST,
            smtp_port=Config.SMTP_PORT,
            username=Config.SMTP_USERNAME,
            password=Config.SMTP_PASSWORD,
            from_addr=Config.SMTP_FROM,
            to_addrs=to_addrs,
            subject=subject,
            html_body=html
        )
    except Exception as e:
        logger.warning(f"Email notification failed: {e}")

@api_bp.route('/upload_and_extract', methods=['POST'])
@require_login
def upload_and_extract_lease_data():
    """
    Upload PDF file, extract lease data with AI, and locate bounding boxes.
    Returns extracted data and highlights for PDF.js rendering.
    """
    user_id = session['user_id']
    logger.info(f"📄 POST /api/upload_and_extract - User {user_id} uploading PDF")
    
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file part in the request"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No selected file"}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        # Get API key from request or environment
        api_key = request.form.get('api_key')
        if not api_key:
            api_key = os.getenv('GOOGLE_AI_API_KEY')
        
        # Save the file temporarily
        filename = secure_filename(file.filename)
        timestamp = str(int(__import__('time').time() * 1000))  # Unique timestamp
        unique_filename = f"{timestamp}_{filename}"
        pdf_path = os.path.join(DOC_UPLOAD_DIR, unique_filename)
        
        try:
            file.save(pdf_path)
            logger.info(f"✅ File saved to: {pdf_path}")
            
            # Use the same extraction method that works (from pdf_upload_backend.py)
            try:
                from .lease_accounting.utils.pdf_extractor import extract_text_from_pdf
                from .lease_accounting.utils.ai_extractor import extract_lease_info_from_text, get_extraction_schema
                from .lease_accounting.utils.pdf_extractor import find_text_positions, normalize_search_text
            except ImportError as e:
                logger.error(f"❌ Import error: {e}")
                return jsonify({"success": False, "error": f"Extraction module not available: {e}"}), 500
            
            # Step 1: Extract text from PDF (same as working endpoint)
            logger.info(f"📄 Extracting text from PDF: {file.filename}")
            result = extract_text_from_pdf(pdf_path)
            if isinstance(result, tuple):
                text, status_msg = result
            else:
                text = result
                status_msg = ""
            
            if not text:
                return jsonify({
                    "success": False,
                    "error": status_msg or 'Failed to extract text from PDF. The PDF may be scanned or password-protected.'
                }), 400
            
            # Step 2: Extract lease info using AI (now returns original_text too)
            logger.info(f"🤖 Starting AI extraction")
            extracted_data = extract_lease_info_from_text(text, api_key)
            
            if 'error' in extracted_data:
                return jsonify({
                    "success": False,
                    "error": extracted_data['error']
                }), 200
            
            # Step 3: Map extracted values to bounding boxes using ORIGINAL TEXT from AI
            highlights = []
            
            # Get original texts that AI found (much more accurate than searching)
            original_texts = extracted_data.get('_original_texts', {})
            
            # Track which fields were actually populated (to avoid highlighting unused fields like rental_2)
            populated_fields = set()
            
            # Step 2.5: Pre-populate check - determine which fields will be populated
            # This helps us avoid highlighting fields that won't be used (e.g., rental_2 if rental_1 exists)
            for field_name, value in extracted_data.items():
                if field_name in ['_metadata', '_original_texts']:
                    continue
                if value is not None and value != "" and not isinstance(value, dict):
                    # Check if this field would be used (not skipped)
                    if field_name == 'rental_2' and 'rental_1' in extracted_data and extracted_data['rental_1']:
                        # rental_2 will be skipped if rental_1 exists
                        logger.info(f"⏭️ Field '{field_name}' will be skipped (rental_1 exists), excluding from highlights")
                        continue
                    populated_fields.add(field_name)
            
            # Log extracted text for comparison
            logger.info("=" * 80)
            logger.info("📊 EXTRACTION COMPARISON: Using AI Original Text for Highlights")
            logger.info("=" * 80)
            logger.info(f"📄 Extracted text length: {len(text)} characters")
            logger.info(f"📝 Extracted fields: {len([k for k in extracted_data.keys() if k not in ['_metadata', '_original_texts']])} fields")
            logger.info(f"🎯 Fields with original_text: {len([k for k, v in original_texts.items() if v])} fields")
            logger.info("")
            
            # Define boolean fields that should not search for generic terms
            BOOLEAN_FIELDS = ['finance_lease', 'sublease', 'bargain_purchase', 'title_transfer', 
                            'practical_expedient', 'short_term_ifrs', 'manual_adj', 'related_party']
            EXCLUDED_SEARCH_TERMS = ['no', 'yes', 'true', 'false', '1', '0', 'n', 'y']
            
            # Map each extracted field value to its bounding box using ORIGINAL TEXT from AI
            for field_name, value in extracted_data.items():
                # Skip metadata fields
                if field_name in ['_metadata', '_original_texts']:
                    continue
                
                # Only highlight fields that were actually populated (not skipped)
                if field_name not in populated_fields:
                    logger.info(f"⏭️ Skipping highlight for '{field_name}' - field was not populated")
                    continue
                
                if value is not None and value != "" and not isinstance(value, dict):
                    # Get the ORIGINAL TEXT that AI found (much more accurate!)
                    original_text = original_texts.get(field_name)
                    
                    # Convert value to string and normalize for search
                    search_value = str(value).strip()
                    
                    # Skip empty values
                    if not search_value or search_value.lower() in ['none', 'null', '']:
                        continue
                    
                    # Skip boolean fields with generic values (to avoid false positives)
                    if field_name in BOOLEAN_FIELDS:
                        search_value_lower = search_value.lower()
                        if search_value_lower in EXCLUDED_SEARCH_TERMS:
                            logger.info(f"🔍 Skipping field '{field_name}' - value '{search_value}' is too generic for boolean field")
                            continue  # Skip searching for generic boolean values
                    
                    # PRIMARY METHOD: Use original_text from AI if available (most accurate!)
                    search_terms = []
                    if original_text and original_text.strip() and original_text.lower() not in ['null', 'none', '']:
                        # Filter out label text for date fields (e.g., "Commencement Date" instead of actual date)
                        original_text_clean = original_text.strip()
                        
                        # For date fields, skip if it's just a label (not a date)
                        if field_name.endswith('_date') or 'date' in field_name.lower():
                            # Check if it's just a label like "Commencement Date", "Start Date", etc.
                            date_labels = ['commencement date', 'start date', 'end date', 'agreement date', 
                                         'termination date', 'first payment date', 'escalation start date',
                                         'expiration date', 'execution date', 'signed date']
                            if original_text_clean.lower() in date_labels:
                                logger.info(f"⚠️ Skipping label text for '{field_name}': '{original_text_clean}' - not a date value")
                                # Use the extracted value and generate date formats instead
                                original_text = None  # Fall back to date format generation
                            else:
                                # It's a date value, use it
                                logger.info(f"🎯 Using AI original_text for field '{field_name}': '{original_text_clean[:100]}'")
                                search_terms.append(original_text_clean)
                        else:
                            logger.info(f"🎯 Using AI original_text for field '{field_name}': '{original_text_clean[:100]}'")
                            search_terms.append(original_text_clean)
                    
                    if not search_terms:  # Fallback if original_text was filtered out or not available
                        logger.info(f"⚠️ No original_text from AI for field '{field_name}', using extracted value '{search_value}'")
                        search_terms.append(search_value)
                    
                    # For date fields, also try multiple date formats as backup (only if original_text not available)
                    if not original_text and (field_name.endswith('_date') or 'date' in field_name.lower()):
                        # Try to generate alternative date formats
                        try:
                            from datetime import datetime
                            if len(search_value) == 10 and search_value.count('-') == 2:  # YYYY-MM-DD format
                                date_obj = datetime.strptime(search_value, '%Y-%m-%d')
                                # Generate common date formats found in PDFs
                                search_terms.extend([
                                    date_obj.strftime('%m/%d/%Y'),  # 03/01/2002
                                    date_obj.strftime('%d/%m/%Y'),  # 01/03/2002
                                    date_obj.strftime('%m-%d-%Y'),   # 03-01-2002
                                    date_obj.strftime('%d-%m-%Y'),   # 01-03-2002
                                    date_obj.strftime('%B %d, %Y'),  # March 1, 2002
                                    date_obj.strftime('%d %B %Y'),   # 1 March 2002
                                ])
                                logger.info(f"   📅 Generated date format alternatives: {len(search_terms) - 1} formats")
                        except:
                            pass
                    
                    # For numeric fields, try different number formats (only if original_text not available)
                    elif not original_text and field_name in ['compound_months', 'frequency_months', 'tenure', 'escalation_percent', 'borrowing_rate', 'ibr', 'pay_day_of_month']:
                        try:
                            # Try as number with different formatting
                            num_value = float(search_value) if '.' in search_value else int(search_value)
                            # Add formatted versions with context
                            search_terms.extend([
                                str(int(num_value)),  # Integer format: "12"
                                f"{num_value:.2f}".rstrip('0').rstrip('.'),  # Decimal without trailing zeros
                                f"{num_value:.2f}%",  # With percentage: "12.00%"
                                f"{num_value}%",  # Integer with percentage: "12%"
                            ])
                            
                            # For month-related fields, add context like "12 months", "monthly", etc.
                            if 'month' in field_name.lower() or field_name == 'frequency_months':
                                month_terms = []
                                if num_value == 1:
                                    month_terms = ['monthly', 'month', '1 month', 'one month']
                                elif num_value == 3:
                                    month_terms = ['quarterly', 'quarter', '3 months', 'three months']
                                elif num_value == 6:
                                    month_terms = ['semi-annual', 'semi annual', '6 months', 'six months']
                                elif num_value == 12:
                                    month_terms = ['annual', 'yearly', '12 months', 'twelve months', 'year']
                                
                                for term in month_terms:
                                    if term not in search_terms:
                                        search_terms.append(term)
                                
                                # Also try with the number: "12 months"
                                search_terms.append(f"{int(num_value)} months")
                                search_terms.append(f"{int(num_value)} month")
                            
                            # For percentage fields
                            if 'percent' in field_name.lower() or field_name == 'escalation_percent':
                                search_terms.extend([
                                    f"{num_value} percent",
                                    f"{num_value} per cent",
                                    f"{num_value:.2f} percent",
                                    f"escalation {num_value}",
                                    f"increase {num_value}",
                                ])
                            
                            logger.info(f"   🔢 Generated number format alternatives for '{field_name}': {len(search_terms)} terms")
                        except:
                            pass
                    
                    # For currency/amount fields, try different formats
                    elif field_name in ['rental_1', 'rental_2', 'rental_amount', 'security_deposit', 'lease_incentive', 'initial_direct_expenditure']:
                        try:
                            num_value = float(search_value.replace(',', '')) if search_value.replace(',', '').replace('.', '').isdigit() else None
                            if num_value:
                                # Try formatted currency versions
                                search_terms.extend([
                                    f"${int(num_value):,}",  # $10,000
                                    f"${num_value:,.2f}",  # $10,000.00
                                    f"{int(num_value):,}",  # 10,000
                                    f"{num_value:,.2f}",  # 10,000.00
                                ])
                                logger.info(f"   💰 Generated currency format alternatives for '{field_name}'")
                        except:
                            pass
                    
                    # Find all positions of the value in the PDF (try all search terms)
                    all_matches = []
                    try:
                        # First pass: Try exact matches with all search terms
                        for search_term in search_terms:
                            if not search_term:
                                continue
                            
                            # Skip only very short terms (< 2 chars) unless it's a number
                            if len(search_term) < 2 and not search_term.isdigit():
                                continue
                                
                            # Normalize the search text
                            normalized_value = normalize_search_text(search_term)
                            
                            # Limit search length to avoid issues with very long values
                            if len(normalized_value) > 100:
                                normalized_value = normalized_value[:100]
                            
                            # Find positions (exact match) - fuzzy parameter might not be supported, ignore it
                            try:
                                term_matches = find_text_positions(pdf_path, normalized_value, case_sensitive=False)
                            except TypeError:
                                # If fuzzy parameter not supported, use without it
                                term_matches = find_text_positions(pdf_path, normalized_value, case_sensitive=False)
                            
                            # Deduplicate matches (same page and similar bbox)
                            for match in term_matches:
                                # Check if this match is already in all_matches
                                is_duplicate = False
                                for existing in all_matches:
                                    if (existing['page'] == match['page'] and 
                                        abs(existing['bbox'][0] - match['bbox'][0]) < 10 and
                                        abs(existing['bbox'][1] - match['bbox'][1]) < 10):
                                        is_duplicate = True
                                        break
                                if not is_duplicate:
                                    all_matches.append(match)
                            
                            # If we found matches, break early (for performance)
                            if len(all_matches) >= 3:
                                break
                        
                        # Second pass: If no matches found, try fuzzy matching for important fields
                        if len(all_matches) == 0 and search_value:
                            logger.info(f"   ⚠️ No exact matches found, trying fuzzy matching...")
                            normalized_original = normalize_search_text(search_value)
                            if len(normalized_original) <= 100:
                                # Try fuzzy matching on original value - use substring search
                                try:
                                    fuzzy_matches = find_text_positions(pdf_path, normalized_original, case_sensitive=False)
                                    # If still no matches, try just the first few words for long text
                                    if not fuzzy_matches and len(normalized_original.split()) > 1:
                                        first_words = ' '.join(normalized_original.split()[:3])  # First 3 words
                                        fuzzy_matches = find_text_positions(pdf_path, first_words, case_sensitive=False)
                                except Exception as e:
                                    logger.warning(f"   Fuzzy matching failed: {e}")
                                    fuzzy_matches = []
                                for match in fuzzy_matches[:2]:  # Limit to 2 fuzzy matches
                                    all_matches.append(match)
                        
                        matches = all_matches
                        logger.info(f"   ✅ Found {len(matches)} matches in PDF (across {len(search_terms)} search terms)")
                        
                        # For boolean fields, limit to first match only to reduce noise
                        match_limit = 1 if field_name in BOOLEAN_FIELDS else 3
                        
                        # CRITICAL: If no matches found but field has a value, try one more aggressive search
                        if len(matches) == 0 and search_value:
                            logger.info(f"   ⚠️ No matches found for '{field_name}'='{search_value}', trying broader search...")
                            
                            # Try searching for just the numeric part or key part
                            if search_value.replace('.', '').replace('-', '').isdigit():
                                # For numeric values, try just the number
                                numeric_only = search_value.replace(',', '').replace('.0', '').replace('.00', '')
                                try:
                                    broader_matches = find_text_positions(pdf_path, numeric_only, case_sensitive=False)
                                    if broader_matches:
                                        matches = broader_matches[:2]  # Take first 2 matches
                                        logger.info(f"   ✅ Found {len(matches)} matches using broader numeric search")
                                except:
                                    pass
                            
                            # For dates, try different component formats
                            elif field_name.endswith('_date') and len(search_value) == 10:
                                try:
                                    from datetime import datetime
                                    date_obj = datetime.strptime(search_value, '%Y-%m-%d')
                                    # Try just the year
                                    year_only = str(date_obj.year)
                                    broader_matches = find_text_positions(pdf_path, year_only, case_sensitive=False, fuzzy=False)
                                    # Or try month/day combinations
                                    if not broader_matches:
                                        month_day = f"{date_obj.month}/{date_obj.day}"
                                        broader_matches = find_text_positions(pdf_path, month_day, case_sensitive=False, fuzzy=False)
                                    if broader_matches:
                                        matches = broader_matches[:1]  # Take first match
                                        logger.info(f"   ✅ Found {len(matches)} matches using broader date search")
                                except:
                                    pass
                        
                        # Log each match
                        for idx, match in enumerate(matches[:match_limit], 1):
                            logger.info(f"      Match {idx}: Page {match['page']}, BBox: {match['bbox']}, Text: '{match.get('text', search_value)[:50]}'")
                        
                        # CRITICAL: If still no matches, create a fallback highlight using extracted value text
                        if len(matches) == 0:
                            logger.warning(f"   ⚠️⚠️⚠️ NO HIGHLIGHT FOUND for field '{field_name}' with value '{search_value}'")
                            logger.warning(f"      This field will NOT have a visual highlight in the PDF")
                            logger.warning(f"      Consider: Field might be derived/calculated or not explicitly stated in PDF")
                        else:
                            # Collect matches for the highlight list (use first valid match if available)
                            for match in matches[:match_limit]:
                                highlights.append({
                                    "field": field_name,
                                    "page": match['page'],
                                    "bbox": match['bbox'],  # Bounding box in pdfplumber units [x0, top, x1, bottom]
                                    "text": match.get('text', search_value)
                                })
                    except Exception as e:
                        logger.error(f"   ❌ Could not find positions for field {field_name}: {e}", exc_info=True)
                        # Don't continue - we want to see which fields failed
                        continue
                
                logger.info("")  # Blank line between fields
            
            logger.info(f"📌 Total highlights created: {len(highlights)}")
            logger.info("=" * 80)
            
            # Generate URL for serving the PDF (will be handled by the static_files route)
            # Use blueprint prefix 'api.' since the route is in the api_bp blueprint
            pdf_url = url_for('api.static_files', filename=unique_filename)
            
            # Extract confidence scores from metadata if available
            confidence_scores = {}
            if '_metadata' in extracted_data:
                metadata = extracted_data['_metadata']
                logger.debug(f"   📊 Found metadata with {len(metadata)} fields")
                for field_name, field_info in metadata.items():
                    if isinstance(field_info, dict) and 'confidence_score' in field_info:
                        confidence_score = field_info['confidence_score']
                        confidence_scores[field_name] = confidence_score
                        logger.debug(f"   📊 Confidence score for {field_name}: {confidence_score}")
                logger.debug(f"   📊 Total confidence scores extracted: {len(confidence_scores)}")

            # If no confidence scores were extracted, create default ones for all extracted fields
            if not confidence_scores:
                logger.info(f"   📊 AI did not provide confidence scores, using default scores (0.8) for all fields")
                for field_name, field_value in extracted_data.items():
                    if field_name not in ['_metadata', '_original_texts'] and field_value is not None:
                        confidence_scores[field_name] = 0.8  # Default high confidence
                        logger.debug(f"   📊 Default confidence score for {field_name}: 0.8")
                logger.info(f"   📊 Created {len(confidence_scores)} default confidence scores")

            # Return the result to the frontend
            return jsonify({
                "success": True,
                "data": extracted_data,
                "highlights": highlights,
                "pdf_url": pdf_url,
                "confidence_scores": confidence_scores
            }), 200
        
        except Exception as e:
            logger.error(f"❌ Extraction failed: {e}", exc_info=True)
            # Clean up file on error
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except:
                    pass
            return jsonify({"success": False, "error": f"Extraction process failed: {str(e)}"}), 500
    
    return jsonify({"success": False, "error": "Invalid file type. Only PDF is supported."}), 400


@api_bp.route('/static_files/<filename>')
@require_login
def static_files(filename):
    """
    Serve temporary PDF files for PDF.js to load.
    This allows PDF.js to fetch the PDF from the server.
    """
    try:
        # Security: ensure filename is safe and exists
        filename = secure_filename(filename)
        file_path = os.path.join(DOC_UPLOAD_DIR, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        
        # Serve the file with appropriate headers
        return send_from_directory(
            DOC_UPLOAD_DIR,
            filename,
            mimetype='application/pdf',
            as_attachment=False
        )
    except Exception as e:
        logger.error(f"Error serving static file: {e}")
        return jsonify({"error": str(e)}), 500


# ============ Admin Config APIs ============
@api_bp.route('/admin/config', methods=['GET'])
@require_login
@require_admin
def get_admin_config():
    try:
        cfg = database.get_configs()
        # Only expose known keys
        safe = {
            'SMTP_HOST': cfg.get('SMTP_HOST') or '',
            'SMTP_PORT': cfg.get('SMTP_PORT') or '',
            'SMTP_USERNAME': cfg.get('SMTP_USERNAME') or '',
            'SMTP_FROM': cfg.get('SMTP_FROM') or '',
            'GEMINI_API_KEY': '***' if cfg.get('GEMINI_API_KEY') else ''
        }
        return jsonify({'success': True, 'config': safe})
    except Exception as e:
        logger.error(f"Error getting admin config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/admin/config', methods=['PUT'])
@require_login
@require_admin
def set_admin_config():
    try:
        body = request.json or {}
        for key in ['SMTP_HOST','SMTP_PORT','SMTP_USERNAME','SMTP_PASSWORD','SMTP_FROM','GEMINI_API_KEY']:
            if key in body and body[key] is not None:
                database.set_config(key, str(body[key]))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error setting admin config: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ Dashboard Stats ============
@api_bp.route('/leases/stats', methods=['GET'])
@require_login
def get_lease_stats():
    """Get lease statistics"""
    user_id = session['user_id']
    logger.info(f"📊 GET /api/leases/stats - User {user_id} fetching stats")
    
    try:
        user = database.get_user(user_id)
        
        if user and (user['role'] == 'admin' or user['role'] == 'reviewer'):
            leases = database.get_all_leases()
        else:
            leases = database.get_leases_by_user(user_id)
        
        stats = {
            'total': len(leases),
            'active': 0,
            'expired': 0,
            'counts': {}
        }
        
        today = date.today()
        
        for lease in leases:
            status = lease.get('status', 'draft')
            stats['counts'][status] = stats['counts'].get(status, 0) + 1
            
            end_date_str = lease.get('lease_end_date')
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    if end_date < today:
                        stats['expired'] += 1
                    else:
                        stats['active'] += 1
                except ValueError:
                    # Handle cases where the date format might be incorrect
                    pass

        return jsonify({'success': True, **stats})
        
    except Exception as e:
        logger.error(f"Error fetching lease stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/leases/stats_by_company', methods=['GET'])
@require_login
def get_lease_stats_by_company():
    """Get lease statistics by company"""
    user_id = session['user_id']
    logger.info(f"🏢 GET /api/leases/stats_by_company - User {user_id} fetching stats")
    
    try:
        user = database.get_user(user_id)
        
        if user and (user['role'] == 'admin' or user['role'] == 'reviewer'):
            leases = database.get_all_leases()
        else:
            leases = database.get_leases_by_user(user_id)
            
        stats = {}
        
        for lease in leases:
            company_name = lease.get('company_name', 'Unknown')
            if company_name not in stats:
                stats[company_name] = {'total': 0, 'active': 0, 'expired': 0}
            
            stats[company_name]['total'] += 1
            
            end_date_str = lease.get('lease_end_date')
            if end_date_str:
                try:
                    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                    if end_date < date.today():
                        stats[company_name]['expired'] += 1
                    else:
                        stats[company_name]['active'] += 1
                except ValueError:
                    pass
                    
        return jsonify({'success': True, 'stats': stats})
        
    except Exception as e:
        logger.error(f"Error fetching lease stats by company: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/user', methods=['GET'])
@require_login
def get_current_user_info():
    """Get current user information"""
    user_id = session.get('user_id')
    if user_id:
        user = database.get_user(user_id)
        if user:
            # Remove sensitive info like password hash
            user.pop('password_hash', None)
            return jsonify({'success': True, 'user': user})
    return jsonify({'success': False, 'error': 'User not logged in'}), 401


@api_bp.route('/audit_logs', methods=['GET'])
@require_login
def get_audit_logs():
    """Get all audit logs"""
    user_id = session['user_id']
    logger.info(f"📋 GET /api/audit_logs - User {user_id} fetching audit logs")
    
    try:
        with database.get_db_connection() as conn:
            rows = conn.execute("SELECT * FROM lease_data_audit ORDER BY change_timestamp DESC").fetchall()
            logs = [dict(row) for row in rows]
        
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        logger.error(f"Error fetching audit logs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/send_report', methods=['POST'])
@require_login
def send_report():
    """Send a report via email"""
    user_id = session['user_id']
    logger.info(f"📧 POST /api/send_report - User {user_id} sending report")

    try:
        data = request.json or {}
        to_email = data.get('to_email')
        subject = data.get('subject')
        body = data.get('body')
        attachment_content = data.get('attachment_content')
        attachment_filename = data.get('attachment_filename')

        if not to_email or not subject or not body:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        configs = database.get_configs()
        smtp_host = configs.get('SMTP_HOST')
        smtp_port = int(configs.get('SMTP_PORT', 587))
        smtp_user = configs.get('SMTP_USERNAME')
        smtp_pass = configs.get('SMTP_PASSWORD')
        from_email = configs.get('SMTP_FROM')

        if not all([smtp_host, smtp_port, smtp_user, smtp_pass, from_email]):
            return jsonify({'success': False, 'error': 'Email is not configured. Please contact an administrator.'}), 500

        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.base import MIMEBase
        from email import encoders

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        if attachment_content and attachment_filename:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(base64.b64decode(attachment_content))
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{attachment_filename}"')
            msg.attach(part)

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        return jsonify({'success': True, 'message': 'Email sent successfully'})
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ NOTIFICATION SETTINGS ============
@api_bp.route('/notifications/settings', methods=['GET'])
@require_login
@require_admin
def get_notification_settings():
    """Get all notification settings"""
    try:
        settings = database.get_notification_settings()
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        logger.error(f"Error fetching notification settings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/notifications/settings', methods=['POST'])
@require_login
@require_admin
def create_notification_setting():
    """Create a new notification setting"""
    try:
        data = request.json or {}
        trigger_field = data.get('trigger_field')
        days_in_advance = data.get('days_in_advance')
        recipient_role = data.get('recipient_role')
        message_template = data.get('message_template')

        if not all([trigger_field, days_in_advance is not None, recipient_role, message_template]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        rule_id = database.create_notification_setting(trigger_field, days_in_advance, recipient_role, message_template)
        return jsonify({'success': True, 'rule_id': rule_id, 'message': 'Notification setting created successfully'}), 201
    except Exception as e:
        logger.error(f"Error creating notification setting: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/notifications/settings/<int:rule_id>', methods=['PUT'])
@require_login
@require_admin
def update_notification_setting(rule_id):
    """Update an existing notification setting"""
    try:
        data = request.json or {}
        trigger_field = data.get('trigger_field')
        days_in_advance = data.get('days_in_advance')
        recipient_role = data.get('recipient_role')
        message_template = data.get('message_template')
        is_active = data.get('is_active', True)

        if not all([trigger_field, days_in_advance is not None, recipient_role, message_template]):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        success = database.update_notification_setting(rule_id, trigger_field, days_in_advance, recipient_role, message_template, is_active)
        if success:
            return jsonify({'success': True, 'message': 'Notification setting updated successfully'})
        else:
            return jsonify({'success': False, 'error': 'Notification setting not found'}), 404
    except Exception as e:
        logger.error(f"Error updating notification setting: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/notifications/settings/<int:rule_id>', methods=['DELETE'])
@require_login
@require_admin
def delete_notification_setting(rule_id):
    """Delete a notification setting"""
    try:
        success = database.delete_notification_setting(rule_id)
        if success:
            return jsonify({'success': True, 'message': 'Notification setting deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Notification setting not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting notification setting: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ USER NOTIFICATION INBOX ============
@api_bp.route('/notifications/inbox', methods=['GET'])
@require_login
def get_user_notifications():
    """Get current user's notifications"""
    user_id = session['user_id']
    logger.info(f"📬 GET /api/notifications/inbox - User {user_id} fetching notifications")

    try:
        from .lease_management.notifications import get_user_notifications
        notifications = get_user_notifications(user_id)

        # Count unread notifications
        unread_count = sum(1 for n in notifications if not n['is_read'])

        return jsonify({
            'success': True,
            'notifications': notifications,
            'unread_count': unread_count
        })
    except Exception as e:
        logger.error(f"Error fetching user notifications: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@require_login
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    user_id = session['user_id']
    logger.info(f"👁️ POST /api/notifications/{notification_id}/read - User {user_id}")

    try:
        from .lease_management.notifications import mark_notification_read
        success = mark_notification_read(notification_id, user_id)

        if success:
            return jsonify({'success': True, 'message': 'Notification marked as read'})
        else:
            return jsonify({'success': False, 'error': 'Notification not found or access denied'}), 404
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/notifications/<int:notification_id>/dismiss', methods=['POST'])
@require_login
def dismiss_user_notification(notification_id):
    """Dismiss a notification"""
    user_id = session['user_id']
    logger.info(f"🗑️ POST /api/notifications/{notification_id}/dismiss - User {user_id}")

    try:
        from .lease_management.notifications import dismiss_notification
        success = dismiss_notification(notification_id, user_id)

        if success:
            return jsonify({'success': True, 'message': 'Notification dismissed'})
        else:
            return jsonify({'success': False, 'error': 'Notification not found or access denied'}), 404
    except Exception as e:
        logger.error(f"Error dismissing notification: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/notifications/dismiss_all', methods=['POST'])
@require_login
def dismiss_all_user_notifications():
    """Dismiss all notifications for current user"""
    user_id = session['user_id']
    logger.info(f"🗑️ POST /api/notifications/dismiss_all - User {user_id}")

    try:
        from .lease_management.notifications import dismiss_all_notifications
        count = dismiss_all_notifications(user_id)

        return jsonify({
            'success': True,
            'message': f'Dismissed {count} notifications',
            'dismissed_count': count
        })
    except Exception as e:
        logger.error(f"Error dismissing all notifications: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
