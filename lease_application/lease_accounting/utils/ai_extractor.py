"""
AI-Assisted Lease Data Extraction using Google Gemini API
Extracts lease information from PDF using AI with bounding box coordinates
"""

import json
import re
import os
from typing import Dict, Optional, List, Any
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
    return """You are an expert lease document extraction system specializing in IFRS 16 and ASC 842 lease accounting. Extract lease information from the PDF document with precise location coordinates.

**CRITICAL EXTRACTION GUIDELINES:**
1. Read the entire document carefully - lease information may be spread across multiple pages
2. Look for common lease terminology: "Lessee", "Lessor", "Commencement Date", "Rent", "Payment", "Term", "Rate"
3. Extract dates in YYYY-MM-DD format (convert from any format found in document)
4. Extract monetary values as pure numbers (remove currency symbols, commas, spaces)
5. Extract percentages as numbers (remove % symbol)
6. For each extracted value, identify its exact location on the page

**REQUIRED FIELDS TO EXTRACT:**

**Basic Information:**
- description: Full lease agreement title or description (e.g., "Office Lease Agreement", "Warehouse Lease")
- company_name: Name of the Lessee (tenant) company
- counterparty: Name of the Lessor (landlord) company
- asset_class: Type of asset (Building, Land, Vehicle, Equipment, etc.)
- asset_id_code: Asset identifier or code if mentioned
- currency: Currency code (USD, EUR, INR, GBP, etc.)

**Key Dates (convert to YYYY-MM-DD format):**
- lease_start_date: Lease commencement/start date (look for: "Commencement Date", "Start Date", "Inception Date")
- end_date: Lease expiration/end date (look for: "Expiration Date", "End Date", "Termination Date")
- agreement_date: Date when agreement was signed (look for: "Agreement Date", "Execution Date", "Signed Date")
- first_payment_date: First rental payment date (look for: "First Payment Date", "Initial Payment Date")
- termination_date: Early termination date (if specified)

**Financial Terms:**
- rental_1: Base monthly/annual rental amount (extract the primary rent amount, remove currency symbols)
- rental_2: Additional or secondary rental amount (if different rent periods exist)
- rental_amount: Same as rental_1 if rental_1 not found (use whichever field name matches)
- borrowing_rate: Incremental Borrowing Rate (IBR) as percentage number (look for: "IBR", "Discount Rate", "Borrowing Rate")
- ibr: Same as borrowing_rate (use if borrowing_rate not found)
- security_deposit: Security deposit amount if mentioned
- lease_incentive: Any lease incentives or free rent periods (convert to monetary value if time-based)
- initial_direct_expenditure: Initial direct costs (legal fees, commissions, etc.)

**Lease Term and Frequency:**
- tenure: Total lease term in months (calculate from start to end date if not explicitly stated)
- frequency_months: Payment frequency (1=Monthly, 3=Quarterly, 6=Semi-annual, 12=Annual)
- day_of_month: Day of month when payments are due (usually 1st or last day)
- compound_months: Compounding frequency for discount rate (usually matches payment frequency)

**Escalation Details (if applicable):**
- escalation_percent: Annual rent escalation percentage (look for: "Escalation", "Increase", "Rent Review")
- escalation_start_date: Date when escalation begins
- esc_freq_months: How often escalation applies (typically 12 months)

**Classification Flags:**
- finance_lease: "Yes" if lease meets finance lease criteria, otherwise "No"
- sublease: "Yes" if this is a sublease, otherwise "No"

**OUTPUT FORMAT:**
For each field extracted, provide:
{
  "field_name": "field_identifier",
  "extracted_value": "actual_value_from_document",
  "page_number": 1,
  "bbox_normalized": [x_min, y_min, x_max, y_max]
}

Where bbox_normalized is in 0-1000 scale (bottom-left origin).

**EXTRACTION TIPS:**
- Dates: Convert "01/15/2025" to "2025-01-15", "January 15, 2025" to "2025-01-15"
- Money: "$10,000.00" becomes 10000.00, "INR 50,000" becomes 50000
- Percentages: "5.5%" becomes 5.5, "10 percent" becomes 10
- Look in headers, footers, tables, and signature blocks
- If a field appears multiple times, use the most prominent or first occurrence

Extract only fields you can confidently identify. Return null for fields not found."""


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
    return f"""Extract lease information from this document and return ONLY a JSON object.

**CRITICAL:** For each field that has a value, provide BOTH the normalized value AND the EXACT ORIGINAL TEXT as it appears in the document.

Return JSON in this format (use objects with "value" and "original_text" for each field):
{{
  "description": {{"value": "lease description or title", "original_text": "exact text from PDF"}},
  "asset_class": {{"value": "asset category/type", "original_text": "exact text from PDF"}},
  "asset_id_code": {{"value": "asset identifier/code or null", "original_text": "exact text or null"}},
  "lease_start_date": {{"value": "start date in YYYY-MM-DD format or null", "original_text": "exact date text like 'March 1, 2002' or '03/01/2002'"}},
  "end_date": {{"value": "end date in YYYY-MM-DD format or null", "original_text": "exact date text from PDF"}},
  "agreement_date": {{"value": "agreement date in YYYY-MM-DD format or null", "original_text": "exact date text from PDF"}},
  "termination_date": {{"value": "termination date in YYYY-MM-DD format or null", "original_text": "exact date text from PDF"}},
  "first_payment_date": {{"value": "first payment date in YYYY-MM-DD format or null", "original_text": "exact date text from PDF"}},
  "tenure": {{"value": "lease term in months (integer or null)", "original_text": "exact text like '180 months' or '15 years'"}},
  "frequency_months": {{"value": "payment frequency in months (integer, default 1)", "original_text": "exact text like 'monthly', 'quarterly', '12 months'"}},
  "day_of_month": {{"value": "payment day of month (string, default '1')", "original_text": "exact text from PDF"}},
  "rental_1": {{"value": "first rental amount as number (remove $, commas)", "original_text": "exact text like '$15,300' or 'USD 15300'"}},
  "rental_2": {{"value": "second rental amount as number or null", "original_text": "exact text from PDF"}},
  "currency": {{"value": "currency code like USD, INR", "original_text": "exact text from PDF"}},
  "borrowing_rate": {{"value": "interest rate as percentage number (remove %)", "original_text": "exact text like '5.5%' or '5.5 percent'"}},
  "compound_months": {{"value": "compounding frequency in months (integer, default 12)", "original_text": "exact text from PDF"}},
  "security_deposit": {{"value": "security deposit amount as number or null", "original_text": "exact text from PDF"}},
  "esc_freq_months": {{"value": "escalation frequency in months (integer or null)", "original_text": "exact text from PDF"}},
  "escalation_percent": {{"value": "escalation percentage as number (remove %)", "original_text": "exact text like '2.75%' or 'annual increase of 2.75%'"}},
  "escalation_start_date": {{"value": "escalation start date in YYYY-MM-DD format or null", "original_text": "exact date text from PDF"}},
  "lease_incentive": {{"value": "lease incentive amount as number or null", "original_text": "exact text from PDF"}},
  "initial_direct_expenditure": {{"value": "initial direct costs as number or null", "original_text": "exact text from PDF"}},
  "finance_lease": {{"value": "Yes or No (string, default 'No')", "original_text": "exact text from PDF"}},
  "sublease": {{"value": "Yes or No (string, default 'No')", "original_text": "exact text from PDF"}},
  "bargain_purchase": {{"value": "Yes or No (string, default 'No')", "original_text": "exact text from PDF"}},
  "title_transfer": {{"value": "Yes or No (string, default 'No')", "original_text": "exact text from PDF"}},
  "practical_expedient": {{"value": "Yes or No (string, default 'No')", "original_text": "exact text from PDF"}},
  "short_term_ifrs": {{"value": "Yes or No (string, default 'No')", "original_text": "exact text from PDF"}},
  "manual_adj": {{"value": "Yes or No (string, default 'No')", "original_text": "exact text from PDF"}},
  "additional_info": {{"value": "any extra information or null", "original_text": "exact text from PDF or null"}}
}}

**IMPORTANT:** 
- For "original_text", provide the EXACT text as it appears in the document (preserve formatting, spacing, punctuation)
- For dates: If PDF says "January 15, 2002", original_text should be "January 15, 2002" (not the converted YYYY-MM-DD)
- For amounts: If PDF says "$15,300.00", original_text should be "$15,300.00" (not the normalized number)
- For percentages: If PDF says "2.75%", original_text should be "2.75%" or the exact phrase containing it
- If field is not found, use null for both value and original_text

Document Text:
{text}

Important: Return ONLY the JSON object, no explanation or markdown formatting."""


