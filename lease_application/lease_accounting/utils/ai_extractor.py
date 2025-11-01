"""
AI-Assisted Lease Data Extraction using Google Gemini API
Extracts lease information from PDF using AI with bounding box coordinates
"""

import json
import re
import os
from typing import Dict, Optional, List
from datetime import datetime

try:
    import google.generativeai as genai
    try:
        from google.generativeai.types import GenerateContentConfig, HarmCategory, HarmBlockThreshold
    except ImportError:
        # Some versions may not have these types
        GenerateContentConfig = None
        HarmCategory = None
        HarmBlockThreshold = None
    HAS_GEMINI = True
except (ImportError, AttributeError, ModuleNotFoundError) as e:
    # Handle import errors gracefully
    HAS_GEMINI = False
    GenerateContentConfig = None
    HarmCategory = None
    HarmBlockThreshold = None
    genai = None


# Configuration
MAX_TEXT_LENGTH = 80000  # Limit text length for AI processing


def extract_lease_info_from_pdf(pdf_path: str, api_key: Optional[str] = None) -> Dict:
    """
    Extract lease information from PDF directly using Google Gemini AI
    Returns extracted fields with bounding box coordinates
    
    Args:
        pdf_path: Path to PDF file
        api_key: Google Gemini API key (if None, tries env var)
        
    Returns:
        Dictionary with extracted lease fields and bounding boxes
    """
    if not HAS_GEMINI:
        return {"error": "Google Gemini API not installed. Install with: pip install google-generativeai"}
    
    if not api_key:
        api_key = os.getenv('GOOGLE_AI_API_KEY')
    
    if not api_key:
        return {"error": "Google Gemini API key not provided"}
    
    if not os.path.exists(pdf_path):
        return {"error": f"PDF file not found: {pdf_path}"}
    
    try:
        # Get actual PDF page dimensions for accurate coordinate conversion
        pdf_dimensions = _get_pdf_page_dimensions(pdf_path)
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # List models and find a working one
        try:
            models = list(genai.list_models())
        except Exception as e:
            print(f'Could not list models: {e}')
            models = []

        # Official model names to try, in recommended order (updated for Gemini 2.x API)
        model_names = [
            'models/gemini-2.5-pro',        # Pro model is better for structured output
            'models/gemini-2.5-flash',      # Latest stable Flash model
            'models/gemini-2.0-flash',      # Stable Flash model
            'models/gemini-2.0-flash-001',  # Flash 001 variant
            'models/gemini-flash-latest',   # Latest flash (fallback)
        ]
        model = None
        model_success = None
        errors = {}
        for model_name in model_names:
            try:
                print(f'Trying Gemini model: {model_name}')
                m = genai.GenerativeModel(model_name)
                _ = m.generate_content('test')  # dummy call
                print(f'✅ Successfully using: {model_name}')
                model = m
                model_success = model_name
                break
            except Exception as e:
                print(f'❌ {model_name} failed: {e}')
                errors[model_name] = str(e)
        if not model:
            return {
                'error': 'No valid Gemini model found for your API key. See model list.',
                'model_attempts': model_names,
                'errors': errors,
                'available_models': [m.name for m in models],
            }
        
        # Read PDF as bytes
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Create PDF part for Gemini
        pdf_part = {
            "mime_type": "application/pdf",
            "data": pdf_data
        }
        
        # Define extraction prompt with coordinate requirements
        extraction_prompt = _create_extraction_prompt_with_coordinates()
        
        # Define response schema for structured output with bounding boxes
        response_schema = _get_extraction_response_schema()
        
        # Configure generation with JSON schema
        generation_config = {
            "temperature": 0.1,  # Lower temperature for more consistent structured output
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }
        
        # Generate response with structured output
        try:
            # Try using structured output (Gemini 2.x supports response_mime_type and response_schema)
            try:
                # Check if model supports structured output
                response_schema = _get_extraction_response_schema()
                
                # Use generate_content with structured output if supported
                response = model.generate_content(
                    contents=[pdf_part, extraction_prompt],
                    generation_config={
                        **generation_config,
                        "response_mime_type": "application/json",
                        "response_schema": response_schema
                    }
                )
            except (TypeError, AttributeError, ValueError) as schema_error:
                # If structured output not supported, use regular generation with prompt
                print(f"⚠️ Structured output not supported, using prompt-based extraction: {schema_error}")
                response = model.generate_content(
                    [pdf_part, extraction_prompt],
                    generation_config=generation_config
                )
            
            # Try to parse structured JSON response
            response_text = response.text
            
            # Parse JSON from response with actual PDF dimensions
            return _parse_ai_response_with_coordinates(response_text, pdf_dimensions)
            
        except Exception as api_error:
            # Fallback: try without structured output if schema not supported
            print(f"⚠️ Structured output failed, trying without schema: {api_error}")
            try:
                response = model.generate_content([pdf_part, extraction_prompt])
                response_text = response.text
                return _parse_ai_response_with_coordinates(response_text, pdf_dimensions)
            except Exception as fallback_error:
                return {"error": f"AI extraction failed: {str(fallback_error)}"}
        
    except Exception as e:
        return {"error": f"AI extraction failed: {str(e)}"}


