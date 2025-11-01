"""
PDF Text Extraction Utilities
Extracts text from PDF files (text-based or scanned images)
Uses pdfplumber and pypdf (open-source) instead of PyMuPDF
"""

import os
import tempfile
import re
from typing import Optional, Tuple

# Try to import pdfplumber (open-source)
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

# Try to import pypdf (open-source)
try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

# Fallback OCR support
try:
    from pdf2image import convert_from_path
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


def extract_text_from_pdf(pdf_path: str) -> Tuple[Optional[str], str]:
    """
    Extract text from PDF file
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Tuple of (extracted_text, status_message)
    """
    if not os.path.exists(pdf_path):
        return None, "PDF file not found"
    
    # Try text-based extraction first (faster) - using pdfplumber
    if HAS_PDFPLUMBER:
        try:
            text = _extract_text_pdfplumber(pdf_path)
            if text and text.strip():
                return text, "Text extracted successfully from text-based PDF"
        except Exception as e:
            print(f"pdfplumber extraction failed: {e}")
    else:
        print("pdfplumber not available")
    
    # Try pypdf as fallback
    if HAS_PYPDF:
        try:
            text = _extract_text_pypdf(pdf_path)
            if text and text.strip():
                return text, "Text extracted successfully from text-based PDF (pypdf)"
        except Exception as e:
            print(f"pypdf extraction failed: {e}")
    else:
        print("pypdf not available")
    
    # Fall back to OCR for scanned PDFs
    if HAS_OCR:
        try:
            text = _extract_text_ocr(pdf_path)
            if text and text.strip():
                return text, "Text extracted successfully from scanned PDF (OCR)"
        except Exception as e:
            print(f"OCR extraction failed: {e}")
    else:
        print("OCR not available (requires pdf2image and pytesseract)")
    
    # Provide helpful error message
    missing_libs = []
    if not HAS_PDFPLUMBER:
        missing_libs.append("pdfplumber")
    if not HAS_PYPDF:
        missing_libs.append("pypdf")
    
    error_msg = "Failed to extract text from PDF."
    if missing_libs:
        error_msg += f" Missing libraries: {', '.join(missing_libs)}. Install with: pip install {' '.join(missing_libs)}"
    
    return None, error_msg


def _extract_text_pdfplumber(pdf_path: str) -> Optional[str]:
    """Extract text from text-based PDF using pdfplumber"""
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(page_text)
    return "\n".join(text_parts) if text_parts else None


def _extract_text_pypdf(pdf_path: str) -> Optional[str]:
    """Extract text from text-based PDF using pypdf (fallback)"""
    text_parts = []
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(page_text)
    except Exception as e:
        print(f"pypdf extraction error: {e}")
        return None
    return "\n".join(text_parts) if text_parts else None


def _extract_text_ocr(pdf_path: str) -> Optional[str]:
    """Extract text from scanned PDF using OCR"""
    images = convert_from_path(pdf_path)
    
    if not images:
        return None
    
    text_parts = []
    for img in images:
        text = pytesseract.image_to_string(img, config="--psm 6")
        if text.strip():
            text_parts.append(text)
    
    return "\n".join(text_parts)


def has_selectable_text(pdf_path: str) -> bool:
    """Check if PDF has selectable text"""
    # Try pdfplumber first
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text and text.strip():
                        return True
        except Exception:
            pass
    
    # Fallback to pypdf
    if HAS_PYPDF:
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                text = page.extract_text()
                if text and text.strip():
                    return True
        except Exception:
            pass
    
    return False


