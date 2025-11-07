"""
PDF Upload and AI Extraction Backend
Handles PDF upload and AI-assisted data extraction for lease forms
"""

from flask import Blueprint, request, jsonify, session
import os
import tempfile
import logging
from pathlib import Path
from werkzeug.utils import secure_filename

try:
    from .lease_accounting.utils.pdf_extractor import extract_text_from_pdf, has_selectable_text
    from .lease_accounting.utils.ai_extractor import (
        extract_lease_info_from_text,
        extract_lease_info_from_pdf,
        HAS_GEMINI
    )
except ImportError as e:
    print(f"Warning: AI extraction modules not fully available: {e}")
    HAS_GEMINI = False
    extract_lease_info_from_pdf = None
    extract_lease_info_from_text = None

# Create blueprint
pdf_bp = Blueprint('pdf', __name__, url_prefix='/api')

logger = logging.getLogger(__name__)


@pdf_bp.route('/extract_lease_pdf', methods=['POST'])
def extract_lease_pdf():
    """
    Extract lease data from uploaded PDF using AI
    
    Expected request:
    - PDF file upload
    - Optional: Google AI API key (or use env var)
    
    Returns:
    - Extracted lease fields if successful
    - Error message if failed
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file uploaded'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Check if it's a PDF
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({
                'success': False,
                'error': 'File must be a PDF'
            }), 400
        
        # Get API key from request or environment
        api_key = request.form.get('api_key')
        if not api_key:
            api_key = os.getenv('GOOGLE_AI_API_KEY')
        
        # Check if Gemini is available
        gemini_available = HAS_GEMINI or extract_lease_info_from_pdf is not None
        
        if not api_key and gemini_available:
            return jsonify({
                'success': False,
                'error': 'Google AI API key required. Set GOOGLE_AI_API_KEY environment variable or provide in form.',
                'help': 'Get your free API key at: https://makersuite.google.com/app/apikey'
            }), 400
        
        if not gemini_available and extract_lease_info_from_text is None:
            return jsonify({
                'success': False,
                'error': 'Google Gemini AI not installed',
                'install_instructions': 'Install with: pip install google-generativeai'
            }), 400
        
        # Save uploaded file temporarily
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"upload_{file.filename}")
        
        try:
            import time
            start_time = time.time()
            logger.info(f"📥 Starting PDF extraction for: {file.filename} (size: {file.content_length} bytes)")
            
            file.save(temp_path)
            save_time = time.time()
            logger.debug(f"   ✅ File saved to temp path: {temp_path} (took {save_time - start_time:.2f}s)")
            
            # Extract text from PDF
            logger.info(f"📄 Extracting text from PDF: {file.filename}")
            pdf_extract_start = time.time()
            try:
                result = extract_text_from_pdf(temp_path)
                if isinstance(result, tuple):
                    text, status_msg = result
                else:
                    text = result
                    status_msg = ""
                
                pdf_extract_time = time.time() - pdf_extract_start
                text_length = len(text) if text else 0
                logger.info(f"📄 Text extraction completed: {text_length} characters extracted in {pdf_extract_time:.2f}s")
                logger.debug(f"   📊 Extraction method: {status_msg}")
                if text:
                    # Log preview of extracted text for debugging
                    preview = text[:200].replace('\n', ' ') if len(text) > 200 else text.replace('\n', ' ')
                    logger.debug(f"   📝 Text preview: {preview}...")
            except Exception as e:
                logger.error(f"❌ Error extracting text from PDF: {e}", exc_info=True)
                logger.debug(f"   🔍 Full error details: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f'Failed to extract text from PDF: {str(e)}',
                    'status': 'extraction_error'
                }), 400
            
            if not text:
                logger.warning(f"⚠️ No text extracted from PDF: {status_msg}")
                logger.debug(f"   🔍 This may indicate a scanned PDF or password-protected file")
                return jsonify({
                    'success': False,
                    'error': status_msg or 'Failed to extract text from PDF. The PDF may be scanned or password-protected.',
                    'status': 'no_text_extracted',
                    'status_msg': status_msg
                }), 400
            
            # Prepare text for AI (smart truncation if needed)
            from .lease_accounting.utils.ai_extractor import MAX_TEXT_LENGTH
            original_text_length = len(text)
            if len(text) > MAX_TEXT_LENGTH:
                logger.debug(f"   ✂️ Text too long ({len(text)} chars), truncating to {MAX_TEXT_LENGTH} chars")
                # Smart truncation happens in ai_extractor
            else:
                logger.debug(f"   ✅ Text length within limit: {len(text)} chars (max: {MAX_TEXT_LENGTH})")
            
            # Extract lease info using AI
            logger.info(f"🤖 Starting AI extraction (text length: {original_text_length} chars, truncated: {len(text[:MAX_TEXT_LENGTH])} chars)")
            ai_extract_start = time.time()
            try:
                # Start with text-based extraction (more reliable)
                if extract_lease_info_from_text is not None:
                    logger.debug(f"   🔑 API key provided: {'Yes' if api_key else 'No (using env var)'}")
                    logger.debug(f"   📤 Sending text to AI model...")
                    extracted_data = extract_lease_info_from_text(text, api_key)
                    
                    ai_extract_time = time.time() - ai_extract_start
                    logger.debug(f"   ⏱️ AI extraction took {ai_extract_time:.2f}s")
                    
                    # Check if text extraction succeeded
                    if 'error' in extracted_data:
                        error_msg = extracted_data.get('error', 'Text extraction failed')
                        logger.error(f"❌ AI returned error: {error_msg}")
                        logger.debug(f"   🔍 Full AI response: {extracted_data}")
                        raise Exception(error_msg)
                    
                    # Log extracted fields
                    extracted_fields = {k: v for k, v in extracted_data.items() if k != '_metadata'}
                    field_count = len(extracted_fields)
                    logger.info(f"✅ AI extraction successful: {field_count} fields extracted in {ai_extract_time:.2f}s")
                    
                    # Log key fields for debugging
                    key_fields = ['description', 'lease_start_date', 'end_date', 'rental_1', 'currency', 'asset_class']
                    for field in key_fields:
                        if field in extracted_fields and extracted_fields[field]:
                            logger.debug(f"   ✅ {field}: {extracted_fields[field]}")
                    
                    # Log fields that failed to extract
                    empty_fields = [k for k, v in extracted_fields.items() if not v or v == '']
                    if empty_fields:
                        logger.debug(f"   ⚠️ Empty/missing fields: {', '.join(empty_fields[:10])}{'...' if len(empty_fields) > 10 else ''}")
                else:
                    raise Exception("Text-based extraction is not available. Please install google-generativeai.")
                
            except Exception as ai_error:
                ai_extract_time = time.time() - ai_extract_start
                logger.error(f"❌ AI extraction failed after {ai_extract_time:.2f}s: {ai_error}", exc_info=True)
                logger.debug(f"   🔍 Text length sent: {len(text[:MAX_TEXT_LENGTH])} chars")
                logger.debug(f"   🔍 Has API key: {bool(api_key)}")
                return jsonify({
                    'success': False,
                    'error': f'AI extraction failed: {str(ai_error)}',
                    'extracted_text_length': len(text),
                    'has_api_key': bool(api_key)
                }), 500
            
            # Validate extracted_data is a dict
            if not isinstance(extracted_data, dict):
                logger.error(f"❌ AI extraction returned invalid data type: {type(extracted_data)}")
                logger.debug(f"   🔍 Received data: {extracted_data}")
                return jsonify({
                    'success': False,
                    'error': 'AI extraction returned invalid data',
                    'extracted_text_length': len(text),
                    'has_api_key': bool(api_key)
                }), 500
            
            if 'error' in extracted_data:
                logger.error(f"❌ AI extraction error in response: {extracted_data['error']}")
                return jsonify({
                    'success': False,
                    'error': extracted_data['error'],
                    'extracted_text_length': len(text),
                    'has_api_key': bool(api_key)
                }), 400
            
            total_time = time.time() - start_time
            extraction_method = 'text-based' if has_selectable_text(temp_path) else 'OCR'
            field_count = len([k for k in extracted_data.keys() if k != '_metadata'])
            
            logger.info(f"✅ Complete extraction successful in {total_time:.2f}s")
            logger.debug(f"   📊 Summary:")
            logger.debug(f"      - PDF size: {file.content_length} bytes")
            logger.debug(f"      - Text extracted: {len(text)} chars")
            logger.debug(f"      - Extraction method: {extraction_method}")
            logger.debug(f"      - Fields extracted: {field_count}")
            logger.debug(f"      - Time breakdown: Total={total_time:.2f}s, PDF extraction={pdf_extract_time:.2f}s, AI processing={ai_extract_time:.2f}s")
            
            response_data = {
                'success': True,
                'data': extracted_data,
                'metadata': {
                    'filename': file.filename,
                    'text_length': len(text),
                    'extraction_method': extraction_method,
                    'processing_time': round(total_time, 2)
                }
            }
            
            return jsonify(response_data)
            
        finally:
            # Clean up temp file
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.debug(f"   🗑️ Cleaned up temp file: {temp_path}")
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Could not cleanup temp file: {cleanup_error}")
        
    except Exception as e:
        logger.error(f"❌ PDF extraction error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Internal error: {str(e)}'
        }), 500