def _parse_ai_response(response_text: str) -> Dict:
    """Parse AI response and extract JSON, handling both old and new formats"""
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
        raw_data = json.loads(json_str)
        
        # Check if new format with value/original_text objects
        extracted_data = {}
        original_texts = {}  # Store original texts for highlight matching
        
        for field_name, field_value in raw_data.items():
            if isinstance(field_value, dict) and 'value' in field_value:
                # New format: {"value": "...", "original_text": "..."}
                extracted_data[field_name] = field_value['value']
                original_texts[field_name] = field_value.get('original_text')
            else:
                # Old format: just the value
                extracted_data[field_name] = field_value
                original_texts[field_name] = None
        
        # Clean up the data
        cleaned_data = _clean_extracted_data(extracted_data)
        
        # Add original texts to metadata for highlight matching
        if original_texts:
            cleaned_data['_original_texts'] = original_texts
        
        return cleaned_data
        
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


# --- New function for extraction with bounding box mapping ---
def extract_and_locate_lease_data(pdf_path: str, fields_to_extract: Optional[Dict[str, str]] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Uses Gemini AI to extract structured data and then finds the 
    corresponding bounding boxes in the PDF using pdf_extractor.
    
    Args:
        pdf_path: Path to the uploaded PDF file.
        fields_to_extract: Optional dictionary of field names and their descriptions.
        api_key: Google Gemini API key (if None, tries env var).
    
    Returns:
        A dictionary containing extracted_data (key-value) and highlights (list of bboxes).
    """
    from .pdf_extractor import find_text_positions, normalize_search_text
    
    # First, extract the lease data using AI
    extracted_data = extract_lease_info_from_pdf(pdf_path, api_key)
    
    # Check for errors in extraction
    if 'error' in extracted_data:
        return {
            "extracted_data": {},
            "highlights": [],
            "error": extracted_data['error']
        }
    
    # Remove metadata from extracted_data for field population
    metadata = extracted_data.pop('_metadata', {})
    
    # Now map extracted values to bounding boxes
    highlights = []
    
    # Map each extracted field value to its bounding box in the PDF
    for field_name, value in extracted_data.items():
        if value is not None and value != "" and not isinstance(value, dict):
            # Convert value to string and normalize for search
            search_value = str(value).strip()
            
            # Skip empty values and metadata
            if not search_value or search_value.lower() in ['none', 'null', '']:
                continue
            
            # Normalize the search text
            normalized_value = normalize_search_text(search_value)
            
            # Limit search length to avoid issues with very long values
            if len(normalized_value) > 100:
                normalized_value = normalized_value[:100]
            
            # Find all positions of the value in the PDF
            try:
                matches = find_text_positions(pdf_path, normalized_value, case_sensitive=False)
                
                # Collect the first few matches for the highlight list
                for match in matches[:3]:  # Limit to top 3 matches to avoid noise
                    highlights.append({
                        "field": field_name,  # The form field this data belongs to
                        "page": match['page'],
                        "bbox": match['bbox'],  # Bounding box in pdfplumber units [x0, top, x1, bottom]
                        "text": match.get('text', search_value)
                    })
            except Exception as e:
                print(f"Warning: Could not find positions for field {field_name}: {e}")
                continue
    
    # Also check metadata for pre-computed bounding boxes from AI
    if isinstance(metadata, dict):
        for field_name, field_info in metadata.items():
            if isinstance(field_info, dict) and 'bounding_boxes' in field_info:
                page_number = field_info.get('page_number', 1)
                for bbox in field_info['bounding_boxes']:
                    if len(bbox) >= 4:
                        highlights.append({
                            "field": field_name,
                            "page": page_number,
                            "bbox": bbox[:4],  # Ensure we have exactly 4 values
                            "text": field_info.get('extracted_value', '')
                        })
    
    return {
        "extracted_data": extracted_data,
        "highlights": highlights
    }


def get_extraction_schema() -> Dict[str, str]:
    """Helper to extract field names and descriptions for use in form population."""
    # Return a mapping of field names to descriptions
    field_descriptions = {
        "agreement_title": "The title or identifier of the lease agreement.",
        "company_name": "The name of the Lessee company.",
        "counterparty": "The name of the Lessor or counterparty.",
        "lease_start_date": "The lease commencement or start date (YYYY-MM-DD format).",
        "lease_end_date": "The lease end or expiration date (YYYY-MM-DD format).",
        "rental_amount": "The base fixed periodic rental payment amount.",
        "ibr": "The Incremental Borrowing Rate (IBR) percentage.",
        "currency": "The currency code (e.g., USD, EUR).",
        "asset_class": "Asset category/type.",
        "asset_id_code": "Unique identifier or code for the leased asset.",
        "borrowing_rate": "Interest rate as percentage.",
        "rental_1": "First rental amount.",
        "rental_2": "Second rental amount (if available).",
        "frequency_months": "Payment frequency in months.",
        "day_of_month": "Payment day of month.",
        "tenure": "Lease term in months.",
    }
    return field_descriptions