def extract_text_with_positions(pdf_path: str) -> Optional[dict]:
    """
    Extract text from PDF with position information (for highlighting)
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dictionary with page-wise text and position data:
        {
            'pages': [
                {
                    'page_num': int,
                    'text': str,
                    'words': [{'text': str, 'bbox': [x0, y0, x1, y1], 'page': int}]
                }
            ],
            'full_text': str
        }
    """
    if not HAS_PDFPLUMBER:
        return None
    
    try:
        result = {
            'pages': [],
            'full_text': ''
        }
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                words = page.extract_words()  # Returns list of word dicts with bbox
                
                # Convert word info to structured format
                word_list = []
                for word_info in words:
                    # pdfplumber word format: {'text': str, 'x0': float, 'y0': float, 'x1': float, 'y1': float, ...}
                    if 'text' in word_info and 'x0' in word_info:
                        word_list.append({
                            'text': word_info['text'],
                            'bbox': [word_info['x0'], word_info['y0'], word_info['x1'], word_info['y1']],
                            'page': page_num
                        })
                
                result['pages'].append({
                    'page_num': page_num,
                    'text': page_text or '',
                    'words': word_list
                })
                result['full_text'] += (page_text or '') + '\n'
        
        return result
    except Exception as e:
        print(f"Error extracting text with positions: {e}")
        return None


def find_text_positions(pdf_path: str, search_text: str, case_sensitive: bool = False, fuzzy: bool = False) -> list:
    """
    Find all occurrences of text in PDF with bounding boxes using pdfplumber.
    Bounding boxes returned are [x0, top, x1, bottom] (Top-Left Origin).
    
    Args:
        pdf_path: Path to PDF file
        search_text: Text to search for (will be normalized before search)
        case_sensitive: Whether search should be case sensitive
        
    Returns:
        List of matches with bounding boxes:
        [
            {
                'page': int,
                'bbox': [x0, top, x1, bottom],  # Top-left origin format
                'text': str
            }
        ]
    """
    if not HAS_PDFPLUMBER:
        return []
    
    matches = []
    
    # 1. Normalize Search Text for Robustness
    search_text_normalized = search_text.strip()
    if not case_sensitive:
        search_text_normalized = search_text_normalized.lower()
    
    # Normalize: replace multiple spaces/newlines with a single space
    search_text_normalized = normalize_search_text(search_text_normalized)
    
    # If text is still too long after normalization, use substring
    if len(search_text_normalized) > 100:
        search_text_normalized = search_text_normalized[:100]
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Try to find text using pdfplumber's word-based search
                # pdfplumber doesn't have a direct search method, so we iterate words
                words = page.extract_words()
                
                if not words:
                    continue
                
                # Build text string from words for searching
                page_text_parts = []
                word_spans = []  # Store word positions for mapping back
                current_pos = 0
                
                for word in words:
                    word_text = word.get('text', '')
                    if not word_text:
                        continue
                    
                    # Normalize word text for comparison
                    if not case_sensitive:
                        normalized_word = normalize_search_text(word_text).lower()
                    else:
                        normalized_word = normalize_search_text(word_text)
                    
                    # Store mapping: text position -> word bounding box
                    word_spans.append({
                        'start': current_pos,
                        'end': current_pos + len(normalized_word),
                        'bbox': [word.get('x0', 0), word.get('top', 0), word.get('x1', 0), word.get('bottom', 0)],
                        'word': word
                    })
                    
                    page_text_parts.append(normalized_word)
                    current_pos += len(normalized_word) + 1  # +1 for space
                
                # Combine into full normalized text
                full_normalized_text = ' '.join(page_text_parts)
                
                # Search for occurrences
                start_idx = 0
                while True:
                    idx = full_normalized_text.find(search_text_normalized, start_idx)
                    if idx == -1:
                        break
                    
                    # Find words that span this match
                    matching_words = []
                    for span in word_spans:
                        # Check if this word overlaps with the match
                        if span['start'] <= idx < span['end'] or idx <= span['start'] < idx + len(search_text_normalized):
                            matching_words.append(span)
                    
                    if matching_words:
                        # Calculate bounding box from matching words
                        x0 = min(w['bbox'][0] for w in matching_words)
                        top = min(w['bbox'][1] for w in matching_words)
                        x1 = max(w['bbox'][2] for w in matching_words)
                        bottom = max(w['bbox'][3] for w in matching_words)
                        
                        matches.append({
                            'page': page_num,
                            'bbox': [x0, top, x1, bottom],  # pdfplumber uses top-left origin
                            'text': search_text
                        })
                    
                    start_idx = idx + 1
                    if len(matches) >= 10:  # Limit matches per search
                        break
                
                # Strategy 2: Fuzzy matching (word-by-word) if exact match failed and fuzzy=True
                if fuzzy and len(matches) == 0 and len(search_text_normalized.split()) > 1:
                    search_words = search_text_normalized.split()
                    # Try to find words in sequence (allowing gaps)
                    for i, search_word in enumerate(search_words):
                        if len(search_word) < 2:
                            continue
                        word_idx = full_normalized_text.find(search_word)
                        if word_idx != -1:
                            # Find all words around this match
                            for span in word_spans:
                                if span['start'] <= word_idx < span['end']:
                                    # Found a matching word
                                    if i == 0:  # First word, use this as anchor
                                        matches.append({
                                            'page': page_num,
                                            'bbox': [span['bbox'][0], span['bbox'][1], span['bbox'][2], span['bbox'][3]],
                                            'text': span['word'].get('text', search_word)
                                        })
                                    break
                            if matches:
                                break  # Stop after first match in fuzzy mode
        
        return matches
    except Exception as e:
        print(f"Error finding text positions with pdfplumber: {e}")
        return []