def extract_lease_info_from_text(text: str, api_key: Optional[str] = None) -> Dict:
    """
    Extract lease information from text using Google Gemini AI
    
    Args:
        text: Extracted text from PDF
        api_key: Google Gemini API key (if None, tries env var)
        
    Returns:
        Dictionary with extracted lease fields
    """
    if not HAS_GEMINI:
        return {"error": "Google Gemini API not installed. Install with: pip install google-generativeai"}
    
    if not api_key:
        api_key = os.getenv('GOOGLE_AI_API_KEY')
    
    if not api_key:
        return {"error": "Google Gemini API key not provided"}
    
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # List models and print them for debugging
        try:
            models = list(genai.list_models())
            print('Available Gemini models:')
            for m in models:
                print(f'- {m.name}')
        except Exception as e:
            print(f'Could not list models: {e}')
            models = []

        # Official model names to try, in recommended order (updated for Gemini 2.x API)
        model_names = [
            'models/gemini-2.5-flash',      # Latest stable Flash model
            'models/gemini-2.0-flash',      # Stable Flash model
            'models/gemini-2.5-pro',        # Latest stable Pro model
            'models/gemini-2.0-flash-001',  # Flash 001 variant
            'models/gemini-flash-latest',   # Latest flash (fallback)
        ]
        model = None
        model_success = None
        errors = {}
        for model_name in model_names:
            try:
                print(f'Trying Gemini model: {model_name}')
                m = genai.GenerativeModel(model_name)
                _ = m.generate_content('test')  # dummy call
                print(f'✅ Successfully using: {model_name}')
                model = m
                model_success = model_name
                break
            except Exception as e:
                print(f'❌ {model_name} failed: {e}')
                errors[model_name] = str(e)
        if not model:
            return {
                'error': 'No valid Gemini model found for your API key. See model list.',
                'model_attempts': model_names,
                'errors': errors,
                'available_models': [m.name for m in models],
            }
        
        # Truncate text if too long
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH]
        
        # Create extraction prompt
        prompt = _create_extraction_prompt(text)
        
        # Generate response
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Parse JSON from response
        return _parse_ai_response(response_text)
        
    except Exception as e:
        return {"error": f"AI extraction failed: {str(e)}"}


def _create_extraction_prompt_with_coordinates() -> str:
    """Create the AI prompt for extracting lease information with bounding box coordinates"""
    return """You are an expert document extraction and analysis system. Your task is to accurately locate and extract specific fields from the provided PDF document. For every field you extract, you must also provide its precise location on the page.

**Crucial Output Requirement:**
1. Provide the extracted text value.
2. Provide the page number where the text is found (1-based).
3. Provide the bounding box (bbox) coordinates of the text. The bounding box must be an array of four integers in the format: [x_min, y_min, x_max, y_max]. These coordinates should be normalized to a 0 to 1000 scale relative to the page size, where (0, 0) is the bottom-left corner and (1000, 1000) is the top-right corner.

Extract the following lease fields from the document:
- description: lease description or title
- asset_class: asset category/type
- asset_id_code: asset identifier/code (if available)
- lease_start_date: start date in YYYY-MM-DD format
- end_date: end date in YYYY-MM-DD format
- agreement_date: agreement date in YYYY-MM-DD format
- termination_date: termination date in YYYY-MM-DD format (if available)
- first_payment_date: first payment date in YYYY-MM-DD format
- tenure: lease term in months (integer)
- frequency_months: payment frequency in months (integer, default 1)
- day_of_month: payment day of month (string, default '1')
- rental_1: first rental amount (number)
- rental_2: second rental amount (number, if available)
- currency: currency code like USD, INR
- borrowing_rate: interest rate as percentage (number)
- compound_months: compounding frequency in months (integer, default 12)
- security_deposit: security deposit amount (number, if available)
- esc_freq_months: escalation frequency in months (integer, if available)
- escalation_percent: escalation percentage (number, if available)
- escalation_start_date: escalation start date in YYYY-MM-DD format (if available)
- lease_incentive: lease incentive amount (number, if available)
- initial_direct_expenditure: initial direct costs (number, if available)
- finance_lease: Yes or No (string, default 'No')
- sublease: Yes or No (string, default 'No')
- bargain_purchase: Yes or No (string, default 'No')
- title_transfer: Yes or No (string, default 'No')
- practical_expedient: Yes or No (string, default 'No')
- short_term_ifrs: Yes or No (string, default 'No')
- manual_adj: Yes or No (string, default 'No')
- additional_info: any extra information (if available)

For each field found, provide:
- field_name: The field identifier
- extracted_value: The actual text/number extracted
- page_number: Page where the field is found (1-based)
- bbox_normalized: [x_min, y_min, x_max, y_max] normalized to 0-1000 scale (bottom-left origin)

Important: Only include fields that you can actually find in the document. Return null or omit fields that are not present."""


def _get_extraction_response_schema() -> dict:
    """Get JSON schema for structured extraction response with bounding boxes"""
    return {
        "type": "object",
        "properties": {
            "extracted_fields": {
                "type": "array",
                "description": "A list of all extracted fields and their locations.",
                "items": {
                    "type": "object",
                    "properties": {
                        "field_name": {
                            "type": "string",
                            "description": "The name of the data field (e.g., 'description', 'lease_start_date', 'rental_1')."
                        },
                        "extracted_value": {
                            "type": "string",
                            "description": "The actual text value extracted from the PDF."
                        },
                        "page_number": {
                            "type": "integer",
                            "description": "The 1-based index of the page where the text is located."
                        },
                        "bbox_normalized": {
                            "type": "array",
                            "description": "Bounding box coordinates in [x_min, y_min, x_max, y_max] format, normalized to a 0-1000 scale (bottom-left origin).",
                            "items": {
                                "type": "number"
                            },
                            "minItems": 4,
                            "maxItems": 4
                        }
                    },
                    "required": [
                        "field_name",
                        "extracted_value",
                        "page_number",
                        "bbox_normalized"
                    ]
                }
            }
        },
        "required": [
            "extracted_fields"
        ]
    }


def _get_pdf_page_dimensions(pdf_path: str) -> Dict[int, Dict[str, float]]:
    """
    Get actual PDF page dimensions for accurate coordinate conversion
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dictionary mapping page_number -> {width, height} in PDF points
        Example: {1: {'width': 595.0, 'height': 842.0}, ...}
    """
    dimensions = {}
    
    # Try pdfplumber first (most reliable)
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                width = page.width  # PDF points
                height = page.height  # PDF points
                dimensions[page_num] = {'width': float(width), 'height': float(height)}
        if dimensions:
            print(f"✅ Got PDF dimensions from pdfplumber: {dimensions}")
            return dimensions
    except Exception as e:
        print(f"⚠️ Could not get dimensions from pdfplumber: {e}")
    
    # Fallback: Try pypdf
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        for page_num, page in enumerate(reader.pages, start=1):
            # pypdf mediabox is in points
            mediabox = page.mediabox
            width = float(mediabox.width) - float(mediabox.left)
            height = float(mediabox.height) - float(mediabox.bottom)
            dimensions[page_num] = {'width': width, 'height': height}
        if dimensions:
            print(f"✅ Got PDF dimensions from pypdf: {dimensions}")
            return dimensions
    except Exception as e:
        print(f"⚠️ Could not get dimensions from pypdf: {e}")
    
    # Default to A4 if unable to get dimensions
    print(f"⚠️ Using default A4 dimensions (595 x 842 points)")
    return {1: {'width': 595.0, 'height': 842.0}}