def normalize_search_text(text: str) -> str:
    """
    Normalize search text for better matching:
    - Strip whitespace
    - Replace multiple spaces/newlines with single space
    - Remove leading/trailing whitespace
    """
    if not text:
        return ""
    
    # Convert to string and strip
    text = str(text).strip()
    
    # Replace multiple spaces and newlines with single space
    text = re.sub(r'\s+', ' ', text)
    
    return text


def find_bbox_for_text_position(words: list, char_start: int, char_length: int, page_height: float, case_sensitive: bool = False) -> Optional[list]:
    """
    Find bounding box for text position by matching character positions with word positions
    
    This is approximate - we try to find words that correspond to the text substring
    """
    if not words:
        return None
    
    # Build character-to-word mapping
    current_char = 0
    matching_words = []
    
    # Normalize all words for comparison
    normalized_words = []
    for word in words:
        word_text = word.get('text', '')
        if not case_sensitive:
            normalized_word = normalize_search_text(word_text).lower()
        else:
            normalized_word = normalize_search_text(word_text)
        normalized_words.append(normalized_word)
    
    # Try to find words that match the substring we're looking for
    # This is a heuristic approach
    text_chars = 0
    word_start_idx = None
    
    for i, word in enumerate(words):
        word_text = word.get('text', '')
        if not word_text:
            continue
        
        normalized_word = normalized_words[i]
        
        # Check if this word starts the match
        if current_char <= char_start < current_char + len(normalized_word):
            word_start_idx = i
            matching_words = [word]
            break
        
        current_char += len(normalized_word) + 1  # +1 for space
    
    # If we found a starting word, try to collect more words for the full match
    if word_start_idx is not None:
        collected_length = len(normalized_words[word_start_idx])
        
        for i in range(word_start_idx + 1, len(words)):
            if collected_length >= char_length:
                break
            
            word = words[i]
            normalized_word = normalized_words[i]
            matching_words.append(word)
            collected_length += len(normalized_word) + 1
        
        # Calculate combined bounding box
        if matching_words:
            x0 = min(w.get('x0', 0) for w in matching_words)
            y0 = min(w.get('y0', 0) for w in matching_words)
            x1 = max(w.get('x1', 0) for w in matching_words)
            y1 = max(w.get('y1', 0) for w in matching_words)
            
            # pdfplumber uses top-left origin, return as [x0, y0, x1, y1]
            return [x0, y0, x1, y1]
    
    # Fallback: return bounding box of first word if exact match not found
    # Try substring search in individual words
    for word in words:
        word_text = word.get('text', '')
        normalized_word = normalize_search_text(word_text)
        if not case_sensitive:
            normalized_word = normalized_word.lower()
        
        # Check if search text appears in this word (or vice versa)
        search_normalized = normalize_search_text(search_text[:50] if len(search_text) > 50 else search_text)
        if not case_sensitive:
            search_normalized = search_normalized.lower()
        
        if search_normalized in normalized_word or normalized_word in search_normalized:
            return [word.get('x0', 0), word.get('y0', 0), word.get('x1', 0), word.get('y1', 0)]
    
    return None


# For backward compatibility, export HAS_PYMUPDF as False
HAS_PYMUPDF = False