def _parse_ai_response_with_coordinates(response_text: str, pdf_dimensions: Optional[Dict[int, Dict[str, float]]] = None) -> Dict:
    """Parse AI response with coordinates and convert to extraction format"""
    try:
        # Try to find JSON in markdown code blocks
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON without markdown
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response_text
        
        # Parse JSON
        response_data = json.loads(json_str)
        
        # Convert structured response to extraction format
        extracted_data = {}
        field_metadata = {}  # Store metadata with bounding boxes
        
        if 'extracted_fields' in response_data:
            for field_info in response_data['extracted_fields']:
                field_name = field_info.get('field_name')
                extracted_value = field_info.get('extracted_value')
                page_number = field_info.get('page_number', 1)
                bbox_normalized = field_info.get('bbox_normalized', [])
                
                if field_name and extracted_value:
                    # Store the extracted value
                    extracted_data[field_name] = extracted_value
                    
                    # Convert normalized bbox (0-1000, bottom-left origin) to PDF points (top-left origin)
                    # Normalized: (0,0) = bottom-left, (1000,1000) = top-right
                    # PDF points: (0,0) = bottom-left, but we need top-left for highlighting
                    # Use actual PDF dimensions if available, fallback to A4
                    page_dims = pdf_dimensions.get(page_number) if pdf_dimensions else None
                    if not page_dims:
                        # Default to A4 if dimensions not available for this page
                        page_dims = {'width': 595.0, 'height': 842.0}
                    pdf_bbox = _convert_normalized_bbox_to_pdf_points(
                        bbox_normalized, 
                        page_number,
                        pdf_width_points=page_dims['width'],
                        pdf_height_points=page_dims['height']
                    )
                    
                    # Store metadata with bounding boxes
                    if field_name not in field_metadata:
                        field_metadata[field_name] = {
                            'field_name': field_name,
                            'extracted_value': extracted_value,
                            'page_number': page_number,
                            'bounding_boxes': []
                        }
                    
                    field_metadata[field_name]['bounding_boxes'].append(pdf_bbox)
        
        # If no fields were extracted from structured format, try to parse as regular extraction
        # This handles cases where AI returns JSON but not in the expected structured format
        if not extracted_data and isinstance(response_data, dict):
            # Check if response_data has direct field names (fallback parsing)
            for key, value in response_data.items():
                if key != 'extracted_fields' and value is not None and value != '':
                    extracted_data[key] = value
        
        # Clean and validate extracted data
        cleaned_data = _clean_extracted_data(extracted_data)
        
        # Add metadata to response (but don't include it in the main data structure)
        # Metadata is stored separately and used later for highlighting
        # Store it in a separate key that won't interfere with field population
        if field_metadata:
            cleaned_data['_metadata'] = field_metadata
        
        # Return cleaned data (frontend expects field values directly)
        # Remove _metadata from the count for field population purposes
        return cleaned_data
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse AI response as JSON: {e}", "raw_response": response_text}
    except Exception as e:
        return {"error": f"Failed to process AI response: {e}", "raw_response": response_text}


def _convert_normalized_bbox_to_pdf_points(
    bbox_normalized: List[float], 
    page_number: int = 1,
    pdf_width_points: float = 595.0,
    pdf_height_points: float = 842.0
) -> List[float]:
    """
    Convert normalized bbox (0-1000 scale, bottom-left origin) to PDF points (top-left origin)
    
    Args:
        bbox_normalized: [x_min, y_min, x_max, y_max] in normalized 0-1000 scale (bottom-left origin)
        page_number: Page number for reference (not used in conversion, but kept for consistency)
        pdf_width_points: Actual PDF page width in points (defaults to A4 width: 595.0)
        pdf_height_points: Actual PDF page height in points (defaults to A4 height: 842.0)
        
    Returns:
        [x0, y0, x1, y1] in PDF points (top-left origin, like pdfplumber/pypdf)
    """
    if not bbox_normalized or len(bbox_normalized) < 4:
        return [0, 0, 0, 0]
    
    x_min_norm, y_min_norm, x_max_norm, y_max_norm = bbox_normalized[:4]
    
    # Convert normalized (0-1000) to PDF points
    # Normalized: (0,0) = bottom-left, (1000,1000) = top-right
    # PDF points (pdfplumber): (0,0) = top-left, (width, height) = bottom-right
    
    # X coordinate: same direction, just scale
    x0_points = (x_min_norm / 1000.0) * pdf_width_points
    x1_points = (x_max_norm / 1000.0) * pdf_width_points
    
    # Y coordinate: flip vertically (normalized uses bottom-left, PDF uses top-left)
    # In normalized: y=0 is bottom, y=1000 is top
    # In PDF points: y=0 is top, y=height is bottom
    # So: y_pdf = pdf_height - (y_norm / 1000.0 * pdf_height)
    y0_points = pdf_height_points - ((y_max_norm / 1000.0) * pdf_height_points)  # max_norm becomes top y
    y1_points = pdf_height_points - ((y_min_norm / 1000.0) * pdf_height_points)  # min_norm becomes bottom y
    
    return [x0_points, y0_points, x1_points, y1_points]


def _create_extraction_prompt(text: str) -> str:
    """Create the AI prompt for extracting lease information (text-based fallback)"""
    return f"""Extract lease information from this document and return ONLY a JSON object with the following fields:

{{
  "description": "lease description or title (string)",
  "asset_class": "asset category/type (string)",
  "asset_id_code": "asset identifier/code (string or null)",
  "lease_start_date": "start date in YYYY-MM-DD format (string or null)",
  "end_date": "end date in YYYY-MM-DD format (string or null)",
  "agreement_date": "agreement date in YYYY-MM-DD format (string or null)",
  "termination_date": "termination date in YYYY-MM-DD format (string or null)",
  "first_payment_date": "first payment date in YYYY-MM-DD format (string or null)",
  "tenure": "lease term in months (integer or null)",
  "frequency_months": "payment frequency in months (integer, default 1)",
  "day_of_month": "payment day of month (string, default '1')",
  "rental_1": "first rental amount (number or null)",
  "rental_2": "second rental amount (number or null)",
  "currency": "currency code like USD, INR (string or null)",
  "borrowing_rate": "interest rate as percentage (number or null)",
  "compound_months": "compounding frequency in months (integer, default 12)",
  "security_deposit": "security deposit amount (number or null)",
  "esc_freq_months": "escalation frequency in months (integer or null)",
  "escalation_percent": "escalation percentage (number or null)",
  "escalation_start_date": "escalation start date in YYYY-MM-DD format (string or null)",
  "lease_incentive": "lease incentive amount (number or null)",
  "initial_direct_expenditure": "initial direct costs (number or null)",
  "finance_lease": "Yes or No (string, default 'No')",
  "sublease": "Yes or No (string, default 'No')",
  "bargain_purchase": "Yes or No (string, default 'No')",
  "title_transfer": "Yes or No (string, default 'No')",
  "practical_expedient": "Yes or No (string, default 'No')",
  "short_term_ifrs": "Yes or No (string, default 'No')",
  "manual_adj": "Yes or No (string, default 'No')",
  "additional_info": "any extra information (string or null)"
}}

Document Text:
{text}

Important: Return ONLY the JSON object, no explanation or markdown formatting."""


def _parse_ai_response(response_text: str) -> Dict:
    """Parse AI response and extract JSON"""
    try:
        # Try to find JSON in markdown code blocks
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON without markdown
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response_text
        
        # Parse JSON
        extracted_data = json.loads(json_str)
        
        # Validate and clean up the data
        return _clean_extracted_data(extracted_data)
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse AI response as JSON: {e}", "raw_response": response_text}
    except Exception as e:
        return {"error": f"Failed to process AI response: {e}"}


def _clean_extracted_data(data: Dict) -> Dict:
    """Clean and validate extracted data"""
    cleaned = {}
    
    # String fields
    string_fields = [
        'description', 'asset_class', 'asset_id_code', 'currency', 'day_of_month',
        'finance_lease', 'sublease', 'bargain_purchase', 'title_transfer',
        'practical_expedient', 'short_term_ifrs', 'manual_adj', 'additional_info'
    ]
    
    for field in string_fields:
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            cleaned[field] = value.strip()
        elif field in ['finance_lease', 'sublease', 'bargain_purchase', 'title_transfer',
                       'practical_expedient', 'short_term_ifrs', 'manual_adj']:
            # Ensure Yes/No fields have proper values
            cleaned[field] = 'Yes' if str(value).lower() in ['yes', 'true', '1', 'on'] else 'No'
        else:
            cleaned[field] = None
    
    # Number fields
    number_fields = [
        'tenure', 'frequency_months', 'rental_1', 'rental_2', 'borrowing_rate',
        'compound_months', 'security_deposit', 'esc_freq_months', 'escalation_percent',
        'lease_incentive', 'initial_direct_expenditure'
    ]
    
    for field in number_fields:
        value = data.get(field)
        try:
            if value is not None:
                cleaned[field] = float(value)
            else:
                cleaned[field] = None
        except (ValueError, TypeError):
            cleaned[field] = None
    
    # Date fields
    date_fields = [
        'lease_start_date', 'end_date', 'agreement_date', 'termination_date',
        'first_payment_date', 'escalation_start_date'
    ]
    
    for field in date_fields:
        value = data.get(field)
        if value:
            cleaned[field] = _parse_date_field(value)
        else:
            cleaned[field] = None
    
    return cleaned


def _parse_date_field(value) -> Optional[str]:
    """Parse date field to YYYY-MM-DD format"""
    if not value:
        return None
    
    # Try various date formats
    date_formats = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%Y/%m/%d',
        '%m-%d-%Y',
        '%d-%m-%Y',
    ]
    
    for fmt in date_formats:
        try:
            dt = datetime.strptime(str(value).strip(), fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    return None

