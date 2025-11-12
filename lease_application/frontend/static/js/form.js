/**
 * Lease Form JavaScript
 * Handles form interactions, validations, and dynamic sections
 */

// Get lease ID from URL if editing
let currentLeaseId = null;
document.addEventListener('DOMContentLoaded', async function() {
    if (!await requireAuth()) { return; }
    updateUserDisplay();
    const urlParams = new URLSearchParams(window.location.search);
    const leaseId = urlParams.get('id');
    if (leaseId && !isNaN(leaseId)) {
        currentLeaseId = parseInt(leaseId);
        loadLeaseData(currentLeaseId);
        loadDocuments(currentLeaseId); // Load documents for the lease
    }
});

// Go Home
function goHome() {
    window.location.href = '/dashboard.html';
}

// Logout
async function logout() {
    try {
        const response = await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
            window.location.href = 'login.html';
        }
    } catch (error) {
        console.error('Logout error:', error);
        window.location.href = 'login.html';
    }
}

// Manual Input Mode - Hide PDF Viewer
function manualInput() {
    const pdfPanel = document.getElementById('pdfPanel');
    const uploadBtn = document.getElementById('uploadBtn');
    const manualBtn = document.getElementById('manualBtn');
    
    if (pdfPanel) {
        pdfPanel.classList.add('hidden');
    }
    
    if (uploadBtn) {
        uploadBtn.style.display = 'inline-block';
    }
    if (manualBtn) {
        manualBtn.style.display = 'none';
    }
}

 // --- Global State for PDF.js ---
let pdfUrl = null;
let highlightData = []; // Stores the highlights from the API
let pdfDocument = null; // Stores the PDFJS document object
let currentScale = 1.5; // Current zoom scale
let renderedPages = []; // Store rendered page info for re-rendering
let isReviewMode = false; // Review mode state
let fieldTypeColors = {}; // Field type color mapping
let fieldHighlightMap = {}; // Maps form field names to their highlights
let fileFromExtraction = null; // To hold the file from AI extraction
let confidenceScores = {}; // Stores confidence scores for each field
let CONFIDENCE_THRESHOLD = 0.7; // Global confidence threshold for flagging low-confidence fields
// --- Maker-Checker: State ---
// currentLeaseId is declared at top of file; do not redeclare here
let currentUserRole = 'user';

async function initWorkflowState() {
    try {
        const user = await getCurrentUser();
        if (user && user.role) currentUserRole = user.role;
    } catch (e) {}
    // Try to read lease id from URL or localStorage
    const params = new URLSearchParams(window.location.search);
    if (params.get('id')) currentLeaseId = parseInt(params.get('id'), 10);
    if (!currentLeaseId) {
        const ls = localStorage.getItem('currentLeaseId');
        if (ls) currentLeaseId = parseInt(ls, 10);
    }
    updateWorkflowButtons('draft');
}

function setCurrentLeaseId(id) {
    currentLeaseId = id;
    if (id) localStorage.setItem('currentLeaseId', String(id));
}

function updateWorkflowButtons(status) {
    const submitBtn = document.getElementById('submitForReviewBtn');
    const approveBtn = document.getElementById('approveLeaseBtn');
    const rejectBtn = document.getElementById('rejectLeaseBtn');
    const submitLeaseBtn = document.getElementById('submitLeaseBtn');

    if (!submitBtn || !approveBtn || !rejectBtn || !submitLeaseBtn) return;

    const isReviewer = currentUserRole === 'admin' || currentUserRole === 'reviewer';

    if (isReviewer) {
        submitBtn.style.display = 'none';
        submitLeaseBtn.style.display = (status === 'draft') ? 'inline-block' : 'none';
    } else {
        submitBtn.style.display = (status === 'draft') ? 'inline-block' : 'none';
        submitLeaseBtn.style.display = 'none';
    }

    approveBtn.style.display = (isReviewer && status === 'submitted') ? 'inline-block' : 'none';
    rejectBtn.style.display = (isReviewer && status === 'submitted') ? 'inline-block' : 'none';
}

async function submitLeaseForReview() {
    // First, save the current data as a draft.
    // The saveDraft function handles both creating and updating.
    await saveDraft();

    // If after saving, we still don't have a lease ID, we can't submit.
    if (!currentLeaseId) {
        showModal('Error', 'Could not save the lease. Please try saving the draft manually before submitting.');
        return;
    }

    // Now, proceed with submitting for review.
    try {
        const res = await fetch(`/api/leases/${currentLeaseId}/submit`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                request_type: document.getElementById('approvalRequestType').value,
                comments: document.getElementById('approvalComments').value
            })
        });
        const j = await res.json();
        if (j.success) {
            updateWorkflowButtons('submitted');
            const fs = document.getElementById('formStatus');
            if (fs) fs.textContent = 'Submitted';
            closeSubmitApprovalModal();
            showModal('Success', 'Lease submitted for review successfully!');
            // Redirect to dashboard after successful submission
            window.location.href = '/dashboard.html';
        } else {
            showModal('Error', j.error || 'Failed to submit for review.');
        }
    } catch (error) {
        console.error('Error submitting for review:', error);
        showModal('Error', 'An error occurred while submitting for review.');
    }
}

function openSubmitApprovalModal() {
    const modal = document.getElementById('submitApprovalModal');
    if (modal) {
        modal.style.display = 'block';
    }
}

function closeSubmitApprovalModal() {
    const modal = document.getElementById('submitApprovalModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function submitLease() {
    await saveDraft();
    if (!currentLeaseId) {
        showModal('Error', 'Could not save the lease. Please try saving the draft manually before submitting.');
        return;
    }

    try {
        const res = await fetch(`/api/leases/${currentLeaseId}/approve`, { method: 'POST', credentials: 'include' });
        const j = await res.json();
        if (j.success) {
            updateWorkflowButtons('approved');
            const fs = document.getElementById('formStatus');
            if (fs) fs.textContent = 'Approved';
            showModal('Success', 'Lease submitted and approved successfully!');
            window.location.href = '/dashboard.html';
        } else {
            showModal('Error', j.error || 'Failed to submit lease.');
        }
    } catch (error) {
        console.error('Error submitting lease:', error);
        showModal('Error', 'An error occurred while submitting the lease.');
    }
}

async function approveCurrentLease() {
    if (!currentLeaseId) return;
    const res = await fetch(`/api/leases/${currentLeaseId}/approve`, {method:'POST', credentials:'include'});
    const j = await res.json();
        if (j.success) {
            updateWorkflowButtons('approved');
            const fs = document.getElementById('formStatus');
            if (fs) fs.textContent = 'Approved';
            showModal('Success', 'Lease approved');
        } else {
            showModal('Error', j.error || 'Failed to approve');
        }
    }

async function rejectCurrentLease() {
    if (!currentLeaseId) return;
    openRejectionModal();
}

function openRejectionModal() {
    const modal = document.getElementById('rejectionModal');
    if (modal) {
        modal.style.display = 'block';
    }
}

function closeRejectionModal() {
    const modal = document.getElementById('rejectionModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function submitRejection() {
    if (!currentLeaseId) return;
    const reason = document.getElementById('rejectionReason').value.trim();
    if (!reason) {
        showModal('Error', 'Please provide a reason for rejection.');
        return;
    }

    const res = await fetch(`/api/leases/${currentLeaseId}/reject`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason })
    });

    const j = await res.json();
    if (j.success) {
        updateWorkflowButtons('rejected');
        const fs = document.getElementById('formStatus');
        if (fs) fs.textContent = 'Rejected';
        closeRejectionModal();
        showModal('Success', 'Lease rejected');
    } else {
        showModal('Error', j.error || 'Failed to reject');
    }
}

// Highlight Category Management (similar to asset classes)
function loadHighlightCategoriesFromStorage() {
    const stored = localStorage.getItem('highlightCategories');
    if (stored) {
        return JSON.parse(stored);
    }
    // Default categories
    return [
        { id: 'date', fields: ['lease_start_date', 'lease_end_date', 'end_date', 'agreement_date', 'rent_agreement_date', 
                'termination_date', 'first_payment_date', 'escalation_start_date', 'transition_date',
                'posting_date', 'renewal_start_date', 'renewal_end_date'], color: 'purple', name: 'Dates' },
        { id: 'amount', fields: ['rental_1', 'rental_2', 'rental_amount', 'security_deposit', 'lease_incentive', 
                'initial_direct_expenditure', 'fair_value', 'purchase_option_price', 'aro_initial_estimate'], color: 'green', name: 'Monetary' },
        { id: 'description', fields: ['description', 'agreement_title', 'asset_title', 'asset_class', 'company_name', 'counterparty'], color: 'blue', name: 'Description' },
        { id: 'boolean', fields: ['finance_lease', 'sublease', 'bargain_purchase', 'title_transfer', 'practical_expedient',
                'short_term_ifrs', 'manual_adj', 'related_party', 'has_renewal_option', 'has_termination_option',
                'has_purchase_option', 'has_security_deposit', 'has_aro'], color: 'orange', name: 'Boolean/Flags' },
        { id: 'text', fields: ['currency', 'asset_id_code', 'asset_location', 'day_of_month', 'pay_day_of_month'], color: 'gray', name: 'Text' },
        { id: 'location', fields: ['asset_location', 'counterparty'], color: 'pink', name: 'Location' },
        { id: 'term', fields: ['tenure', 'tenure_months', 'frequency_months', 'payment_interval', 'compound_months', 
                'esc_freq_months', 'escalation_frequency'], color: 'teal', name: 'Term/Frequency' },
        { id: 'rate', fields: ['borrowing_rate', 'ibr', 'escalation_percent', 'escalation_percentage', 'discount_rate'], color: 'indigo', name: 'Rates/Percentages' }
    ];
}

function saveHighlightCategoriesToStorage(categories) {
    localStorage.setItem('highlightCategories', JSON.stringify(categories));
}

let highlightCategories = loadHighlightCategoriesFromStorage();

// Convert to FIELD_TYPES format for backward compatibility
const FIELD_TYPES = {};
highlightCategories.forEach(cat => {
    FIELD_TYPES[cat.id] = {
        fields: cat.fields,
        color: cat.color,
        name: cat.name
    };
});

// Words to exclude from boolean field searches (too generic)
const EXCLUDED_BOOLEAN_SEARCH_TERMS = ['no', 'yes', 'true', 'false', '1', '0'];

// Load PDF.js from local file first, then CDN fallback
function loadPDFJS() {
    if (typeof pdfjsLib !== 'undefined') {
        // Already loaded, configure worker if needed
        if (typeof pdfjsLib.GlobalWorkerOptions !== 'undefined') {
            // Try local worker first
            const baseUrl = window.location.origin;
            pdfjsLib.GlobalWorkerOptions.workerSrc = baseUrl + '/static/js/pdf.worker.min.js';
        }
        return Promise.resolve();
    }
    
    // Check if already loading
    if (window._pdfjsLoading) {
        return window._pdfjsLoading;
    }
    
    return window._pdfjsLoading = new Promise((resolve, reject) => {
        // Try local file first, then CDN sources for reliability
        const baseUrl = window.location.origin;
        const cdnUrls = [
            baseUrl + '/static/js/pdf.min.js',  // Local file first
            'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js',
            'https://unpkg.com/pdfjs-dist@3.11.174/build/pdf.min.js',
            'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.min.js'
        ];
        
        const workerUrls = [
            baseUrl + '/static/js/pdf.worker.min.js',  // Local worker first
            'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js',
            'https://unpkg.com/pdfjs-dist@3.11.174/build/pdf.worker.min.js',
            'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js'
        ];
        
        let currentIndex = 0;
        
        function tryLoad(index) {
            if (index >= cdnUrls.length) {
                reject(new Error('Failed to load PDF.js from all sources'));
                window._pdfjsLoading = null;
                return;
            }
            
            const script = document.createElement('script');
            script.src = cdnUrls[index];
            script.crossOrigin = 'anonymous';
            
            script.onload = () => {
                // Load worker
                if (typeof pdfjsLib !== 'undefined') {
                    pdfjsLib.GlobalWorkerOptions.workerSrc = workerUrls[index];
                    const source = index === 0 ? 'local file' : `CDN (source ${index})`;
                    console.log(`✅ PDF.js loaded from ${source}`);
                    window._pdfjsLoading = null;
                    resolve();
                } else {
                    // Try next source
                    tryLoad(index + 1);
                }
            };
            
            script.onerror = () => {
                const source = index === 0 ? 'local file' : `CDN ${index}`;
                console.warn(`Failed to load PDF.js from ${source}, trying next...`);
                // Try next source
                tryLoad(index + 1);
            };
            
            document.head.appendChild(script);
        }
        
        tryLoad(0);
    });
}

// Initialize PDF.js on page load (non-blocking)
setTimeout(() => {
    loadPDFJS().catch(err => {
        console.warn('PDF.js not loaded on page load (will retry when needed):', err.message);
    });
}, 100);

// --- PDF Panel Resizer ---
function setupPDFResizer() {
    const resizer = document.getElementById('pdfResizer');
    const pdfPanel = document.getElementById('pdfPanel');
    
    if (!resizer || !pdfPanel) return;
    
    let isResizing = false;
    let startX = 0;
    let startWidth = 0;
    
    resizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        startX = e.clientX;
        startWidth = pdfPanel.offsetWidth;
        resizer.classList.add('active');
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
        e.preventDefault();
    });
    
    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        
        const width = startWidth - (e.clientX - startX);
        const minWidth = 300;
        const maxWidth = window.innerWidth * 0.8;
        
        if (width >= minWidth && width <= maxWidth) {
            pdfPanel.style.width = width + 'px';
        }
    });
    
    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            resizer.classList.remove('active');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    });
}

// Setup resizer when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupPDFResizer);
} else {
    setupPDFResizer();
}

// Upload Contract Mode - Show PDF Viewer and trigger AI extraction
function uploadContract() {
    const pdfPanel = document.getElementById('pdfPanel');
    const uploadBtn = document.getElementById('uploadBtn');
    const manualBtn = document.getElementById('manualBtn');
    
    if (pdfPanel) {
        pdfPanel.classList.remove('hidden');
    }
    
    if (uploadBtn) {
        uploadBtn.style.display = 'none';
    }
    if (manualBtn) {
        manualBtn.style.display = 'inline-block';
    }
    
    // Create or get file input for PDF
    let pdfInput = document.getElementById('pdfUploadInput');
    if (!pdfInput) {
        pdfInput = document.createElement('input');
        pdfInput.type = 'file';
        pdfInput.id = 'pdfUploadInput';
        pdfInput.accept = '.pdf';
        pdfInput.style.display = 'none';
        pdfInput.onchange = function(e) {
            if (e.target.files && e.target.files.length > 0) {
                uploadAndExtract(e.target.files[0]);
            }
        };
        document.body.appendChild(pdfInput);
    }
    
    // Trigger file upload dialog
    pdfInput.click();
}

// --- New Upload and Extraction Function (Replaces extractAndPopulateForm) ---
async function uploadAndExtract(file) {
    fileFromExtraction = file; // Store the file globally
    console.log('📥 Starting extraction for file:', file.name);
    
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
        showModal('Error', 'Please select a PDF file');
        return;
    }
    
    // Check for stored API key first
    let storedApiKey = localStorage.getItem('google_ai_api_key');
    
    // Default API key (user provided)
    if (!storedApiKey || !storedApiKey.trim()) {
        storedApiKey = 'AIzaSyCm96pgKZ1tXA73_2m8XXDbj04WCpYp76g';
        localStorage.setItem('google_ai_api_key', storedApiKey);
        console.log('✅ Using default API key and storing in localStorage');
    }
    
    let apiKey = storedApiKey.trim();
    console.log('✅ Using API key from localStorage');
    
    // Show extraction loader with progress
    showExtractionLoader();
    updateLoaderStep(0); // Reading PDF
    
    // Display loading status
    document.getElementById('formStatus').textContent = 'AI Extraction in Progress...';
    const pdfPlaceholder = document.getElementById('pdfPlaceholder');
    const pdfViewerContainer = document.getElementById('pdfViewerContainer');
    
    if (pdfPlaceholder) pdfPlaceholder.style.display = 'block';
    if (pdfViewerContainer) pdfViewerContainer.style.display = 'none';
    
    // Show loading indicator on button
    const uploadBtn = document.getElementById('uploadBtn');
    if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Extracting...';
    }
    
    try {
        updateLoaderStep(1); // Extracting Text
        
        const formData = new FormData();
        formData.append('file', file);
        
        // Add API key if provided
        if (apiKey && apiKey.trim()) {
            formData.append('api_key', apiKey.trim());
        }
        
        updateLoaderStep(2); // AI Processing
        
        const response = await fetch('/api/upload_and_extract', {
            method: 'POST',
            credentials: 'include',
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            let errorMsg = `Server error (${response.status})`;
            try {
                const errorJson = JSON.parse(errorText);
                errorMsg = errorJson.error || errorMsg;
            } catch (e) {
                errorMsg = errorText || errorMsg;
            }
            hideExtractionLoader();
            showModal('Error', `❌ Error: ${errorMsg}`);
            if (uploadBtn) {
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload Contract – AI Extraction';
            }
            return;
        }

        const result = await response.json();
        
        if (result.success) {
            updateLoaderStep(3); // Populating Form

            // Debug: Log the full response to see what we're getting
            console.log('🔍 Full API response:', result);
            console.log('🔍 Confidence scores in response:', result.confidence_scores);
            console.log('🔍 Confidence scores type:', typeof result.confidence_scores);

            // 1. Store global state
            pdfUrl = result.pdf_url;
            highlightData = result.highlights || [];
            confidenceScores = result.confidence_scores || {};

            console.log('📊 Stored confidence scores:', confidenceScores);
            console.log('📊 Confidence scores keys:', Object.keys(confidenceScores));

            // Build field highlight mapping (extraction field -> form field -> highlights)
            fieldHighlightMap = {};
            highlightData.forEach(h => {
                const extractionField = h.field;
                // Find which form field this maps to
                let formFieldName = fieldNameMapping[extractionField] || extractionField;

                // The mapping should already work, but let's ensure it's correct
                // formFieldName is already set above from fieldNameMapping

                // If still no match, use extraction field name directly
                if (!formFieldName) {
                    formFieldName = extractionField;
                }

                if (!fieldHighlightMap[formFieldName]) {
                    fieldHighlightMap[formFieldName] = [];
                }
                fieldHighlightMap[formFieldName].push(h);

                console.log(`📌 Mapped highlight: ${extractionField} → ${formFieldName} (${h.page})`);
            });

            console.log(`✅ Built highlight map for ${Object.keys(fieldHighlightMap).length} form fields`);
            console.log(`✅ Loaded confidence scores for ${Object.keys(confidenceScores).length} fields`);

            // 2. Populate form with extracted data
            if (result.data) {
                populateForm(result.data);
            }
            
            // 3. Add highlight icons to populated fields
            addHighlightIcons();
            
            // 3. Load PDF.js if needed and render PDF and highlights
            // Make PDF rendering optional - don't fail if PDF.js doesn't load
            let pdfRendered = false;
            try {
                await loadPDFJS();
                if (typeof pdfjsLib !== 'undefined') {
                    await renderPDFAndHighlights(result.pdf_url, highlightData);
                    // Cache review context (lease -> pdf + highlights)
                    if (currentLeaseId && result.pdf_url && Array.isArray(highlightData)) {
                        try {
                            localStorage.setItem(`lease_review_${currentLeaseId}`, JSON.stringify({ pdfUrl: result.pdf_url, highlights: highlightData }));
                        } catch (e) {}
                    }
                    pdfRendered = true;
                } else {
                    throw new Error('PDF.js library not available');
                }
            } catch (pdfError) {
                console.warn('PDF.js rendering failed (continuing without PDF view):', pdfError);
                // Show success message even if PDF rendering fails
                if (pdfPlaceholder) {
                    pdfPlaceholder.innerHTML = `
                        <p style="color: #27ae60; font-weight: 600;">✅ PDF Processed Successfully</p>
                        <p style="color: #666; font-size: 14px;">Form populated with extracted data.</p>
                        <p style="color: #999; font-size: 12px; margin-top: 10px;">PDF viewer unavailable (${pdfError.message})</p>
                    `;
                    pdfPlaceholder.style.display = 'block';
                }
            }
            
            // Show AI confidence legend if there are low-confidence fields
            const hasLowConfidence = Object.values(confidenceScores).some(score => score < CONFIDENCE_THRESHOLD);
            const aiConfidenceLegend = document.getElementById('aiConfidenceLegend');
            if (aiConfidenceLegend) {
                if (hasLowConfidence) {
                    aiConfidenceLegend.style.display = 'block';
                    console.log('✅ Showing AI confidence legend due to low-confidence fields');
                } else {
                    aiConfidenceLegend.style.display = 'none';
                    console.log('ℹ️ No low-confidence fields detected, hiding legend');
                }
            }

            // Update UI state
            document.getElementById('formStatus').textContent = 'Draft (AI Extracted)';
            if (pdfRendered) {
                if (pdfPlaceholder) pdfPlaceholder.style.display = 'none';
                if (pdfViewerContainer) pdfViewerContainer.style.display = 'block';

                // Show Review Mode button
                const reviewModeBtn = document.getElementById('reviewModeBtn');
                if (reviewModeBtn) {
                    reviewModeBtn.style.display = 'inline-block';
                }

                // Setup review mode
                setupReviewMode();
            }

        } else {
            hideExtractionLoader();
            showModal('Error', `Extraction failed: ${result.error || 'Unknown error'}`);
            document.getElementById('formStatus').textContent = 'Draft (Error)';
        }
        
        hideExtractionLoader();
        
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload Contract – AI Extraction';
        }
    } catch (error) {
        console.error('Upload and Extraction error:', error);
        hideExtractionLoader();
        showModal('Error', 'Failed to process the document. Check console for details.');
        document.getElementById('formStatus').textContent = 'Draft (Error)';
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload Contract – AI Extraction';
        }
    }
}

// Helper function to update loader step
function updateLoaderStep(stepIndex) {
    const loader = document.getElementById('extractionLoader');
    if (loader) {
        const steps = loader.querySelectorAll('.step');
        steps.forEach((step, index) => {
            if (index <= stepIndex) {
                step.classList.add('active');
            } else {
                step.classList.remove('active');
            }
        });
    }
}

// --- PDF Rendering and Highlighting Functions ---

async function renderPDFAndHighlights(url, highlights) {
    const pdfScrollArea = document.getElementById('pdfScrollArea');
    if (!pdfScrollArea) {
        console.error('PDF scroll area not found');
        return;
    }
    
    pdfScrollArea.innerHTML = ''; // Clear previous content
    renderedPages = []; // Clear stored pages

    if (typeof pdfjsLib === 'undefined') {
        console.error("PDF.js is not available.");
        return;
    }
    
    try {
        // Load the PDF Document
        const loadingTask = pdfjsLib.getDocument(url);
        pdfDocument = await loadingTask.promise;
        
        console.log(`📄 PDF loaded: ${pdfDocument.numPages} pages`);
        
        // Calculate optimal scale for native-like experience (fit width)
        const containerWidth = pdfScrollArea.clientWidth - 40; // Account for padding
        const firstPage = await pdfDocument.getPage(1);
        const firstViewport = firstPage.getViewport({ scale: 1.0 });
        const optimalScale = containerWidth / firstViewport.width;
        currentScale = Math.max(1.0, Math.min(2.5, optimalScale)); // Clamp between 100% and 250%
        
        updateZoomDisplay();
        setupZoomControls();
        
        // Log extracted text and highlights for comparison
        logExtractionComparison(highlights);
        
        // Render all pages
        for (let pageNum = 1; pageNum <= pdfDocument.numPages; pageNum++) {
            const page = await pdfDocument.getPage(pageNum);
            
            // 1. Create wrapper and canvas for PDF.js
            const pageWrapper = document.createElement('div');
            pageWrapper.className = 'pdf-page-wrapper';
            pageWrapper.id = `pdf-page-${pageNum}`;
            pageWrapper.setAttribute('data-page', pageNum);
            pageWrapper.dataset.page = pageNum; // For easier access
            
            const canvas = document.createElement('canvas');
            pageWrapper.appendChild(canvas);
            
            // 2. Render the page on canvas with current scale
            const viewport = page.getViewport({ scale: currentScale });
            const context = canvas.getContext('2d');
            canvas.height = viewport.height;
            canvas.width = viewport.width;
            
            // Enable high-DPI rendering for crisp text
            const outputScale = window.devicePixelRatio || 1;
            canvas.width = viewport.width * outputScale;
            canvas.height = viewport.height * outputScale;
            context.scale(outputScale, outputScale);
            canvas.style.width = viewport.width + 'px';
            canvas.style.height = viewport.height + 'px';

            const renderContext = {
                canvasContext: context,
                viewport: viewport
            };
            await page.render(renderContext).promise;

            // 3. Create highlight overlay - ensure it matches canvas size exactly
            const highlightOverlay = document.createElement('div');
            highlightOverlay.className = 'highlight-overlay';
            highlightOverlay.style.width = viewport.width + 'px';
            highlightOverlay.style.height = viewport.height + 'px';
            pageWrapper.appendChild(highlightOverlay);

            // 4. Draw highlights for this page
            drawHighlightsOnPage(highlightOverlay, pageNum, viewport.width, viewport.height, page.view, highlights);
            
            // Store page info for re-rendering
            renderedPages.push({
                pageNum,
                page,
                pageWrapper,
                canvas,
                highlightOverlay,
                viewport
            });
            
            pdfScrollArea.appendChild(pageWrapper);
        }
        
        // 5. Setup interactivity
        setupHighlightInteractivity();
        
        // 6. Initialize highlight navigation
        initializeHighlightNavigation();
        
        console.log('✅ PDF rendered with highlights at scale:', currentScale.toFixed(2));
    } catch (error) {
        console.error('Error rendering PDF:', error);
        pdfScrollArea.innerHTML = `<p style="color: red; padding: 20px;">Error loading PDF: ${error.message}</p>`;
    }
}

// Log extracted text vs highlighted positions for comparison
function logExtractionComparison(highlights) {
    console.group('📊 Extraction vs Highlight Comparison');
    console.log('Total highlights found:', highlights.length);
    
    // Group by field
    const highlightsByField = {};
    highlights.forEach(h => {
        if (!highlightsByField[h.field]) {
            highlightsByField[h.field] = [];
        }
        highlightsByField[h.field].push(h);
    });
    
    console.log('\n📋 Highlights by Field:');
    for (const [field, fieldHighlights] of Object.entries(highlightsByField)) {
        console.group(`  ${field} (${fieldHighlights.length} matches)`);
        fieldHighlights.forEach((h, idx) => {
            console.log(`  Match ${idx + 1}:`, {
                text: h.text,
                page: h.page,
                bbox: h.bbox,
                position: `[${h.bbox.map(v => v.toFixed(1)).join(', ')}]`
            });
        });
        console.groupEnd();
    }
    
    console.log('\n🔍 Summary:');
    console.table(
        Object.entries(highlightsByField).map(([field, highlights]) => ({
            Field: field,
            'Matches': highlights.length,
            'Pages': [...new Set(highlights.map(h => h.page))].join(', '),
            'Sample Text': highlights[0]?.text?.substring(0, 30) || 'N/A'
        }))
    );
    
    console.groupEnd();
}

// Zoom controls
function setupZoomControls() {
    const zoomInBtn = document.getElementById('zoomInBtn');
    const zoomOutBtn = document.getElementById('zoomOutBtn');
    const fitWidthBtn = document.getElementById('fitWidthBtn');
    const fitPageBtn = document.getElementById('fitPageBtn');
    const downloadBtn = document.getElementById('downloadPdfBtn');
    
    if (zoomInBtn) {
        zoomInBtn.addEventListener('click', () => {
            currentScale = Math.min(3.0, currentScale + 0.25);
            reRenderPDF();
        });
    }
    
    if (zoomOutBtn) {
        zoomOutBtn.addEventListener('click', () => {
            currentScale = Math.max(0.5, currentScale - 0.25);
            reRenderPDF();
        });
    }
    
    if (fitWidthBtn) {
        fitWidthBtn.addEventListener('click', () => {
            if (pdfDocument && renderedPages.length > 0) {
                const containerWidth = document.getElementById('pdfScrollArea').clientWidth - 40;
                const firstPage = renderedPages[0].page;
                const firstViewport = firstPage.getViewport({ scale: 1.0 });
                currentScale = containerWidth / firstViewport.width;
                reRenderPDF();
            }
        });
    }
    
    if (fitPageBtn) {
        fitPageBtn.addEventListener('click', () => {
            currentScale = 1.5; // Default scale
            reRenderPDF();
        });
    }
    
    if (downloadBtn && pdfUrl) {
        downloadBtn.addEventListener('click', () => {
            const link = document.createElement('a');
            link.href = pdfUrl;
            link.download = 'extracted_lease_document.pdf';
            link.click();
        });
    }
    
    // Highlight navigation buttons
    if (prevHighlightBtn) {
        prevHighlightBtn.addEventListener('click', () => {
            navigateHighlight(-1); // Previous
        });
    }
    
    if (nextHighlightBtn) {
        nextHighlightBtn.addEventListener('click', () => {
            navigateHighlight(1); // Next
        });
    }
    
    // Initialize highlight navigation after PDF is rendered
    initializeHighlightNavigation();
}

/**
 * Initialize highlight navigation - build array of all highlights in order
 */
function initializeHighlightNavigation() {
    allHighlightBoxes = [];
    const allHighlights = document.querySelectorAll('.highlight-box');
    
    // Convert to array and sort by page, then by position
    const highlightsArray = Array.from(allHighlights);
    
    // Sort by page number, then by top position
    highlightsArray.sort((a, b) => {
        const pageWrapperA = a.closest('.pdf-page-wrapper');
        const pageWrapperB = b.closest('.pdf-page-wrapper');
        const pageA = parseInt(pageWrapperA?.dataset.page || pageWrapperA?.getAttribute('data-page') || '0');
        const pageB = parseInt(pageWrapperB?.dataset.page || pageWrapperB?.getAttribute('data-page') || '0');
        if (pageA !== pageB) return pageA - pageB;
        
        // Get absolute position within PDF scroll area
        const topA = pageWrapperA ? pageWrapperA.offsetTop + a.offsetTop : a.offsetTop;
        const topB = pageWrapperB ? pageWrapperB.offsetTop + b.offsetTop : b.offsetTop;
        return topA - topB;
    });
    
    allHighlightBoxes = highlightsArray;
    currentHighlightIndex = -1;
    
    console.log(`✅ Initialized highlight navigation with ${allHighlightBoxes.length} highlights`);
}

/**
 * Navigate to previous/next highlight
 */
function navigateHighlight(direction) {
    if (allHighlightBoxes.length === 0) {
        console.warn('No highlights available for navigation');
        return;
    }
    
    // Clear all active highlights
    document.querySelectorAll('.highlight-box').forEach(h => h.classList.remove('active'));
    document.querySelectorAll('.form-group').forEach(g => g.classList.remove('review-highlighted'));
    
    // Move to next/previous highlight
    currentHighlightIndex += direction;
    
    // Wrap around
    if (currentHighlightIndex < 0) {
        currentHighlightIndex = allHighlightBoxes.length - 1;
    } else if (currentHighlightIndex >= allHighlightBoxes.length) {
        currentHighlightIndex = 0;
    }
    
    // Get the current highlight
    const currentHighlight = allHighlightBoxes[currentHighlightIndex];
    if (!currentHighlight) return;
    
    // Activate this highlight
    currentHighlight.classList.add('active');
    
    // Scroll to this highlight
    const pdfScrollArea = document.getElementById('pdfScrollArea');
    if (pdfScrollArea) {
        const highlightTop = currentHighlight.offsetTop;
        const scrollTop = highlightTop - (pdfScrollArea.clientHeight / 2) + (currentHighlight.offsetHeight / 2);
        
        pdfScrollArea.scrollTo({
            top: Math.max(0, scrollTop),
            behavior: 'smooth'
        });
        
        // Focus PDF viewer
        pdfScrollArea.focus();
    }
    
    // Show which highlight we're on
    console.log(`📍 Highlight ${currentHighlightIndex + 1} of ${allHighlightBoxes.length}`);
}

function updateZoomDisplay() {
    const zoomValue = document.getElementById('zoomValue');
    if (zoomValue) {
        zoomValue.textContent = Math.round(currentScale * 100) + '%';
    }
}

async function reRenderPDF() {
    if (!pdfDocument || renderedPages.length === 0) return;
    
    updateZoomDisplay();
    
    // Re-render all pages with new scale
    for (const pageInfo of renderedPages) {
        const { page, canvas, highlightOverlay, pageNum } = pageInfo;
        
        const viewport = page.getViewport({ scale: currentScale });
        const context = canvas.getContext('2d');
        
        // Clear canvas
        context.clearRect(0, 0, canvas.width, canvas.height);
        
        // Resize canvas
        const outputScale = window.devicePixelRatio || 1;
        canvas.width = viewport.width * outputScale;
        canvas.height = viewport.height * outputScale;
        canvas.style.width = viewport.width + 'px';
        canvas.style.height = viewport.height + 'px';
        context.scale(outputScale, outputScale);
        
        // Re-render
        const renderContext = {
            canvasContext: context,
            viewport: viewport
        };
        await page.render(renderContext).promise;
        
        // Re-draw highlights - ensure overlay is properly sized
        highlightOverlay.innerHTML = '';
        // Set overlay size to match canvas exactly
        highlightOverlay.style.width = viewport.width + 'px';
        highlightOverlay.style.height = viewport.height + 'px';
        drawHighlightsOnPage(highlightOverlay, pageNum, viewport.width, viewport.height, page.view, highlightData);
    }
    
    // Re-initialize highlight navigation after re-rendering
    initializeHighlightNavigation();
}

/**
 * Get field type for a given field name
 */
function getFieldType(fieldName) {
    for (const [type, config] of Object.entries(FIELD_TYPES)) {
        if (config.fields.includes(fieldName)) {
            return type;
        }
    }
    return 'text'; // Default
}

/**
 * Draws the bounding boxes on the HTML overlay layer with color coding.
 * @param {HTMLElement} overlay - The highlight-overlay div for the page.
 * @param {number} pageNum - The current page number.
 * @param {number} canvasWidth - The rendered width of the canvas in pixels.
 * @param {number} canvasHeight - The rendered height of the canvas in pixels.
 * @param {Array<number>} view - The original PDF page size [x, y, width, height] (from pdf.view).
 * @param {Array<object>} highlights - The list of highlight objects from the API.
 */
function drawHighlightsOnPage(overlay, pageNum, canvasWidth, canvasHeight, view, highlights) {
    // Get the original PDF dimensions (in PDF units, e.g., 72dpi)
    const pdfWidth = view[2]; // usually 595.3 for A4
    const pdfHeight = view[3]; // usually 841.9 for A4

    // Ensure overlay matches canvas dimensions exactly
    if (overlay) {
        overlay.style.width = canvasWidth + 'px';
        overlay.style.height = canvasHeight + 'px';
    }

    const scaleX = canvasWidth / pdfWidth;
    const scaleY = canvasHeight / pdfHeight;
    
    const pageHighlights = highlights.filter(h => h.page === pageNum);
    
    pageHighlights.forEach(h => {
        // h.bbox format: [x0, top, x1, bottom] from pdfplumber (Top-Left Origin)
        const [x0, top, x1, bottom] = h.bbox; 
        
        // Convert pdfplumber coordinates to pixel coordinates
        const pixelLeft = x0 * scaleX;
        const pixelTop = top * scaleY;
        const pixelWidth = (x1 - x0) * scaleX;
        const pixelHeight = (bottom - top) * scaleY;

        const highlightBox = document.createElement('div');
        
        // Get field type and apply color class
        const fieldType = getFieldType(h.field);
        highlightBox.className = `highlight-box highlight-type-${fieldType}`;
        
        // Get category for dynamic color
        const category = highlightCategories.find(c => c.id === fieldType);
        const colorValue = category?.color || FIELD_TYPES[fieldType]?.color || 'gray';
        
        // Apply dynamic color
        const colors = {
            purple: 'rgba(156, 39, 176, 0.4)',
            green: 'rgba(76, 175, 80, 0.4)',
            blue: 'rgba(33, 150, 243, 0.4)',
            orange: 'rgba(255, 152, 0, 0.4)',
            gray: 'rgba(158, 158, 158, 0.4)',
            pink: 'rgba(233, 30, 99, 0.4)',
            teal: 'rgba(0, 150, 136, 0.4)',
            indigo: 'rgba(63, 81, 181, 0.4)'
        };
        
        // Check if colorValue is hex (6 chars)
        let bgColor, borderColor;
        if (/^[0-9A-Fa-f]{6}$/.test(colorValue)) {
            const r = parseInt(colorValue.substr(0, 2), 16);
            const g = parseInt(colorValue.substr(2, 2), 16);
            const b = parseInt(colorValue.substr(4, 2), 16);
            bgColor = `rgba(${r}, ${g}, ${b}, 0.4)`;
            borderColor = `rgba(${r}, ${g}, ${b}, 0.8)`;
        } else {
            bgColor = colors[colorValue] || colors.gray;
            borderColor = colors[colorValue]?.replace('0.4', '0.8') || colors.gray;
        }
        
        // Store the form field name for interactivity
        highlightBox.dataset.field = h.field;
        highlightBox.dataset.fieldType = fieldType;
        
        highlightBox.style.cssText = `
            left: ${pixelLeft}px;
            top: ${pixelTop}px;
            width: ${pixelWidth}px;
            height: ${pixelHeight}px;
            background-color: ${bgColor};
            border: 2px solid ${borderColor};
        `;
        
        overlay.appendChild(highlightBox);
    });
}

// --- Form Population and Interactivity ---

// Field name mapping: AI extracted field names -> Form field names
const fieldNameMapping = {
    'end_date': 'lease_end_date',
    'rental_1': 'rental_amount',
    'rental_2': 'rental_amount', // Also map rental_2 to rental_amount if needed
    'borrowing_rate': 'ibr', // Map borrowing_rate to ibr
    'ibr': 'ibr', // Keep ibr as is
    'lease_start_date': 'lease_start_date',
    'first_payment_date': 'first_payment_date',
    'agreement_date': 'rent_agreement_date',
    'company_name': 'company_name',
    'counterparty': 'counterparty',
    'asset_class': 'asset_class',
    'asset_id_code': 'asset_id_code',
    'currency': 'currency',
    'tenure': 'tenure_months',
    'frequency_months': 'payment_interval',
    'day_of_month': 'pay_day_of_month',
    'escalation_percent': 'escalation_percentage',
    'escalation_start_date': 'escalation_start_date',
    'escalation_frequency': 'escalation_frequency',
    'security_deposit': 'security_deposit_amount_1',
    'lease_incentive': 'lease_incentive',
    'initial_direct_expenditure': 'initial_direct_expenditure',
    'description': 'agreement_title',
};

function populateForm(data) {
    const form = document.getElementById('leaseForm');
    if (!form) {
        console.error('Form not found');
        return;
    }

    console.log('📝 Populating form with extracted data:', data);

    for (const fieldName in data) {
        if (data.hasOwnProperty(fieldName)) {
            // Skip metadata fields
            if (fieldName === '_metadata') continue;

            let formFieldName = fieldName;

            // Check if field name needs mapping
            if (fieldNameMapping[fieldName]) {
                formFieldName = fieldNameMapping[fieldName];
                console.log(`   ↳ Mapping ${fieldName} → ${formFieldName}`);
            }

            const input = form.querySelector(`[name="${formFieldName}"]`);
            if (input) {
                let value = data[fieldName];

                // Skip null, empty, or invalid values
                if (value === null || value === '' || value === 'null' || value === 'None') {
                    continue;
                }

                // Handle special cases
                if (fieldName === 'rental_2' && value && data['rental_1']) {
                    // If rental_2 exists but rental_amount already has rental_1, skip
                    console.log(`   ⏭️ Skipping rental_2 (already have rental_1)`);
                    continue;
                }

                // Handle different input types
                if (input.type === 'checkbox') {
                    input.checked = (value === true || value === 'true' || value === 'Yes' || value === 'yes');
                } else if (input.tagName === 'SELECT') {
                    // Try to match value to option
                    input.value = value;
                    // Trigger change event for selects that have dependencies
                    if (input.name === 'rent_frequency') {
                        input.dispatchEvent(new Event('change'));
                    }
                } else {
                    // Default for text, number, date
                    input.value = value;
                }

                // Trigger change event for fields with dependencies
                if (input.name === 'lease_start_date' || input.name === 'lease_end_date') {
                    input.dispatchEvent(new Event('change'));
                }

                console.log(`   ✅ Set ${formFieldName} = ${value}`);

                // Add a class to indicate this field was auto-populated
                const formGroup = input.closest('.form-group');
                if (formGroup) {
                    formGroup.classList.add('extracted-field');

                    // Check confidence score and apply low-confidence styling
                    const confidenceScore = confidenceScores[fieldName] || confidenceScores[formFieldName];
                    console.log(`   📊 Confidence check for ${formFieldName}: fieldName=${fieldName}, formFieldName=${formFieldName}, confidenceScore=${confidenceScore}, threshold=${CONFIDENCE_THRESHOLD}`);

                    if (confidenceScore !== undefined && confidenceScore < CONFIDENCE_THRESHOLD) {
                        formGroup.classList.add('low-confidence-field');
                        console.log(`   ⚠️ Low confidence (${confidenceScore.toFixed(2)}) for ${formFieldName}`);

                        // Add confidence badge
                        addConfidenceBadge(formGroup, confidenceScore);
                    } else if (confidenceScore !== undefined) {
                        console.log(`   ✅ High confidence (${confidenceScore.toFixed(2)}) for ${formFieldName}`);
                    } else {
                        console.log(`   ❓ No confidence score found for ${formFieldName}`);
                    }
                }
            } else {
                console.log(`   ⚠️ Form field not found: ${formFieldName}`);
            }
        }
    }

    console.log('✅ Form population complete');
}

/**
 * Add confidence badge to low-confidence fields
 */
function addConfidenceBadge(formGroup, confidenceScore) {
    // Remove existing badge if any
    const existingBadge = formGroup.querySelector('.confidence-badge');
    if (existingBadge) {
        existingBadge.remove();
    }

    // Create badge
    const badge = document.createElement('span');
    badge.className = 'confidence-badge';
    badge.textContent = `${(confidenceScore * 100).toFixed(0)}%`;
    badge.title = `AI Confidence: ${(confidenceScore * 100).toFixed(1)}% - Low confidence field, please verify`;

    // Add to form group
    formGroup.appendChild(badge);
}

/**
 * Add highlight icons next to populated fields that have highlights
 */
function addHighlightIcons() {
    const form = document.getElementById('leaseForm');
    if (!form) return;
    
    // Remove existing icons first
    document.querySelectorAll('.highlight-icon').forEach(icon => icon.remove());
    
    let iconsAdded = 0;
    
    // Add icons for fields that have highlights
    for (const [formFieldName, highlights] of Object.entries(fieldHighlightMap)) {
        if (!highlights || highlights.length === 0) {
            console.warn(`⚠️ No highlights for field: ${formFieldName}`);
            continue;
        }
        
        const input = form.querySelector(`[name="${formFieldName}"]`);
        if (!input) {
            console.warn(`⚠️ Input not found for field: ${formFieldName}`);
            continue;
        }
        
        // Skip if field is empty
        if (!input.value || input.value === '' || input.value === 'null') {
            console.warn(`⚠️ Field ${formFieldName} is empty, skipping icon`);
            continue;
        }
        
        const formGroup = input.closest('.form-group');
        if (!formGroup) continue;
        
        // Get field type for color
        const firstHighlight = highlights[0];
        const extractionField = firstHighlight.field;
        const fieldType = getFieldType(extractionField);
        
        // Create icon
        const icon = document.createElement('button');
        icon.type = 'button';
        icon.className = 'highlight-icon';
        icon.dataset.fieldName = formFieldName;
        icon.dataset.fieldType = fieldType;
        icon.title = `Click to view highlight in PDF (${highlights.length} match${highlights.length > 1 ? 'es' : ''})`;
        
        // Set color based on field type from category
        const category = highlightCategories.find(c => c.id === fieldType);
        const colorValue = category?.color || FIELD_TYPES[fieldType]?.color || 'gray';
        
        const typeColors = {
            purple: 'rgba(156, 39, 176, 0.8)',
            green: 'rgba(76, 175, 80, 0.8)',
            blue: 'rgba(33, 150, 243, 0.8)',
            orange: 'rgba(255, 152, 0, 0.8)',
            gray: 'rgba(158, 158, 158, 0.8)',
            pink: 'rgba(233, 30, 99, 0.8)',
            teal: 'rgba(0, 150, 136, 0.8)',
            indigo: 'rgba(63, 81, 181, 0.8)'
        };
        
        // Check if colorValue is hex (6 chars)
        let iconColor;
        if (/^[0-9A-Fa-f]{6}$/.test(colorValue)) {
            const r = parseInt(colorValue.substr(0, 2), 16);
            const g = parseInt(colorValue.substr(2, 2), 16);
            const b = parseInt(colorValue.substr(4, 2), 16);
            iconColor = `rgba(${r}, ${g}, ${b}, 0.8)`;
        } else {
            iconColor = typeColors[colorValue] || typeColors.gray;
        }
        
        icon.style.backgroundColor = iconColor;
        icon.style.borderColor = iconColor;
        
        // Add click handler - focus PDF highlight, not form field
        icon.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            scrollToFieldHighlight(formFieldName, input, true, false); // false = don't focus form field
        });
        
        // Insert icon inline with the input field
        // Create or find a wrapper div for the input + icon
        let inputWrapper = input.parentElement;
        
        // Check if input is already in a flex container
        if (inputWrapper && window.getComputedStyle(inputWrapper).display === 'flex') {
            // Already in a flex container, just add icon
            inputWrapper.appendChild(icon);
        } else {
            // Create a wrapper div
            const wrapper = document.createElement('div');
            wrapper.style.display = 'flex';
            wrapper.style.alignItems = 'center';
            wrapper.style.gap = '8px';
            wrapper.style.width = '100%';
            
            // Move input into wrapper
            input.parentElement.insertBefore(wrapper, input);
            wrapper.appendChild(input);
            wrapper.appendChild(icon);
        }
        
        iconsAdded++;
    }
    
    console.log(`✅ Added ${iconsAdded} highlight icons (${Object.keys(fieldHighlightMap).length} fields with highlights)`);
    
    // Log warning for fields that are populated but don't have highlights
    const allPopulatedFields = form.querySelectorAll('.extracted-field input, .extracted-field select, .extracted-field textarea');
    const populatedWithoutIcons = [];
    allPopulatedFields.forEach(input => {
        const fieldName = input.getAttribute('name');
        const hasValue = input.value && input.value !== '' && input.value !== 'null';
        const hasIcon = input.parentElement.querySelector('.highlight-icon') !== null;
        
        if (hasValue && !hasIcon && fieldName) {
            populatedWithoutIcons.push(fieldName);
        }
    });
    
    if (populatedWithoutIcons.length > 0) {
        console.warn(`⚠️ ${populatedWithoutIcons.length} populated fields without highlights:`, populatedWithoutIcons);
    }
}

/**
 * Sets up listeners so clicking an input highlights its source in the PDF.
 * Enhanced with click-to-scroll functionality.
 */
function setupHighlightInteractivity() {
    const form = document.getElementById('leaseForm');
    if (!form) return;
    
    const allInputs = form.querySelectorAll('input, select, textarea');
    const allHighlights = document.querySelectorAll('.highlight-box');

    allInputs.forEach(input => {
        // Use the form field name to link to the highlight data-field attribute
        const fieldName = input.getAttribute('name');

        if (!fieldName) return;

        // Clear all highlights when form loses focus
        input.addEventListener('blur', () => {
            if (!isReviewMode) {
                allHighlights.forEach(h => h.classList.remove('active'));
                const formGroup = input.closest('.form-group');
                if (formGroup) formGroup.classList.remove('review-highlighted');
            }
        });

        // Enhanced click/focus listener with scroll-to-highlight
        input.addEventListener('focus', (e) => {
            scrollToFieldHighlight(fieldName, input, true);
        });
        
        // Also add click listener for better UX in review mode
        input.addEventListener('click', (e) => {
            if (isReviewMode) {
                scrollToFieldHighlight(fieldName, input, true);
            }
        });
    });
}

/**
 * Scroll to the first highlight for a given field
 * @param {string} fieldName - Form field name
 * @param {HTMLElement} input - Input element (optional)
 * @param {boolean} highlight - Whether to highlight the match
 * @param {boolean} focusFormField - Whether to also focus/scroll the form field (default true)
 */
function scrollToFieldHighlight(fieldName, input, highlight = true, focusFormField = true) {
    const allHighlights = document.querySelectorAll('.highlight-box');
    
    // Clear all previous highlights
    allHighlights.forEach(h => h.classList.remove('active'));
    document.querySelectorAll('.form-group').forEach(g => g.classList.remove('review-highlighted'));
    
    // Find matching highlights
    let matches = document.querySelectorAll(`.highlight-box[data-field="${fieldName}"]`);
    
    // If no matches, try the original field name (for extraction field names)
    if (matches.length === 0) {
        // Try reverse lookup - find which extraction field maps to this form field
        for (const [extractionField, formField] of Object.entries(fieldNameMapping)) {
            if (formField === fieldName) {
                matches = document.querySelectorAll(`.highlight-box[data-field="${extractionField}"]`);
                if (matches.length > 0) break;
            }
        }
    }
    
    if (matches.length > 0) {
        if (highlight) {
            // Highlight all matches
            matches.forEach(h => h.classList.add('active'));
            
            // Highlight the form field only if focusFormField is true
            if (focusFormField && input) {
                const formGroup = input.closest('.form-group');
                if (formGroup) formGroup.classList.add('review-highlighted');
            }
        }
        
        // Scroll to the first match in PDF (this is the main action)
        const firstMatch = matches[0];
        const firstMatchPage = firstMatch.closest('.pdf-page-wrapper');
        if (firstMatchPage) {
            // Scroll PDF viewer to the highlight with focus on the highlight box
            const pdfScrollArea = document.getElementById('pdfScrollArea');
            if (pdfScrollArea) {
                // Calculate scroll position to center the highlight in view
                const highlightTop = firstMatch.offsetTop;
                const scrollTop = highlightTop - (pdfScrollArea.clientHeight / 2) + (firstMatch.offsetHeight / 2);
                
                pdfScrollArea.scrollTo({
                    top: Math.max(0, scrollTop),
                    behavior: 'smooth'
                });
                
                // Focus the PDF viewer
                pdfScrollArea.focus();
            }
        }
        
        // Also scroll form if needed (only if focusFormField is true)
        if (focusFormField && input) {
            input.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    } else {
        console.warn(`No highlights found for field: ${fieldName}`);
    }
}

/**
 * Toggle Review Mode
 */
function toggleReviewMode() {
    isReviewMode = !isReviewMode;
    const reviewModeBtn = document.getElementById('reviewModeBtn');
    const reviewModeText = document.getElementById('reviewModeText');
    const legend = document.getElementById('highlightLegend');
    
    if (isReviewMode) {
        // Enable review mode
        if (reviewModeText) reviewModeText.textContent = 'Exit Review';
        if (reviewModeBtn) reviewModeBtn.classList.add('active');
        if (legend) legend.style.display = 'block';
        
        // Build legend
        buildFieldTypeLegend();
        
        // Highlight all extracted fields
        document.querySelectorAll('.extracted-field').forEach(group => {
            group.classList.add('review-highlighted');
        });
        
        console.log('✅ Review Mode Enabled');
    } else {
        // Disable review mode
        if (reviewModeText) reviewModeText.textContent = 'Review Mode';
        if (reviewModeBtn) reviewModeBtn.classList.remove('active');
        if (legend) legend.style.display = 'none';
        
        // Clear highlights
        document.querySelectorAll('.highlight-box').forEach(h => h.classList.remove('active'));
        document.querySelectorAll('.form-group').forEach(g => g.classList.remove('review-highlighted'));
        
        console.log('✅ Review Mode Disabled');
    }
}

/**
 * Build field type legend
 */
function buildFieldTypeLegend() {
    const legendItems = document.getElementById('legendItems');
    if (!legendItems) return;
    
    legendItems.innerHTML = '';
    
    // Count highlights by type
    const highlightsByType = {};
    highlightData.forEach(h => {
        const type = getFieldType(h.field);
        if (!highlightsByType[type]) {
            highlightsByType[type] = [];
        }
        highlightsByType[type].push(h);
    });
    
    // Create legend items
    for (const [type, config] of Object.entries(FIELD_TYPES)) {
        const count = highlightsByType[type]?.length || 0;
        if (count === 0) continue;
        
        const legendItem = document.createElement('div');
        legendItem.className = 'legend-item active';
        legendItem.dataset.type = type;
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = true;
        checkbox.dataset.type = type;
        
        const colorBox = document.createElement('span');
        colorBox.className = 'legend-color highlight-type-' + type;
        // Get color from category or use default
        const category = highlightCategories.find(c => c.id === type);
        const colorValue = category?.color || config.color;
        
        // Convert color name to rgba or use hex directly
        const colors = {
            purple: 'rgba(156, 39, 176, 0.4)',
            green: 'rgba(76, 175, 80, 0.4)',
            blue: 'rgba(33, 150, 243, 0.4)',
            orange: 'rgba(255, 152, 0, 0.4)',
            gray: 'rgba(158, 158, 158, 0.4)',
            pink: 'rgba(233, 30, 99, 0.4)',
            teal: 'rgba(0, 150, 136, 0.4)',
            indigo: 'rgba(63, 81, 181, 0.4)'
        };
        
        // Check if colorValue is a hex color (starts with number or letter, 6 chars)
        if (/^[0-9A-Fa-f]{6}$/.test(colorValue)) {
            // Convert hex to rgba
            const r = parseInt(colorValue.substr(0, 2), 16);
            const g = parseInt(colorValue.substr(2, 2), 16);
            const b = parseInt(colorValue.substr(4, 2), 16);
            colorBox.style.backgroundColor = `rgba(${r}, ${g}, ${b}, 0.4)`;
            colorBox.style.borderColor = `rgba(${r}, ${g}, ${b}, 0.8)`;
        } else {
            colorBox.style.backgroundColor = colors[colorValue] || colors.gray;
            colorBox.style.borderColor = colors[colorValue]?.replace('0.4', '0.8') || colors.gray;
        }
        
        const label = document.createElement('span');
        label.textContent = `${config.name} (${count})`;
        
        // Toggle visibility on checkbox change
        checkbox.addEventListener('change', (e) => {
            const show = e.target.checked;
            document.querySelectorAll(`.highlight-type-${type}`).forEach(h => {
                h.style.display = show ? 'block' : 'none';
            });
            legendItem.classList.toggle('inactive', !show);
        });
        
        legendItem.appendChild(checkbox);
        legendItem.appendChild(colorBox);
        legendItem.appendChild(label);
        legendItems.appendChild(legendItem);
    }
}

/**
 * Setup review mode functionality
 */
function setupReviewMode() {
    // Already set up via toggle function
    // This can be used for initial setup if needed
}

// Extract lease data from PDF and populate form
async function extractAndPopulateForm(file) {
    console.log('📥 Starting extraction for file:', file.name);
    
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
        showAlert('Please select a PDF file', 'warning');
        return;
    }
    
    // Check for stored API key first
    let storedApiKey = localStorage.getItem('google_ai_api_key');
    
    // Default API key (user provided)
    if (!storedApiKey || !storedApiKey.trim()) {
        storedApiKey = 'AIzaSyCm96pgKZ1tXA73_2m8XXDbj04WCpYp76g';
        localStorage.setItem('google_ai_api_key', storedApiKey);
        console.log('✅ Using default API key and storing in localStorage');
    }
    
    let apiKey = storedApiKey.trim();
    console.log('✅ Using API key from localStorage');
    
    // Show loading overlay
    console.log('⏳ Showing extraction loader...');
    try {
        showExtractionLoader();
        console.log('✅ Loader shown');
    } catch (error) {
        console.error('❌ Error showing loader:', error);
    }
    
    // Show loading indicator on button
    const uploadBtn = document.getElementById('uploadBtn');
    if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.textContent = 'Extracting...';
    }
    
    try {
        // Create FormData
        const formData = new FormData();
        formData.append('file', file);
        console.log('📦 FormData created, file size:', file.size, 'bytes');
        
        // Add API key if provided (or backend will use environment variable)
        if (apiKey && apiKey.trim()) {
            formData.append('api_key', apiKey.trim());
            console.log('🔑 API key added to form');
        } else {
            console.log('🔑 No API key provided, backend will use env var');
        }
        
        // Call extraction API
        console.log('🌐 Sending request to /api/extract_lease_pdf...');
        const startTime = Date.now();
        
        const response = await fetch('/api/extract_lease_pdf', {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        
        const requestTime = Date.now() - startTime;
        console.log(`⏱️ Request completed in ${requestTime}ms, status: ${response.status}`);
        
        // Check if response is OK
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ Response not OK:', response.status, errorText);
            hideExtractionLoader();
            let errorMsg = `Server error (${response.status})`;
            try {
                const errorJson = JSON.parse(errorText);
                errorMsg = errorJson.error || errorMsg;
            } catch (e) {
                errorMsg = errorText || errorMsg;
            }
            showAlert(`❌ Error: ${errorMsg}`, 'error');
            if (uploadBtn) {
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload Contract – AI Extraction';
            }
            return;
        }
        
        // Parse JSON response
        let result;
        try {
            result = await response.json();
            console.log('✅ Response parsed:', result.success ? 'Success' : 'Failed');
        } catch (parseError) {
            console.error('❌ Error parsing JSON response:', parseError);
            hideExtractionLoader();
            showAlert('❌ Error: Invalid response from server. Please check console for details.', 'error');
            if (uploadBtn) {
                uploadBtn.disabled = false;
                uploadBtn.textContent = 'Upload Contract – AI Extraction';
            }
            return;
        }
        
        // Hide loading overlay
        console.log('⏳ Hiding loader...');
        hideExtractionLoader();
        
        if (result.success && result.data) {
            console.log('✅ Extraction successful, fields extracted:', Object.keys(result.data).length);
            
            // Map extracted data to form fields
            try {
                mapExtractedDataToForm(result.data);
                console.log('✅ Form populated with extracted data');
            } catch (mapError) {
                console.error('❌ Error mapping data to form:', mapError);
            }
            
            // Display PDF in viewer
            try {
                displayUploadedPDF(file);
                console.log('✅ PDF displayed in viewer');
            } catch (displayError) {
                console.error('❌ Error displaying PDF:', displayError);
            }
            
            showAlert('✅ Lease data extracted and form populated successfully!', 'success');
        } else {
            const errorMsg = result.error || 'Failed to extract lease data';
            console.error('❌ Extraction failed:', errorMsg);
            let errorDisplay = `❌ Error: ${errorMsg}`;
            if (result.help) {
                errorDisplay += `\n\n${result.help}`;
            }
            showAlert(errorDisplay, 'error');
        }
    } catch (error) {
        console.error('❌ Error extracting lease data:', error);
        console.error('   Stack:', error.stack);
        hideExtractionLoader();
        const errorMsg = error.message || 'Failed to extract lease data';
        showAlert(`❌ Error: ${errorMsg}\n\nPlease check the browser console for more details.`, 'error');
    } finally {
        // Reset button
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.textContent = 'Upload Contract – AI Extraction';
        }
    }
}

// Show extraction loader overlay
function showExtractionLoader() {
    console.log('🎬 showExtractionLoader called');
    
    // Remove existing loader if any
    let loader = document.getElementById('extractionLoader');
    if (loader) {
        console.log('🗑️ Removing existing loader');
        loader.remove();
    }
    
    // Create loader overlay
    loader = document.createElement('div');
    loader.id = 'extractionLoader';
    loader.className = 'extraction-loader-overlay';
    loader.style.display = 'flex'; // Ensure it's visible
    loader.style.zIndex = '10000'; // Ensure it's on top
    loader.innerHTML = `
        <div class="extraction-loader-content">
            <div class="extraction-spinner">
                <div class="spinner-ring"></div>
                <div class="spinner-ring"></div>
                <div class="spinner-ring"></div>
            </div>
            <div class="extraction-loader-text">
                <h3>🤖 AI Extraction in Progress</h3>
                <p>Extracting lease fields from PDF...</p>
                <div class="extraction-steps">
                    <div class="step active">📄 Reading PDF</div>
                    <div class="step">🔍 Extracting Text</div>
                    <div class="step">🧠 AI Processing</div>
                    <div class="step">✅ Populating Form</div>
                </div>
            </div>
        </div>
    `;
    
    try {
        document.body.appendChild(loader);
        console.log('✅ Loader appended to body');
        
        // Force visibility
        setTimeout(() => {
            if (loader && loader.parentNode) {
                loader.style.display = 'flex';
                loader.style.opacity = '1';
                console.log('✅ Loader visibility ensured');
            }
        }, 100);
    } catch (error) {
        console.error('❌ Error appending loader:', error);
    }
    
    // Animate steps
    let currentStep = 0;
    const steps = loader.querySelectorAll('.step');
    const stepInterval = setInterval(() => {
        if (currentStep < steps.length) {
            steps[currentStep].classList.add('active');
            currentStep++;
        } else {
            clearInterval(stepInterval);
        }
    }, 1500);
    
    // Store interval for cleanup
    loader._stepInterval = stepInterval;
}

// Hide extraction loader
function hideExtractionLoader() {
    console.log('🛑 hideExtractionLoader called');
    const loader = document.getElementById('extractionLoader');
    if (loader) {
        // Clear interval
        if (loader._stepInterval) {
            clearInterval(loader._stepInterval);
        }
        // Fade out
        loader.style.opacity = '0';
        loader.style.transition = 'opacity 0.3s ease-out';
        setTimeout(() => {
            if (loader && loader.parentNode) {
                loader.remove();
                console.log('✅ Loader removed');
            }
        }, 300);
    } else {
        console.log('⚠️ No loader found to hide');
    }
}

// Show API Key Modal
function showApiKeyModal() {
    return new Promise((resolve, reject) => {
        try {
            console.log('🔑 Creating API key modal...');
            
            // Check for stored API key first
            const storedApiKey = localStorage.getItem('google_ai_api_key');
            
            // Check if modal already exists
            let modal = document.getElementById('apiKeyModal');
            if (!modal) {
                // Create modal
                modal = document.createElement('div');
                modal.id = 'apiKeyModal';
                modal.className = 'modal';
                modal.style.display = 'none'; // Start hidden
                modal.style.zIndex = '10001'; // Higher than loader
                modal.innerHTML = `
                    <div class="modal-content" style="max-width: 500px;">
                        <div class="modal-header">
                            <h2>Google AI API Key</h2>
                            <button class="modal-close" onclick="closeApiKeyModal()">&times;</button>
                        </div>
                        <div class="modal-body">
                            <p style="margin-bottom: 15px; color: #666;">
                                Enter your Google Gemini API key for AI extraction. 
                                Leave empty to use environment variable (if set).
                            </p>
                            <div class="form-group">
                                <label>
                                    API Key
                                    <span class="tooltip-icon" title="Get your free API key from https://makersuite.google.com/app/apikey">?</span>
                                </label>
                                <input type="password" id="apiKeyInput" placeholder="Enter API key or leave empty for env var" style="width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">
                            </div>
                            <div style="margin-top: 10px;">
                                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer;">
                                    <input type="checkbox" id="saveApiKey" checked>
                                    <span style="font-size: 14px; color: #666;">Save API key for future use</span>
                                </label>
                            </div>
                            <p style="margin-top: 10px; font-size: 12px; color: #999;">
                                💡 <a href="https://makersuite.google.com/app/apikey" target="_blank" style="color: #3498db;">Get your free API key here</a>
                            </p>
                        </div>
                        <div class="modal-footer">
                            <button class="btn-secondary" onclick="closeApiKeyModal()">Cancel</button>
                            <button class="btn-primary" onclick="submitApiKey()">Continue</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
                console.log('✅ API key modal created');
            }
            
            // Pre-fill stored API key if available
            const input = document.getElementById('apiKeyInput');
            const saveCheckbox = document.getElementById('saveApiKey');
            if (storedApiKey && input) {
                input.value = storedApiKey;
                console.log('✅ Pre-filled stored API key');
            }
            
            // Store resolve function for later use
            window._apiKeyResolve = resolve;
            window._apiKeyReject = reject;
            
            // Show modal - force all styles
            modal.style.display = 'block';
            modal.style.position = 'fixed';
            modal.style.zIndex = '10001';
            modal.style.left = '0';
            modal.style.top = '0';
            modal.style.width = '100%';
            modal.style.height = '100%';
            modal.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
            modal.classList.add('show');
            console.log('✅ API key modal shown');
            
            // Force visibility check
            setTimeout(() => {
                const computedStyle = window.getComputedStyle(modal);
                const modalRect = modal.getBoundingClientRect();
                console.log('🔍 Modal visibility check:', {
                    display: computedStyle.display,
                    visibility: computedStyle.visibility,
                    zIndex: computedStyle.zIndex,
                    width: computedStyle.width,
                    height: computedStyle.height,
                    rect: modalRect
                });
                
                // Ensure modal is visible
                if (computedStyle.display === 'none' || computedStyle.zIndex < '10001') {
                    console.warn('⚠️ Modal not visible, forcing...');
                    modal.style.cssText = `
                        display: block !important;
                        position: fixed !important;
                        z-index: 10001 !important;
                        left: 0 !important;
                        top: 0 !important;
                        width: 100% !important;
                        height: 100% !important;
                        background-color: rgba(0, 0, 0, 0.6) !important;
                        overflow: auto !important;
                    `;
                }
            }, 100);
            
            // Focus on input
            if (input) {
                setTimeout(() => {
                    input.focus();
                    input.select();
                }, 100);
                // Allow Enter key to submit
                input.onkeypress = function(e) {
                    if (e.key === 'Enter') {
                        submitApiKey();
                    }
                };
            }
            
            // Timeout after 60 seconds to prevent hanging
            window._apiKeyTimeout = setTimeout(() => {
                if (window._apiKeyResolve === resolve) {
                    console.warn('⚠️ API key modal timeout');
                    closeApiKeyModal();
                    reject(new Error('API key modal timeout'));
                }
            }, 60000);
        } catch (error) {
            console.error('❌ Error creating API key modal:', error);
            reject(error);
        }
    });
}

// Close API Key Modal
function closeApiKeyModal() {
    console.log('🔒 Closing API key modal');
    const modal = document.getElementById('apiKeyModal');
    if (modal) {
        modal.style.display = 'none';
    }
    
    // Clear timeout
    if (window._apiKeyTimeout) {
        clearTimeout(window._apiKeyTimeout);
        window._apiKeyTimeout = null;
    }
    
    if (window._apiKeyResolve) {
        window._apiKeyResolve(null); // User cancelled
        window._apiKeyResolve = null;
    }
    if (window._apiKeyReject) {
        window._apiKeyReject = null;
    }
}

// Submit API Key
function submitApiKey() {
    console.log('✅ Submitting API key');
    const input = document.getElementById('apiKeyInput');
    const saveCheckbox = document.getElementById('saveApiKey');
    const apiKey = input ? input.value : '';
    const shouldSave = saveCheckbox ? saveCheckbox.checked : false;
    
    // Save to localStorage if checkbox is checked
    if (shouldSave && apiKey && apiKey.trim()) {
        localStorage.setItem('google_ai_api_key', apiKey.trim());
        console.log('✅ API key saved to localStorage');
    } else if (!shouldSave) {
        // Remove if unchecked
        localStorage.removeItem('google_ai_api_key');
        console.log('🗑️ API key removed from localStorage');
    }
    
    // Clear timeout
    if (window._apiKeyTimeout) {
        clearTimeout(window._apiKeyTimeout);
        window._apiKeyTimeout = null;
    }
    
    closeApiKeyModal();
    
    if (window._apiKeyResolve) {
        window._apiKeyResolve(apiKey); // Return API key (empty string is OK - will use env var)
        window._apiKeyResolve = null;
    }
}

// Map extracted data from AI to form fields
function mapExtractedDataToForm(extractedData) {
    const form = document.getElementById('leaseForm');
    if (!form) return;
    
    // Field mapping from AI extraction keys to form field names
    const fieldMapping = {
        'description': 'agreement_title',
        'asset_class': 'asset_class',
        'asset_id_code': 'asset_title',
        'lease_start_date': 'lease_start_date',
        'end_date': 'lease_end_date',
        'agreement_date': 'rent_agreement_date',
        'first_payment_date': 'first_payment_date',
        'tenure': null, // Calculated field
        'frequency_months': 'rent_frequency',
        'day_of_month': 'pay_day_of_month',
        'rental_1': 'rental_amount',
        'currency': 'currency',
        'compound_months': 'compound_months',
        'security_deposit': 'security_deposit_amount_1',
        'esc_freq_months': 'escalation_frequency',
        'escalation_percent': null, // Not in current form
        'escalation_start_date': 'escalation_start_date',
        'lease_incentive': 'lease_incentive',
        'initial_direct_expenditure': 'initial_direct_expenditure',
        'counterparty': 'counterparty',
        'group_entity_name': 'company_name',
        'finance_lease': 'lease_classification',
        'sublease': null,
        'bargain_purchase': null,
        'title_transfer': null,
        'practical_expedient': null,
        'short_term_ifrs': 'scope_exemption',
        'manual_adj': null,
        'additional_info': 'judgements'
    };
    
    // Populate form fields
    for (const [extractKey, formFieldName] of Object.entries(fieldMapping)) {
        const value = extractedData[extractKey];
        if (!formFieldName || value === null || value === undefined || value === '') {
            continue;
        }
        
        const field = form.querySelector(`[name="${formFieldName}"]`);
        if (!field) continue;
        
        try {
            // Handle different field types
            if (field.type === 'checkbox') {
                field.checked = value === 'Yes' || value === true || value === 1 || value === '1';
            } else if (field.type === 'date') {
                if (value) {
                    // Ensure date format is YYYY-MM-DD
                    let dateValue = value;
                    if (typeof dateValue === 'string' && dateValue.includes(' ')) {
                        dateValue = dateValue.split(' ')[0];
                    }
                    field.value = dateValue;
                }
            } else if (field.tagName === 'SELECT') {
                // For selects, try to match value
                const option = Array.from(field.options).find(opt => 
                    opt.value.toLowerCase() === String(value).toLowerCase() ||
                    opt.text.toLowerCase().includes(String(value).toLowerCase())
                );
                if (option) {
                    field.value = option.value;
                } else {
                    field.value = value;
                }
            } else {
                // Text, number inputs
                field.value = value;
            }
            
            // Trigger change events for fields with handlers
            if (field.onchange) {
                field.onchange();
            } else {
                field.dispatchEvent(new Event('change'));
            }
        } catch (error) {
            console.warn(`Error populating field ${formFieldName}:`, error);
        }
    }
    
        // Special handling for lease classification
        if (extractedData.finance_lease) {
            const classificationField = form.querySelector('[name="lease_classification"]');
            if (classificationField) {
                classificationField.value = extractedData.finance_lease === 'Yes' ? 'finance' : 'operating';
                classificationField.dispatchEvent(new Event('change'));
            }
        }
        
        // Special handling for scope exemption
        if (extractedData.short_term_ifrs) {
            const scopeField = form.querySelector('[name="scope_exemption"]');
            if (scopeField) {
                if (extractedData.short_term_ifrs === 'Yes') {
                    scopeField.value = 'short_term';
                } else if (extractedData.low_value !== undefined && extractedData.low_value === 'Yes') {
                    scopeField.value = 'low_value';
                } else {
                    scopeField.value = 'no';
                }
                scopeField.dispatchEvent(new Event('change'));
            }
        }
        
        // Handle payment type based on day_of_month
        if (extractedData.day_of_month === 'Last' || extractedData.day_of_month === 'last') {
            const paymentTypeField = form.querySelector('[name="payment_type"]');
            if (paymentTypeField) {
                paymentTypeField.value = 'arrear';
                if (typeof handlePaymentType === 'function') {
                    handlePaymentType(paymentTypeField);
                }
            }
        }
        
        // Handle frequency mapping - convert number to select value
        if (extractedData.frequency_months) {
            const freqField = form.querySelector('[name="rent_frequency"]');
            if (freqField) {
                const freqValue = String(extractedData.frequency_months);
                freqField.value = freqValue;
                if (typeof updatePaymentInterval === 'function') {
                    updatePaymentInterval(freqField);
                }
            }
        }
        
        // Update payment interval if frequency is set
        if (extractedData.frequency_months) {
            const intervalField = form.querySelector('[name="payment_interval"]');
            if (intervalField) {
                intervalField.value = extractedData.frequency_months;
            }
        }
        
        // Trigger all change handlers
        const inputs = form.querySelectorAll('input, select, textarea');
        inputs.forEach(input => {
            if (input.onchange) {
                try {
                    input.onchange();
                } catch (e) {
                    // Ignore errors
                }
            }
        });
        
        console.log('✅ Form populated with extracted data');
    }

// Display uploaded PDF in viewer
function displayUploadedPDF(file) {
    const pdfViewer = document.getElementById('pdfViewer');
    const pdfFrame = document.getElementById('pdfFrame');
    
    if (pdfViewer && pdfFrame) {
        const reader = new FileReader();
        reader.onload = function(e) {
            pdfFrame.src = e.target.result;
            pdfViewer.style.display = 'block';
        };
        reader.readAsDataURL(file);
    }
}

// Load Lease Data for Editing
async function loadLeaseData(leaseId) {
    try {
        const user = await getCurrentUser();
        const response = await fetch(`/api/leases/${leaseId}`, {
            method: 'GET',
            credentials: 'include'
        });
        
        const result = await response.json();
        if (result.success && result.lease) {
            if (user && user.role === 'admin') {
                result.lease.username = user.username;
            }
            const lease = result.lease;
            const form = document.getElementById('leaseForm');
            
            // Debug: log lease data
            console.log('📋 Loading lease data:', lease);
            console.log('🔍 rental_schedule in response:', lease.rental_schedule, 'Type:', typeof lease.rental_schedule);
            
            // Map database field names to form field names
            // Database uses 'ibr' - form field is also 'ibr'
            const fieldMapping = {
                'ibr': 'ibr',  // Database column 'ibr' maps to form field 'ibr'
                // All other fields match database column names exactly
            };
            
            // Populate all form fields
            for (const [key, value] of Object.entries(lease)) {
                // Skip internal fields and JSON fields (handled separately)
                if (key === 'lease_id' || key === 'user_id' || key === 'created_at' || key === 'updated_at' 
                    || key === 'rental_schedule' || key === 'sublease_payment_details') {
                    continue;
                }
                
                // Use mapped field name if exists, otherwise use key as-is
                const formFieldName = fieldMapping[key] || key;
                let field = form.querySelector(`[name="${formFieldName}"]`);
                
                // If not found, try case-insensitive search
                if (!field) {
                    const allFields = form.querySelectorAll(`[name]`);
                    for (const f of allFields) {
                        if (f.name && f.name.toLowerCase() === formFieldName.toLowerCase()) {
                            field = f;
                            break;
                        }
                    }
                }
                
                if (field) {
                    try {
                        if (field.type === 'checkbox') {
                            // Handle checkboxes - database stores 0/1 (INTEGER), convert to boolean
                            // Accept: 1, true, '1', 'true', 'on' as checked
                            // Accept: 0, false, '0', 'false', '', null, undefined as unchecked
                            const checked = value === 1 || value === true || value === '1' || String(value).toLowerCase() === 'true' || String(value).toLowerCase() === 'on';
                            field.checked = checked;
                            
                            // Trigger change event if checkbox has onChange handler (for toggle handlers)
                            // Use setTimeout to ensure DOM is ready and functions are defined
                            setTimeout(() => {
                                if (field.onchange || field.getAttribute('onchange')) {
                                    try {
                                        const changeEvent = new Event('change', { bubbles: true });
                                        field.dispatchEvent(changeEvent);
                                    } catch (e) {
                                        // If the handler function doesn't exist yet, ignore it
                                        console.warn(`⚠️ Error triggering change event for ${formFieldName}:`, e);
                                    }
                                }
                            }, 100);
                        } else if (field.type === 'date') {
                            // Handle dates - convert to YYYY-MM-DD format
                            if (value) {
                                let dateValue = value;
                                // If it's a datetime string, extract just the date part
                                if (typeof dateValue === 'string' && dateValue.includes(' ')) {
                                    dateValue = dateValue.split(' ')[0];
                                }
                                // If it's a date object or ISO string, format it
                                if (dateValue instanceof Date) {
                                    dateValue = dateValue.toISOString().split('T')[0];
                                } else if (dateValue.match(/^\d{4}-\d{2}-\d{2}$/)) {
                                    // Already in correct format
                                } else if (dateValue.match(/^\d{2}\/\d{2}\/\d{4}$/)) {
                                    // Convert DD/MM/YYYY to YYYY-MM-DD
                                    const parts = dateValue.split('/');
                                    dateValue = `${parts[2]}-${parts[1]}-${parts[0]}`;
                                }
                                field.value = dateValue || '';
                            } else {
                                field.value = '';
                            }
                        } else if (field.type === 'number') {
                            // Handle numeric fields
                            if (value !== null && value !== undefined && value !== '') {
                                const numValue = parseFloat(value);
                                if (!isNaN(numValue)) {
                                    field.value = numValue;
                                } else {
                                    field.value = value || '';
                                }
                            } else {
                                field.value = '';
                            }
                        } else if (field.tagName === 'SELECT') {
                            // Handle select dropdowns
                            const stringValue = String(value || '');
                            // Try exact match first
                            if (field.querySelector(`option[value="${stringValue}"]`)) {
                                field.value = stringValue;
                            } else {
                                // Try case-insensitive match
                                const options = field.querySelectorAll('option');
                                for (const opt of options) {
                                    if (String(opt.value).toLowerCase() === stringValue.toLowerCase()) {
                                        field.value = opt.value;
                                        break;
                                    }
                                }
                                // If still no match, set directly (might be dynamic select)
                                if (!field.value) {
                                    field.value = stringValue;
                                }
                            }
                        } else if (field.tagName === 'TEXTAREA') {
                            // Handle textareas
                            field.value = value || '';
                        } else {
                            // Handle text inputs and other fields
                            field.value = value || '';
                        }
                    } catch (error) {
                        console.warn(`⚠️ Error populating field '${formFieldName}':`, error);
                    }
                } else {
                    // Debug: log fields that weren't found (only for important fields)
                    const importantFields = ['ibr', 'lease_start_date', 'lease_end_date', 
                                            'first_payment_date', 'rental_amount', 'escalation_percentage'];
                    if (importantFields.includes(key) || importantFields.includes(formFieldName)) {
                        console.warn(`⚠️ Field '${key}' → '${formFieldName}' (value: ${value}) not found in form`);
                        // Special handling for ibr field
                        if (key === 'ibr' && value !== null && value !== undefined && value !== '') {
                            const ibrField = form.querySelector('[name="ibr"]');
                            if (ibrField) {
                                console.log(`✅ Found ibr field, populating with ${key} value: ${value}`);
                                const numValue = parseFloat(value);
                                if (!isNaN(numValue)) {
                                    ibrField.value = numValue;
                                }
                            }
                        }
                    }
                }
            }
            
            // Ensure IBR field is populated - ALWAYS overwrite with database value
            // This is done after the loop to ensure IBR always reflects what's in the database
            const ibrField = form.querySelector('[name="ibr"]');
            if (ibrField) {
                // Get IBR value from lease data - database uses 'ibr'
                const ibrValue = lease.ibr;
                let dbIbrValue = null;
                
                // Check if ibrValue exists and is valid
                if (ibrValue !== null && ibrValue !== undefined && ibrValue !== '') {
                    const numValue = parseFloat(ibrValue);
                    if (!isNaN(numValue)) {
                        dbIbrValue = numValue;
                    }
                }
                
                // ALWAYS update the field with the database value, regardless of current value
                // This ensures the form always reflects what's in the database
                console.log(`🔍 IBR update check: dbValue=${dbIbrValue}, currentFieldValue=${ibrField.value}, lease.ibr=${lease.ibr} (type: ${typeof lease.ibr})`);
                
                if (dbIbrValue !== null && dbIbrValue !== undefined) {
                    // Always overwrite, even if value looks the same
                    console.log(`✅ FORCE UPDATING IBR field with database value: ${dbIbrValue} (was: ${ibrField.value})`);
                    ibrField.value = dbIbrValue;
                    // Trigger input event to ensure any listeners are notified
                    ibrField.dispatchEvent(new Event('input', { bubbles: true }));
                    ibrField.dispatchEvent(new Event('change', { bubbles: true }));
                } else if (ibrValue === null || ibrValue === undefined || ibrValue === '') {
                    // If database explicitly has null/empty, clear the field
                    console.log(`✅ CLEARING IBR field (database value is null/empty)`);
                    ibrField.value = '';
                    ibrField.dispatchEvent(new Event('input', { bubbles: true }));
                    ibrField.dispatchEvent(new Event('change', { bubbles: true }));
                }
            } else {
                console.error('❌ IBR field not found in form!');
            }
            
            // Special handling for dependent fields
            // Update tenure if dates are populated
            if (lease.lease_start_date && lease.lease_end_date) {
                setTimeout(() => updateTenureFromDates(), 100);
            }
            
            // Update rent accrual day if lease start date is populated
            if (lease.lease_start_date && !lease.rent_accrual_day) {
                setTimeout(() => updateRentAccrualDayFromStartDate(), 100);
            }
            
            // Update status
            const statusEl = document.getElementById('formStatus');
            if (statusEl) {
                statusEl.textContent = lease.status || 'Draft';
            }
            
            // Trigger toggle handlers for checkboxes - handle safely
            // Skip this if functions aren't defined yet, to avoid errors
            const checkboxes = form.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(cb => {
                const onchangeAttr = cb.getAttribute('onchange');
                if (onchangeAttr) {
                    // Check if the function exists before triggering
                    const funcMatch = onchangeAttr.match(/(\w+)\s*\(/);
                    if (funcMatch && typeof window[funcMatch[1]] === 'function') {
                        setTimeout(() => {
                            try {
                                const changeEvent = new Event('change', { bubbles: true });
                                cb.dispatchEvent(changeEvent);
                            } catch (e) {
                                console.warn(`⚠️ Error triggering checkbox handler for ${cb.name}:`, e);
                            }
                        }, 150);
                    }
                } else if (cb.onchange) {
                    setTimeout(() => {
                        try {
                            cb.onchange();
                        } catch (e) {
                            console.warn(`⚠️ Error calling checkbox handler for ${cb.name}:`, e);
                        }
                    }, 150);
                }
            });
            
            // Update Rent Accrual Day if lease start date is loaded and accrual day is not set
            const rentAccrualDayInput = form.querySelector('input[name="rent_accrual_day"]');
            const leaseStartDateInput = document.getElementById('lease_start_date');
            if (rentAccrualDayInput && leaseStartDateInput && leaseStartDateInput.value) {
                if (!rentAccrualDayInput.value || rentAccrualDayInput.value === '') {
                    updateRentAccrualDayFromStartDate();
                }
            }
            
            // Populate rental schedule table if rental_schedule exists
            console.log('🔍 Checking rental_schedule:', lease.rental_schedule, 'Type:', typeof lease.rental_schedule, 'Is Array:', Array.isArray(lease.rental_schedule));
            if (lease.rental_schedule) {
                // Handle both string (if not parsed) and array formats
                let rentalSchedule = lease.rental_schedule;
                if (typeof rentalSchedule === 'string') {
                    try {
                        rentalSchedule = JSON.parse(rentalSchedule);
                        console.log('✅ Parsed rental_schedule from string:', rentalSchedule);
                    } catch (e) {
                        console.error('❌ Error parsing rental_schedule:', e);
                        rentalSchedule = null;
                    }
                }
                
                if (Array.isArray(rentalSchedule) && rentalSchedule.length > 0) {
                    console.log('📋 Populating rental schedule table with', rentalSchedule.length, 'rows:', rentalSchedule);
                    populateRentalScheduleTable(rentalSchedule);
                } else {
                    console.warn('⚠️ rental_schedule is not a valid array or is empty:', rentalSchedule);
                }
            } else {
                console.warn('⚠️ rental_schedule field is missing or empty in lease data');
            }
            
            // Populate sublease payment details if exists (for future use)
            if (lease.sublease_payment_details) {
                console.log('📋 Sublease payment details found:', lease.sublease_payment_details);
                // TODO: Implement sublease payment details population if needed
            }
            
            // Log any fields that weren't populated for debugging
            console.log('✅ Lease data loaded and form populated');
        }
    } catch (error) {
        console.error('Error loading lease data:', error);
    }
}

// Toggle section accordion
function toggleSection(header) {
    const section = header.parentElement;
    const content = section.querySelector('.section-content');
    const icon = header.querySelector('.toggle-icon');
    
    content.classList.toggle('active');
    icon.style.transform = content.classList.contains('active') ? 'rotate(180deg)' : 'rotate(0deg)';
}

// Asset Class Management
function loadAssetClassesFromStorage() {
    const stored = localStorage.getItem('assetClasses');
    if (stored) {
        return JSON.parse(stored);
    }
    return ['Land', 'Building', 'Vehicle', 'Equipment', 'Plant and Machinery'];
}

function saveAssetClassesToStorage(classes) {
    localStorage.setItem('assetClasses', JSON.stringify(classes));
}

let assetClasses = loadAssetClassesFromStorage();

function openAssetClassModal() {
    const modal = document.getElementById('assetClassModal');
    modal.style.display = 'block';
    loadAssetClasses();
}

function closeAssetClassModal() {
    const modal = document.getElementById('assetClassModal');
    modal.style.display = 'none';
}

function loadAssetClasses() {
    const ul = document.getElementById('assetClassesUl');
    ul.innerHTML = assetClasses.map((ac, index) => `
        <li class="asset-class-item">
            <span>${ac}</span>
            <button type="button" class="btn-remove-small" onclick="removeAssetClass(${index})">Remove</button>
        </li>
    `).join('');
}

function addAssetClass() {
    const input = document.getElementById('newAssetClass');
    const value = input.value.trim();
    
    if (!value) {
        showModal('Error', 'Please enter an asset class name');
        return;
    }
    
    if (assetClasses.includes(value)) {
        showModal('Error', 'Asset class already exists');
        return;
    }
    
    assetClasses.push(value);
    saveAssetClassesToStorage(assetClasses);
    updateAssetClassDropdown();
    loadAssetClasses();
    input.value = '';
}

function removeAssetClass(index) {
    if (confirm(`Remove "${assetClasses[index]}"?`)) {
        assetClasses.splice(index, 1);
        saveAssetClassesToStorage(assetClasses);
        updateAssetClassDropdown();
        loadAssetClasses();
    }
}

function updateAssetClassDropdown() {
    const select = document.getElementById('assetClassSelect');
    const currentValue = select.value;
    
    select.innerHTML = '<option value="">Select asset class</option>' +
        assetClasses.map(ac => `<option value="${ac}">${ac}</option>`).join('');
    
    if (currentValue && assetClasses.includes(currentValue)) {
        select.value = currentValue;
    }
}

// Highlight Category Management Functions
function openHighlightCategoryModal() {
    const modal = document.getElementById('highlightCategoryModal');
    modal.style.display = 'block';
    renderHighlightCategories();
}

function closeHighlightCategoryModal() {
    const modal = document.getElementById('highlightCategoryModal');
    modal.style.display = 'none';
}

function renderHighlightCategories() {
    const container = document.getElementById('highlightCategoriesList');
    if (!container) return;
    
    container.innerHTML = highlightCategories.map((cat, index) => `
        <div class="highlight-category-item" style="margin-bottom: 15px; padding: 12px; border: 1px solid #e0e0e0; border-radius: 4px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                <input type="text" id="cat-name-${index}" value="${cat.name}" 
                       style="flex: 1; padding: 6px; border: 1px solid #ccc; border-radius: 3px;"
                       onchange="updateHighlightCategoryName(${index}, this.value)">
                <input type="color" id="cat-color-${index}" value="#${getColorHex(cat.color)}" 
                       style="width: 50px; height: 35px; border: 1px solid #ccc; border-radius: 3px; cursor: pointer;"
                       onchange="updateHighlightCategoryColor(${index}, this.value)">
                <button type="button" class="btn-remove-small" onclick="removeHighlightCategory(${index})">Remove</button>
            </div>
            <div style="font-size: 12px; color: #666;">
                <strong>Fields:</strong> ${cat.fields.join(', ')}
            </div>
        </div>
    `).join('');
}

function getColorHex(colorName) {
    const colorMap = {
        purple: '9C27B0',
        green: '4CAF50',
        blue: '2196F3',
        orange: 'FF9800',
        gray: '9E9E9E',
        pink: 'E91E63',
        teal: '009688',
        indigo: '3F51B5'
    };
    return colorMap[colorName] || '9E9E9E';
}

function updateHighlightCategoryName(index, newName) {
    if (highlightCategories[index]) {
        highlightCategories[index].name = newName;
        saveHighlightCategoriesToStorage(highlightCategories);
        // Rebuild FIELD_TYPES
        Object.keys(FIELD_TYPES).forEach(key => delete FIELD_TYPES[key]);
        highlightCategories.forEach(cat => {
            FIELD_TYPES[cat.id] = {
                fields: cat.fields,
                color: cat.color,
                name: cat.name
            };
        });
        // Re-render legend if in review mode
        if (isReviewMode) {
            buildFieldTypeLegend();
        }
    }
}

function updateHighlightCategoryColor(index, colorHex) {
    if (highlightCategories[index]) {
        // Convert hex to color name if possible, or store hex
        highlightCategories[index].color = colorHex.replace('#', '');
        saveHighlightCategoriesToStorage(highlightCategories);
        // Rebuild FIELD_TYPES
        Object.keys(FIELD_TYPES).forEach(key => delete FIELD_TYPES[key]);
        highlightCategories.forEach(cat => {
            FIELD_TYPES[cat.id] = {
                fields: cat.fields,
                color: cat.color,
                name: cat.name
            };
        });
        // Re-render PDF highlights with new colors
        if (pdfDocument && renderedPages.length > 0) {
            reRenderPDF();
        }
    }
}

function removeHighlightCategory(index) {
    if (confirm(`Remove highlight category "${highlightCategories[index].name}"?`)) {
        highlightCategories.splice(index, 1);
        saveHighlightCategoriesToStorage(highlightCategories);
        // Rebuild FIELD_TYPES
        Object.keys(FIELD_TYPES).forEach(key => delete FIELD_TYPES[key]);
        highlightCategories.forEach(cat => {
            FIELD_TYPES[cat.id] = {
                fields: cat.fields,
                color: cat.color,
                name: cat.name
            };
        });
        renderHighlightCategories();
        // Re-render PDF if open
        if (pdfDocument && renderedPages.length > 0) {
            reRenderPDF();
        }
    }
}

// Initialize all sections as collapsed
document.addEventListener('DOMContentLoaded', function() {
    // Initialize asset classes dropdown
    updateAssetClassDropdown();
    
    // Expand first section by default
    const firstSection = document.querySelector('.form-section');
    if (firstSection) {
        const content = firstSection.querySelector('.section-content');
        content.classList.add('active');
    }
    
    // Set entered by field
    updateEnteredBy();
    updateLastModifiedDate();
    
    // Initialize in manual mode (hide PDF viewer)
    manualInput();
    
    // Initialize smart tooltip positioning
    initSmartTooltips();
    
    // Initialize Rent Accrual Day from Lease Start Date
    initializeRentAccrualDay();
    
           // Update Rent Accrual Day when Lease Start Date changes
           const leaseStartDateInput = document.getElementById('lease_start_date');
           if (leaseStartDateInput) {
               leaseStartDateInput.addEventListener('change', function() {
                   updateRentAccrualDayFromStartDate();
               });
           }
           
           // Initialize Transition Option requirement
           toggleTransitionOptionRequired();
           
           // Add change listener for transition date
           const transitionDateInput = document.getElementById('transition_date');
           if (transitionDateInput) {
               transitionDateInput.addEventListener('change', toggleTransitionOptionRequired);
           }

    // Initialize maker-checker controls
    initWorkflowState();

    // If opened in review mode with an id, auto-enable Review Mode and load cached PDF/highlights
    try {
        const params = new URLSearchParams(window.location.search);
        const mode = params.get('mode');
        const idParam = params.get('id');
        if (mode === 'review' && idParam) {
            const cache = localStorage.getItem(`lease_review_${idParam}`);
            if (cache) {
                const parsed = JSON.parse(cache);
                if (parsed.pdfUrl && Array.isArray(parsed.highlights)) {
                    // Ensure PDF.js is ready
                    loadPDFJS().then(async () => {
                        if (typeof pdfjsLib !== 'undefined') {
                            await renderPDFAndHighlights(parsed.pdfUrl, parsed.highlights);
                            const reviewModeBtn = document.getElementById('reviewModeBtn');
                            if (reviewModeBtn) reviewModeBtn.style.display = 'inline-block';
                            toggleReviewMode();
                        }
                    }).catch(() => {});
                }
            }
        }
    } catch(e) {}
       });

// Toggle Transition Option required field based on Transition Date
function toggleTransitionOptionRequired() {
    const transitionDateInput = document.getElementById('transition_date');
    const transitionOptionSelect = document.getElementById('transition_option');
    const requiredIndicator = document.getElementById('transition_option_required');
    
    if (transitionDateInput && transitionOptionSelect && requiredIndicator) {
        const hasTransitionDate = transitionDateInput.value && transitionDateInput.value.trim() !== '';
        
        if (hasTransitionDate) {
            // Show required indicator and make field required
            requiredIndicator.style.display = 'inline';
            transitionOptionSelect.required = true;
            transitionOptionSelect.setAttribute('required', 'required');
        } else {
            // Hide required indicator and make field optional
            requiredIndicator.style.display = 'none';
            transitionOptionSelect.required = false;
            transitionOptionSelect.removeAttribute('required');
            // Clear the value if no transition date
            if (!transitionOptionSelect.value) {
                transitionOptionSelect.value = '';
            }
        }
    }
}

// Initialize Rent Accrual Day from Lease Start Date
function initializeRentAccrualDay() {
    const rentAccrualDayInput = document.querySelector('input[name="rent_accrual_day"]');
    const leaseStartDateInput = document.getElementById('lease_start_date');
    
    if (rentAccrualDayInput && leaseStartDateInput && leaseStartDateInput.value) {
        const startDate = new Date(leaseStartDateInput.value + 'T00:00:00');
        if (!isNaN(startDate.getTime())) {
            // Only set if field is empty
            if (!rentAccrualDayInput.value || rentAccrualDayInput.value === '') {
                rentAccrualDayInput.value = startDate.getDate();
            }
        }
    }
}

// Update Rent Accrual Day when Lease Start Date changes
function updateRentAccrualDayFromStartDate() {
    const rentAccrualDayInput = document.querySelector('input[name="rent_accrual_day"]');
    const leaseStartDateInput = document.getElementById('lease_start_date');
    
    if (rentAccrualDayInput && leaseStartDateInput && leaseStartDateInput.value) {
        const startDate = new Date(leaseStartDateInput.value + 'T00:00:00');
        if (!isNaN(startDate.getTime())) {
            // Only update if field is empty or user hasn't manually changed it
            // We'll check if the value matches the old start date's day
            // For simplicity, we'll update it if it's empty or matches a reasonable default
            const currentValue = parseInt(rentAccrualDayInput.value);
            const newDay = startDate.getDate();
            
            // Update if empty or if we should sync (user hasn't customized it)
            // We'll update it if it matches the previous calculation
            if (!rentAccrualDayInput.value || rentAccrualDayInput.value === '') {
                rentAccrualDayInput.value = newDay;
            }
        }
    }
}

// Smart tooltip positioning - ensures tooltip is always visible
function initSmartTooltips() {
    const tooltips = document.querySelectorAll('.tooltip-icon[title]');
    
    tooltips.forEach(tooltip => {
        tooltip.addEventListener('mouseenter', function(e) {
            const rect = this.getBoundingClientRect();
            const tooltipText = this.getAttribute('title');
            
            // Check if we're near the top of viewport (within 200px)
            const isNearTop = rect.top < 200;
            // Check if we're near the right edge (within 350px)
            const viewportWidth = window.innerWidth;
            const isNearRight = rect.right > (viewportWidth - 350);
            
            // Set position based on viewport constraints
            // Always prefer top-right, but adjust if needed
            if (isNearTop) {
                this.setAttribute('data-tooltip-position', 'bottom-right');
            } else if (isNearRight) {
                this.setAttribute('data-tooltip-position', 'top-left');
            } else {
                this.setAttribute('data-tooltip-position', 'top-right');
            }
        });
        
        tooltip.addEventListener('mouseleave', function() {
            this.removeAttribute('data-tooltip-position');
        });
    });
}

// Toggle Posting Date field
function togglePostingDate(checkbox) {
    const postingDateField = document.getElementById('postingDateField');
    if (checkbox.checked) {
        postingDateField.style.display = 'none';
    } else {
        postingDateField.style.display = 'block';
    }
}

// Toggle Renewal Option
function toggleRenewalOption(checkbox) {
    const renewalOptions = document.getElementById('renewalOptions');
    if (checkbox.checked) {
        renewalOptions.style.display = 'block';
    } else {
        renewalOptions.style.display = 'none';
    }
}

// Add Renewal Option
function addRenewalOption() {
    const container = document.getElementById('renewalOptions');
    const newOption = document.createElement('div');
    newOption.className = 'renewal-option';
    newOption.innerHTML = `
        <div class="form-row">
            <div class="form-group">
                <label>Renewal Start Date</label>
                <input type="date" name="renewal_start_date[]">
            </div>
            <div class="form-group">
                <label>Renewal End Date</label>
                <input type="date" name="renewal_end_date[]">
            </div>
        </div>
        <button type="button" class="btn-secondary" onclick="this.parentElement.remove()">Remove</button>
    `;
    container.appendChild(newOption);
}

// Toggle Termination Option
function toggleTerminationOption(checkbox) {
    const terminationOption = document.getElementById('terminationOption');
    if (checkbox.checked) {
        terminationOption.style.display = 'block';
    } else {
        terminationOption.style.display = 'none';
    }
}

// Handle Payment Type
function handlePaymentType(select) {
    const payDaySelect = document.querySelector('select[name="pay_day_of_month"]');
    if (select.value === 'arrear' && payDaySelect) {
        payDaySelect.value = 'last';
    }
}

// Update Payment Interval
function updatePaymentInterval(select) {
    const intervalMap = {
        '1': 1,
        '3': 3,
        '6': 6,
        '12': 12
    };
    
    const intervalInput = document.querySelector('input[name="payment_interval"]');
    if (intervalMap[select.value] !== undefined) {
        intervalInput.value = intervalMap[select.value];
        intervalInput.readOnly = true;
    } else if (select.value === 'custom') {
        intervalInput.readOnly = false;
    }
}

// Calculate IRR from Fair Value
function calculateIRR(input) {
    // Placeholder for IRR calculation logic
    const irrInput = document.querySelector('input[name="irr"]');
    if (input.value && irrInput) {
        // This would typically involve complex financial calculations
        // For now, just show that it would be auto-computed
        irrInput.placeholder = 'Will be computed from fair value';
    }
}

// Auto Populate Rental with Escalation Logic
function autoPopulateRental() {
    // Get required values
    const leaseStartDate = document.getElementById('lease_start_date').value;
    const leaseEndDate = document.getElementById('lease_end_date').value;
    const rentalAmount = parseFloat(document.getElementById('rental_amount').value) || 0;
    const escalationStartDate = document.getElementById('escalation_start_date').value;
    const escalationPercentage = parseFloat(document.getElementById('escalation_percentage').value) || 0;
    const escalationFrequency = parseInt(document.getElementById('escalation_frequency').value) || 12;
    const rentFrequency = parseInt(document.querySelector('select[name="rent_frequency"]').value) || 1;
    const firstPaymentDate = document.querySelector('input[name="first_payment_date"]').value;
    const rentAccrualDay = parseInt(document.querySelector('input[name="rent_accrual_day"]').value) || null;
    const payDayOfMonth = document.querySelector('select[name="pay_day_of_month"]').value;
    
    // Validate required fields
    if (!leaseStartDate || !leaseEndDate) {
        showModal('Error', 'Please enter Lease Start Date and Lease End Date');
        return;
    }
    
    if (!rentalAmount || rentalAmount <= 0) {
        showModal('Error', 'Please enter Rental Amount in the escalation parameters section');
        return;
    }
    
    // Parse dates
    const startDate = new Date(leaseStartDate + 'T00:00:00');
    const endDate = new Date(leaseEndDate + 'T00:00:00');
    
    // Validate parsed dates
    if (isNaN(startDate.getTime())) {
        showModal('Error', 'Invalid Lease Start Date');
        return;
    }
    if (isNaN(endDate.getTime())) {
        showModal('Error', 'Invalid Lease End Date');
        return;
    }
    
    // Parse escalation start date - handle both string and Date object
    console.log('📅 Escalation Start Date raw value:', escalationStartDate, typeof escalationStartDate);
    
    let escStartDate = null;
    if (escalationStartDate) {
        if (typeof escalationStartDate === 'string' && escalationStartDate.trim() !== '') {
            const dateStr = escalationStartDate.trim();
            console.log('📅 Parsing escalation start date string:', dateStr);
            escStartDate = new Date(dateStr + 'T00:00:00');
            console.log('📅 Parsed escalation start date:', escStartDate, 'Valid:', !isNaN(escStartDate.getTime()));
            if (isNaN(escStartDate.getTime())) {
                console.error('❌ Invalid escalation start date, cannot parse:', dateStr);
                showModal('Error', 'Invalid Escalation Start Date. Please enter a valid date.');
                return;
            }
        } else if (escalationStartDate instanceof Date) {
            escStartDate = new Date(escalationStartDate);
            if (isNaN(escStartDate.getTime())) {
                console.error('❌ Invalid escalation start date object');
                showModal('Error', 'Invalid Escalation Start Date. Please enter a valid date.');
                return;
            }
        }
    } else {
        // Escalation start date is required for escalation
        if (escalationPercentage > 0) {
            console.error('❌ Escalation Start Date is required when escalation percentage is set');
            showModal('Error', 'Please enter Escalation Start Date in the escalation parameters section');
            return;
        }
    }
    
    let firstPayDate = firstPaymentDate ? new Date(firstPaymentDate + 'T00:00:00') : startDate;
    if (isNaN(firstPayDate.getTime())) {
        console.warn('Invalid first payment date, using lease start date');
        firstPayDate = startDate;
    }
    
    // Get accrual day - default to lease start date day if not specified
    let accrualDay = rentAccrualDay;
    if (!accrualDay || isNaN(accrualDay) || accrualDay < 1 || accrualDay > 31) {
        accrualDay = startDate.getDate();
    }
    
    // Get day of month for payment
    let dayOfMonth = payDayOfMonth === 'last' ? 'last' : parseInt(payDayOfMonth) || startDate.getDate();
    
    // Generate rental schedule with escalation
    const rentalRows = generateRentalSchedule(
        startDate,
        endDate,
        rentalAmount,
        escStartDate,
        escalationPercentage,
        escalationFrequency,
        rentFrequency,
        firstPayDate,
        accrualDay,
        dayOfMonth
    );
    
    // Clear existing table
    const tbody = document.getElementById('rentalTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    // Add rows to table
    rentalCount = 0;
    rentalRows.forEach((row, index) => {
        // Validate row data before creating table row
        if (!row.startDate || !row.endDate || row.startDate === '' || row.endDate === '') {
            console.warn('Skipping invalid rental row:', row);
            return;
        }
        
        rentalCount = index + 1;
        const tr = document.createElement('tr');
        
        // Ensure amount is a valid number
        const amount = isNaN(row.amount) ? 0 : parseFloat(row.amount.toFixed(2));
        const count = isNaN(row.count) ? 0 : parseInt(row.count);
        
        tr.innerHTML = `
            <td>${rentalCount}</td>
            <td><input type="date" name="rental_start_date_${rentalCount}" value="${row.startDate}"></td>
            <td><input type="date" name="rental_end_date_${rentalCount}" value="${row.endDate}"></td>
            <td><input type="number" name="rental_count_${rentalCount}" value="${count}" min="0"></td>
            <td><input type="number" name="rental_amount_${rentalCount}" value="${amount}" step="0.01" min="0"></td>
            <td><button type="button" class="file-action-btn" onclick="this.closest('tr').remove(); updateRentalNumbers()">Remove</button></td>
        `;
        tbody.appendChild(tr);
    });
    
    // Show table container
    const tableContainer = document.getElementById('rentalTableContainer');
    if (tableContainer) {
        tableContainer.style.display = 'block';
    }
}

// Generate rental schedule with escalation logic (matching VBA findrent() logic)
function generateRentalSchedule(startDate, endDate, baseAmount, escalationStartDate, escalationPercentage, escalationFrequency, rentFrequency, firstPaymentDate, accrualDay, dayOfMonth) {
    const rows = [];
    
    // Early exit if no escalation
    if (!escalationPercentage || escalationPercentage <= 0 || !escalationFrequency || escalationFrequency <= 0 || !escalationStartDate) {
        // No escalation - single period with base amount
        const rentals = calculateRentalsInPeriod(firstPaymentDate, endDate, rentFrequency);
        if (rentals > 0) {
            rows.push({
                startDate: formatDate(firstPaymentDate),
                endDate: formatDate(endDate),
                count: rentals,
                amount: baseAmount
            });
        }
        return rows;
    }
    
    // Validate escalationStartDate - check if it's a Date object or a string
    console.log('📅 generateRentalSchedule - escalationStartDate:', escalationStartDate, typeof escalationStartDate);
    
    let escStart;
    if (escalationStartDate instanceof Date) {
        escStart = new Date(escalationStartDate);
        console.log('📅 Using Date object, converted:', escStart);
    } else if (typeof escalationStartDate === 'string' && escalationStartDate.trim() !== '') {
        const dateStr = escalationStartDate.trim();
        escStart = new Date(dateStr + 'T00:00:00');
        console.log('📅 Parsing string:', dateStr, 'Result:', escStart);
    } else {
        console.error('❌ Invalid escalationStartDate type or empty:', escalationStartDate, typeof escalationStartDate);
        // Fallback: use first payment date as escalation start
        escStart = new Date(firstPaymentDate);
        console.log('📅 Using fallback firstPaymentDate:', escStart);
    }
    
    // Validate escStart date
    if (isNaN(escStart.getTime())) {
        console.error('❌ Invalid escStart date calculated from:', escalationStartDate, 'Using fallback:', firstPaymentDate);
        // Fallback: use first payment date as escalation start
        escStart = new Date(firstPaymentDate);
        if (isNaN(escStart.getTime())) {
            console.error('❌ Even fallback date is invalid!', firstPaymentDate);
            return [];
        }
    }
    
    console.log('📅 Final escStart date:', escStart, 'Year:', escStart.getFullYear(), 'Month:', escStart.getMonth(), 'Day:', escStart.getDate());
    
    // Validate accrual day - ensure it's valid for the month
    let validAccrualDay = accrualDay;
    if (!validAccrualDay || isNaN(validAccrualDay) || validAccrualDay < 1 || validAccrualDay > 31) {
        validAccrualDay = startDate.getDate();
    }
    
    // Validate startDate is valid
    if (isNaN(startDate.getTime())) {
        console.error('Invalid startDate:', startDate);
        return [];
    }
    
    // VBA findrent() logic: begind = date(Escalation_Start.year - 1, Lease_start_date.month, accrualday)
    // Ensure accrual day is valid for the month
    const begindYear = escStart.getFullYear() - 1;
    const begindMonth = startDate.getMonth();
    
    // Validate begindYear and begindMonth are valid numbers
    if (isNaN(begindYear) || isNaN(begindMonth)) {
        console.error('Invalid begindYear or begindMonth:', { begindYear, begindMonth, escStartYear: escStart.getFullYear(), startDateMonth: startDate.getMonth() });
        return [];
    }
    
    // Calculate max day for the target month
    const maxDay = new Date(begindYear, begindMonth + 1, 0).getDate();
    const validBegindDay = Math.min(validAccrualDay, maxDay);
    
    // Validate validBegindDay is a valid number
    if (isNaN(validBegindDay)) {
        console.error('Invalid validBegindDay calculated:', { validAccrualDay, maxDay, begindYear, begindMonth });
        return [];
    }
    
    const begind = new Date(begindYear, begindMonth, validBegindDay);
    
    // Validate begind
    if (isNaN(begind.getTime())) {
        console.error('Invalid begind date calculated:', { begindYear, begindMonth, validBegindDay, validAccrualDay, maxDay });
        return [];
    }
    
    // Find startd - beginning of escalation period based on frequency
    let startd = begind;
    for (let t = 1; t < 25; t++) {
        const e_date = edate(begind, rentFrequency * t);
        if (isNaN(e_date.getTime())) {
            break;
        }
        if (escStart < e_date) {
            startd = edate(begind, rentFrequency * (t - 1));
            if (isNaN(startd.getTime())) {
                startd = begind;
            }
            break;
        } else if (escStart.getTime() === e_date.getTime()) {
            startd = edate(begind, rentFrequency * t);
            if (isNaN(startd.getTime())) {
                startd = begind;
            }
            break;
        }
    }
    
    // Validate startd
    if (isNaN(startd.getTime())) {
        startd = begind;
    }
    
    // begdate1 = date(startd.year, startd.month, dayOfMonth)
    // Handle "last" day of month
    let paymentDay = dayOfMonth === 'last' ? getLastDayOfMonth(startd) : dayOfMonth;
    if (typeof paymentDay !== 'number' || paymentDay < 1 || paymentDay > 31) {
        paymentDay = startd.getDate();
    }
    // Ensure payment day is valid for the month
    const maxPaymentDay = new Date(startd.getFullYear(), startd.getMonth() + 1, 0).getDate();
    paymentDay = Math.min(paymentDay, maxPaymentDay);
    const begdate1 = new Date(startd.getFullYear(), startd.getMonth(), paymentDay);
    
    // Validate begdate1 - if invalid, use startd
    let validBegdate1 = begdate1;
    if (isNaN(validBegdate1.getTime())) {
        console.error('Invalid begdate1 calculated:', startd.getFullYear(), startd.getMonth(), paymentDay);
        validBegdate1 = startd;
    }
    
    // startd = date(startd.year, startd.month, accrualday)
    // Ensure accrual day is valid for startd's month
    const maxStartdDay = new Date(startd.getFullYear(), startd.getMonth() + 1, 0).getDate();
    const validStartdDay = Math.min(validAccrualDay, maxStartdDay);
    startd = new Date(startd.getFullYear(), startd.getMonth(), validStartdDay);
    
    // Validate startd
    if (isNaN(startd.getTime())) {
        startd = begind;
    }
    
    // offse = (startd - Escalation_Start).days
    const offse = Math.floor((startd - escStart) / (1000 * 60 * 60 * 24));
    
    // Generate rental periods based on ESCALATION FREQUENCY, not payment frequency
    // Each period represents one escalation cycle where rental amount remains constant
    let periodStartDate = new Date(Math.max(firstPaymentDate.getTime(), escStart.getTime()));
    let escalationPeriod = 0; // Track which escalation period we're in (0-based: 0, 1, 2, ...)
    
    while (periodStartDate < endDate) {
        // Calculate end date of this escalation period
        // Period ends at: escStart + (escalationPeriod + 1) * escalationFrequency months
        const escalationPeriodEndDate = edate(escStart, escalationFrequency * (escalationPeriod + 1));
        escalationPeriodEndDate.setDate(escalationPeriodEndDate.getDate() - 1); // EDATE - 1
        
        // Actual period end is the minimum of escalation period end and lease end date
        const periodEndDate = new Date(Math.min(escalationPeriodEndDate.getTime(), endDate.getTime()));
        
        // Skip if period is invalid or reversed
        if (periodStartDate >= periodEndDate || periodStartDate > endDate) {
            break;
        }
        
        // Calculate escalation amount for this period
        // Formula: baseAmount * (1 + escalationPercentage/100)^escalationPeriod
        let amount = baseAmount * Math.pow(1 + escalationPercentage / 100, escalationPeriod);
        
        // Handle offset for first period if escalation doesn't start at period boundary
        if (offse !== 0 && escalationPeriod === 0) {
            // First period spans two escalation periods due to offset
            // Calculate weighted average of two escalation amounts
            const period1End = edate(escStart, escalationFrequency);
            period1End.setDate(period1End.getDate() - 1);
            
            const period2Start = edate(escStart, escalationFrequency);
            
            // Calculate days in each sub-period
            const daysInPeriod1 = Math.floor((period1End - periodStartDate) / (1000 * 60 * 60 * 24));
            const totalDays = Math.floor((periodEndDate - periodStartDate) / (1000 * 60 * 60 * 24));
            
            if (totalDays > 0 && daysInPeriod1 > 0 && daysInPeriod1 < totalDays) {
                // Weighted average: (amount1 * days1 + amount2 * days2) / totalDays
                const amount1 = baseAmount;
                const amount2 = baseAmount * (1 + escalationPercentage / 100);
                const daysInPeriod2 = totalDays - daysInPeriod1;
                amount = (amount1 * daysInPeriod1 + amount2 * daysInPeriod2) / totalDays;
            }
        }
        
        // Validate dates before using
        if (isNaN(periodStartDate.getTime()) || isNaN(periodEndDate.getTime())) {
            console.error('Invalid date in rental period:', { periodStartDate, periodEndDate });
            break;
        }
        
        // Calculate number of rentals (payments) in this escalation period
        const rentals = calculateRentalsInPeriod(periodStartDate, periodEndDate, rentFrequency);
        
        if (rentals > 0 && periodStartDate <= periodEndDate) {
            const startDateStr = formatDate(periodStartDate);
            const endDateStr = formatDate(periodEndDate);
            
            // Validate formatted dates before adding to rows
            if (startDateStr && endDateStr && startDateStr !== '' && endDateStr !== '') {
                rows.push({
                    startDate: startDateStr,
                    endDate: endDateStr,
                    count: rentals,
                    amount: parseFloat(amount.toFixed(2))
                });
                
                console.log(`📊 Escalation Period ${escalationPeriod}: ${startDateStr} to ${endDateStr}, Amount: ${amount.toFixed(2)}, Rentals: ${rentals}`);
            } else {
                console.error('Invalid formatted dates:', { startDateStr, endDateStr, periodStartDate, periodEndDate });
            }
        }
        
        // Move to next escalation period
        periodStartDate = edate(escStart, escalationFrequency * (escalationPeriod + 1));
        escalationPeriod++;
        
        // Safety check to prevent infinite loop
        if (escalationPeriod > 1000 || periodStartDate >= endDate) {
            break;
        }
    }
    
    return rows;
}

// Helper function to get last day of month
function getLastDayOfMonth(date) {
    const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0);
    return lastDay.getDate();
}

// Calculate number of rentals in a period based on frequency
function calculateRentalsInPeriod(startDate, endDate, frequencyMonths) {
    if (startDate >= endDate) return 0;
    
    const start = new Date(startDate);
    const end = new Date(endDate);
    let count = 0;
    let currentPaymentDate = new Date(start);
    
    while (currentPaymentDate <= end) {
        count++;
        // Move to next payment date
        currentPaymentDate = edate(currentPaymentDate, frequencyMonths);
    }
    
    return count;
}

// Format date as YYYY-MM-DD
function formatDate(date) {
    if (!date || isNaN(date.getTime())) {
        // Invalid date - return empty string or a safe default
        console.error('Invalid date passed to formatDate:', date);
        return '';
    }
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// Add Manual Rental Detail
let rentalCount = 0;  // Global counter for rental schedule rows

function addManualRentalDetail() {
    const tbody = document.getElementById('rentalTableBody');
    const tableContainer = document.getElementById('rentalTableContainer');
    
    // Create table if it doesn't exist
    if (!tbody) {
        // Table should already exist in HTML, but ensure container is visible
        if (tableContainer) {
            tableContainer.style.display = 'block';
        }
        return;
    }
    
    // Show table container if hidden
    if (tableContainer) {
        tableContainer.style.display = 'block';
    }
    
    // Get lease dates for default values
    const leaseStartDate = document.getElementById('lease_start_date').value || '';
    const leaseEndDate = document.getElementById('lease_end_date').value || '';
    
    rentalCount++;
    const rowCount = tbody.rows.length;
    const newRow = tbody.insertRow();
    newRow.innerHTML = `
        <td>${rowCount + 1}</td>
        <td><input type="date" name="rental_start_date_${rentalCount}" value="${leaseStartDate}"></td>
        <td><input type="date" name="rental_end_date_${rentalCount}" value="${leaseEndDate}"></td>
        <td><input type="number" name="rental_count_${rentalCount}" value="1" min="0"></td>
        <td><input type="number" name="rental_amount_${rentalCount}" value="0.00" step="0.01" min="0"></td>
        <td><button type="button" class="file-action-btn" onclick="this.closest('tr').remove(); updateRentalNumbers()">Remove</button></td>
    `;
}

// Reset Rental Schedule - called when escalation parameters are edited
function resetRentalSchedule() {
    const tbody = document.getElementById('rentalTableBody');
    const tableContainer = document.getElementById('rentalTableContainer');
    
    if (tbody) {
        tbody.innerHTML = '';
    }
    
    if (tableContainer) {
        tableContainer.style.display = 'none';
    }
    
    rentalCount = 0;
}

// Populate rental schedule table from saved data
function populateRentalScheduleTable(rentalSchedule) {
    const tbody = document.getElementById('rentalTableBody');
    const tableContainer = document.getElementById('rentalTableContainer');
    
    if (!tbody) {
        console.warn('⚠️ rentalTableBody not found');
        return;
    }
    
    // Clear existing rows
    tbody.innerHTML = '';
    rentalCount = 0;
    
    // Show table container
    if (tableContainer) {
        tableContainer.style.display = 'block';
    }
    
    // Add rows for each rental schedule entry
    if (rentalSchedule && Array.isArray(rentalSchedule)) {
        rentalSchedule.forEach((rental, index) => {
            rentalCount++;
            const rowCount = tbody.rows.length;
            const newRow = tbody.insertRow();
            
            // Format dates for input fields (YYYY-MM-DD)
            // Handle both formats: {start_date, end_date, rental_count, amount} and {startDate, endDate, rentalCount, amount}
            const startDate = rental.start_date || rental.startDate || '';
            const endDate = rental.end_date || rental.endDate || '';
            const count = rental.rental_count !== undefined ? rental.rental_count : (rental.rentalCount !== undefined ? rental.rentalCount : 0);
            const amount = rental.amount !== undefined ? rental.amount : 0;
            
            newRow.innerHTML = `
                <td>${rowCount + 1}</td>
                <td><input type="date" name="rental_start_date_${rentalCount}" value="${startDate}"></td>
                <td><input type="date" name="rental_end_date_${rentalCount}" value="${endDate}"></td>
                <td><input type="number" name="rental_count_${rentalCount}" value="${count}" min="0"></td>
                <td><input type="number" name="rental_amount_${rentalCount}" value="${amount}" step="0.01" min="0"></td>
                <td><button type="button" class="file-action-btn" onclick="this.closest('tr').remove(); updateRentalNumbers()">Remove</button></td>
            `;
        });
        
        console.log(`✅ Populated ${rentalSchedule.length} rental schedule rows`);
    }
}

// Update rental numbers after removal
function updateRentalNumbers() {
    const tbody = document.getElementById('rentalTableBody');
    if (tbody) {
        const rows = tbody.rows;
        for (let i = 0; i < rows.length; i++) {
            rows[i].cells[0].textContent = i + 1;
        }
    }
}

// Toggle Purchase Option
function togglePurchaseOption(checkbox) {
    const purchaseOption = document.getElementById('purchaseOption');
    if (checkbox.checked) {
        purchaseOption.style.display = 'block';
    } else {
        purchaseOption.style.display = 'none';
    }
}

// Update Useful Life End Date
function updateUsefulLifeEnd(input) {
    const months = parseInt(input.value);
    if (months && !isNaN(months)) {
        const startDateInput = document.querySelector('input[name="lease_start_date"]');
        if (startDateInput && startDateInput.value) {
            const startDate = new Date(startDateInput.value);
            const endDate = new Date(startDate);
            endDate.setMonth(endDate.getMonth() + months);
            
            const endDateInput = document.querySelector('input[name="useful_life_end_date"]');
            if (endDateInput) {
                endDateInput.value = endDate.toISOString().split('T')[0];
            }
        }
    }
}

// Toggle Security Deposit
function toggleSecurityDeposit(checkbox) {
    const securityDeposit = document.getElementById('securityDeposit');
    if (checkbox.checked) {
        securityDeposit.style.display = 'block';
    } else {
        securityDeposit.style.display = 'none';
    }
}

// Add Security Deposit Detail
let securityDepositCount = 1;

function addSecurityDepositDetail() {
    securityDepositCount++;
    const container = document.getElementById('securityDepositList');
    
    const depositDiv = document.createElement('div');
    depositDiv.className = 'security-deposit-item';
    depositDiv.id = `securityDeposit${securityDepositCount}`;
    depositDiv.innerHTML = `
        <div class="deposit-item-header">
            <h4>Security Deposit ${securityDepositCount}</h4>
            <button type="button" class="btn-remove" onclick="removeSecurityDepositDetail(${securityDepositCount})">Remove</button>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>Security Deposit Amount</label>
                <input type="number" name="security_deposit_amount_${securityDepositCount}" step="0.01" placeholder="0.00">
            </div>
            <div class="form-group">
                <label>Security Deposit Date</label>
                <input type="date" name="security_deposit_date_${securityDepositCount}">
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label>Discount Rate</label>
                <input type="number" name="security_discount_rate_${securityDepositCount}" step="0.01" placeholder="0.00">
            </div>
        </div>
    `;
    
    container.appendChild(depositDiv);
}

function removeSecurityDepositDetail(id) {
    const item = document.getElementById(`securityDeposit${id}`);
    if (item) {
        item.remove();
    }
}

// Update Scope Exemption - check if short-term or low-value asset is selected
function updateScopeExemption() {
    const shortTermUSGAAP = document.querySelector('input[name="short_term_usgaap"]');
    const shortTermIFRS = document.querySelector('input[name="short_term_ifrs"]');
    const lowValueAsset = document.querySelector('input[name="low_value_asset"]');
    const scopeExemptionApplied = document.getElementById('scopeExemptionApplied');
    
    if (scopeExemptionApplied) {
        // Check if any scope exemption criteria are met
        const hasExemption = (shortTermUSGAAP && shortTermUSGAAP.checked) ||
                            (shortTermIFRS && shortTermIFRS.checked) ||
                            (lowValueAsset && lowValueAsset.checked);
        
        scopeExemptionApplied.checked = hasExemption;
    }
}

// Toggle ARO
function toggleARO(checkbox) {
    const aroSection = document.getElementById('aroSection');
    if (checkbox.checked) {
        aroSection.style.display = 'block';
    } else {
        aroSection.style.display = 'none';
    }
}

// Handle File Upload (for attachments section)
function handleFileUpload(input) {
    const files = input.files;
    const uploadedFilesList = document.getElementById('uploadedFiles');
    
    for (let file of files) {
        const fileItem = document.createElement('div');
        fileItem.className = 'uploaded-file-item';
        fileItem.innerHTML = `
            <span>${file.name}</span>
            <div class="file-actions">
                <button type="button" class="file-action-btn" onclick="downloadFile('${file.name}')">Download</button>
                <button type="button" class="file-action-btn" onclick="this.parentElement.parentElement.remove()">Delete</button>
            </div>
        `;
        uploadedFilesList.appendChild(fileItem);
        
        // If PDF, show in viewer
        if (file.type === 'application/pdf') {
            displayPDF(file);
        }
    }
}

// Display PDF in viewer
function displayPDF(file) {
    const pdfViewer = document.getElementById('pdfViewer');
    const pdfFrame = document.getElementById('pdfFrame');
    
    const reader = new FileReader();
    reader.onload = function(e) {
        pdfFrame.src = e.target.result;
        pdfViewer.style.display = 'block';
        
        // Show AI highlights placeholder
        const aiHighlights = document.getElementById('aiHighlights');
        if (aiHighlights) {
            aiHighlights.style.display = 'block';
        }
    };
    reader.readAsDataURL(file);
}

// Update Entered By
async function updateEnteredBy() {
    if (currentLeaseId) {
        return; // Don't update for existing leases
    }
    try {
        // Use AuthAPI from auth.js
        if (typeof getCurrentUser === 'function') {
            const user = await getCurrentUser();
            if (user) {
                const enteredByInput = document.querySelector('input[name="entered_by"]');
                if (enteredByInput) {
                    enteredByInput.value = user.username || '';
                }
            }
        } else {
            console.warn('AuthAPI not available, skipping entered_by update');
        }
    } catch (error) {
        console.error('Error fetching user:', error);
    }
}

// Update Last Modified Date
function updateLastModifiedDate() {
    const lastModifiedInput = document.querySelector('input[name="last_modified_date"]');
    if (lastModifiedInput && !lastModifiedInput.value) {
        lastModifiedInput.value = new Date().toISOString().split('T')[0];
    }
}


// Save Draft
async function saveDraft() {
    const form = document.getElementById('leaseForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    
    // Debug: Log ibr value specifically
    const ibrField = form.querySelector('[name="ibr"]');
    if (ibrField) {
        const ibrValue = ibrField.value.trim();
        console.log('🔑 IBR field value:', ibrValue, 'Type:', typeof ibrValue);
        // Always use the field's current value, even if empty (convert empty string to null for database)
        if (ibrValue === '' || ibrValue === null || ibrValue === undefined) {
            data.ibr = null;
        } else {
            const numValue = parseFloat(ibrValue);
            data.ibr = isNaN(numValue) ? null : numValue;
        }
        console.log('🔑 IBR value being saved:', data.ibr);
    } else {
        console.warn('⚠️ IBR field not found in form!');
        data.ibr = null;
    }
    
    // Collect rental schedule data from table
    const rentalSchedule = collectRentalScheduleData();
    
    // Always include rental_schedule if it exists (even for drafts)
    if (rentalSchedule && rentalSchedule.length > 0) {
        data.rental_schedule = rentalSchedule;
    }
    
    // Add lease_id if editing
    if (currentLeaseId) {
        data.lease_id = currentLeaseId;
    }
    
    data.status = 'draft';
    
    console.log('📤 Saving draft:', data);
    console.log('🔑 IBR in data:', data.ibr);
    
    // Validate Transition Option if Transition Date is provided
    const transitionDate = data.transition_date;
    const transitionOption = data.transition_option;
    if (transitionDate && transitionDate.trim() !== '' && (!transitionOption || transitionOption.trim() === '')) {
        showModal('Error', 'Transition Option is required when Transition Date is provided.');
        const transitionOptionSelect = document.getElementById('transition_option');
        if (transitionOptionSelect) {
            transitionOptionSelect.focus();
        }
        return;
    }
    
    try {
        // Use PUT with lease_id in URL for updates, POST for new leases
        const url = currentLeaseId ? `/api/leases/${currentLeaseId}` : '/api/leases';
        const method = currentLeaseId ? 'PUT' : 'POST';
        
        // Call backend API to save draft
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        console.log('📥 Save draft response:', result);
        
        if (result.success) {
            const isNewLease = !currentLeaseId && result.lease_id;
            if (isNewLease) {
                currentLeaseId = result.lease_id;
                window.history.replaceState({}, '', `/lease_form.html?id=${result.lease_id}`);
            }

            // If this was a new lease created after an AI extraction, upload the source file.
            if (isNewLease && fileFromExtraction) {
                await uploadExtractedFile(currentLeaseId, fileFromExtraction);
                fileFromExtraction = null; // Clear after upload
            }

            showModal('Success', 'Draft saved successfully!');
            // Update status display
            const statusEl = document.getElementById('formStatus');
            if (statusEl) {
                statusEl.textContent = 'Draft';
            }
        } else {
            console.error('❌ Save draft failed:', result);
            showModal('Error', 'Error saving draft: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('❌ Error saving draft:', error);
        showModal('Error', 'Error saving draft. Please try again. Check console for details.');
    }
}

// Submit Form
async function submitForm() {
    const form = document.getElementById('leaseForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    
    // Debug: Log ibr value specifically
    const ibrField = form.querySelector('[name="ibr"]');
    if (ibrField) {
        const ibrValue = ibrField.value.trim();
        console.log('🔑 IBR field value:', ibrValue, 'Type:', typeof ibrValue);
        // Always use the field's current value, even if empty (convert empty string to null for database)
        if (ibrValue === '' || ibrValue === null || ibrValue === undefined) {
            data.ibr = null;
        } else {
            const numValue = parseFloat(ibrValue);
            data.ibr = isNaN(numValue) ? null : numValue;
        }
        console.log('🔑 IBR value being saved:', data.ibr);
    } else {
        console.warn('⚠️ IBR field not found in form!');
        data.ibr = null;
    }
    
    // Collect rental schedule data from table
    const rentalSchedule = collectRentalScheduleData();
    
    // Validate: Must have at least one rental amount (from rental_schedule OR rental_amount field)
    const rentalAmount = parseFloat(data.rental_amount) || 0;
    const hasRentalSchedule = rentalSchedule && rentalSchedule.length > 0 && 
                             rentalSchedule.some(r => r.amount && parseFloat(r.amount) > 0);
    const hasRentalAmount = rentalAmount > 0;
    
    if (!hasRentalSchedule && !hasRentalAmount) {
        showModal('Error', 'Please provide at least one rental amount. Either:\n' +
              '1. Add rental entries in the Rent Schedule table, OR\n' +
              '2. Enter an amount in the "Amount" field for auto-population.');
        const rentalAmountInput = document.getElementById('rental_amount');
        if (rentalAmountInput) {
            rentalAmountInput.focus();
        }
        return;
    }
    
    // Always include rental_schedule if it exists (for calculation - source of truth)
    if (rentalSchedule && rentalSchedule.length > 0) {
        data.rental_schedule = rentalSchedule;
    }
    
    // Add lease_id if editing
    if (currentLeaseId) {
        data.lease_id = currentLeaseId;
    }
    
    data.status = 'submitted';
    
    // Validate Transition Option if Transition Date is provided
    const transitionDate = data.transition_date;
    const transitionOption = data.transition_option;
    if (transitionDate && transitionDate.trim() !== '' && (!transitionOption || transitionOption.trim() === '')) {
        showModal('Error', 'Transition Option is required when Transition Date is provided.');
        const transitionOptionSelect = document.getElementById('transition_option');
        if (transitionOptionSelect) {
            transitionOptionSelect.focus();
        }
        return;
    }
    
    // Log data being sent for debugging
    console.log('📤 Submitting lease data:', data);
    console.log('🔑 IBR in data:', data.ibr);
    
    try {
        // Use PUT with lease_id in URL for updates, POST for new leases
        const url = currentLeaseId ? `/api/leases/${currentLeaseId}` : '/api/leases';
        const method = currentLeaseId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify(data)
        });
        
        const result = await response.json();
        console.log('📥 Submit response:', result);
        
        if (result.success) {
            showModal('Success', 'Lease submitted successfully!');
            window.location.href = '/dashboard.html';
        } else {
            console.error('❌ Submit failed:', result);
            showModal('Error', 'Error submitting lease: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('❌ Error submitting form:', error);
        showModal('Error', 'Error submitting form. Please try again. Check console for details.');
    }
}

// Collect rental schedule data from the table
function collectRentalScheduleData() {
    const tbody = document.getElementById('rentalTableBody');
    if (!tbody || tbody.rows.length === 0) {
        return null;
    }
    
    const rentalRows = [];
    for (let i = 0; i < tbody.rows.length; i++) {
        const row = tbody.rows[i];
        const cells = row.cells;
        
        if (cells.length >= 5) {
            const startDateInput = cells[1].querySelector('input[type="date"]');
            const endDateInput = cells[2].querySelector('input[type="date"]');
            const countInput = cells[3].querySelector('input[type="number"]');
            const amountInput = cells[4].querySelector('input[type="number"]');
            
            if (startDateInput && endDateInput && countInput && amountInput) {
                rentalRows.push({
                    rental_number: i + 1,
                    start_date: startDateInput.value || null,
                    end_date: endDateInput.value || null,
                    rental_count: parseInt(countInput.value) || 0,
                    amount: parseFloat(amountInput.value) || 0
                });
            }
        }
    }
    
    return rentalRows.length > 0 ? rentalRows : null;
}

// Reset Form
function resetForm() {
    if (confirm('Are you sure you want to reset the form? All data will be lost.')) {
        document.getElementById('leaseForm').reset();
    }
}

// Excel EDATE function equivalent: adds months to date and returns new date
// Handles month-end dates properly (e.g., Jan 31 + 1 month = Feb 28/29)
function edate(date, months) {
    const result = new Date(date);
    const originalDay = result.getDate();
    
    // Add months
    result.setMonth(result.getMonth() + months);
    
    // If the day doesn't exist in the new month (e.g., Jan 31 -> Feb doesn't have day 31),
    // set to last day of that month
    if (result.getDate() !== originalDay) {
        // Day doesn't exist in the new month, set to last day
        result.setDate(0); // This sets to last day of previous month
        // But we want last day of current month, so add one month back
        result.setMonth(result.getMonth() + 1);
        result.setDate(0); // Now it's last day of target month
    }
    
    return result;
}

// Calculate tenure from start and end dates using EDATE logic
function updateTenureFromDates() {
    const startDateInput = document.getElementById('lease_start_date');
    const endDateInput = document.getElementById('lease_end_date');
    const tenureMonthsInput = document.getElementById('tenure_months');
    const tenureDaysInputField = document.getElementById('tenure_days_input');
    
    // Skip if currently updating from tenure (to prevent infinite loop)
    if (endDateInput && endDateInput.dataset.updatingFromTenure === 'true') {
        return;
    }
    
    // Set flag to indicate we're updating from dates (prevent tenure update from triggering date update)
    if (startDateInput) {
        startDateInput.dataset.updatingFromDates = 'true';
    }
    
    // Only validate and calculate if both dates are fully entered (valid date format)
    if (startDateInput && endDateInput && startDateInput.value && endDateInput.value) {
        // Check if dates are valid (YYYY-MM-DD format)
        const startDateStr = startDateInput.value.trim();
        const endDateStr = endDateInput.value.trim();
        
        // Validate date format (YYYY-MM-DD) - be lenient, HTML5 date input handles format
        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        if (!dateRegex.test(startDateStr) || !dateRegex.test(endDateStr)) {
            // Not a complete date yet, don't validate
            return;
        }
        
        // Parse dates using native Date constructor (handles YYYY-MM-DD properly)
        const startDate = new Date(startDateStr + 'T00:00:00'); // Add time to avoid timezone issues
        const endDate = new Date(endDateStr + 'T00:00:00');
        
        // Check if dates are valid (not NaN)
        if (isNaN(startDate.getTime()) || isNaN(endDate.getTime())) {
            return;
        }
        
        // Validate end date is not before start date - silently allow if invalid (user can correct)
        if (endDate < startDate) {
            // Don't clear or show alert, just skip calculation
            return;
        }
        
        // Calculate total difference in days
        const diffTime = endDate - startDate;
        const totalDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        // Calculate months using EDATE logic (back-computation)
        // Find the maximum number of months where EDATE(start, months) - 1 <= endDate
        // EDATE formula: EDATE(startDate, months) - 1
        let months = 0;
        let calculatedEndDate = new Date(startDate);
        calculatedEndDate.setDate(calculatedEndDate.getDate() - 1); // EDATE(0) - 1
        
        if (calculatedEndDate <= endDate) {
            // Binary search approach to find maximum months
            let low = 0;
            let high = Math.ceil(totalDays / 28) + 12; // Upper bound
            
            while (low <= high) {
                const mid = Math.floor((low + high) / 2);
                const testDate = edate(startDate, mid);
                testDate.setDate(testDate.getDate() - 1); // EDATE - 1
                
                if (testDate <= endDate) {
                    months = mid;
                    calculatedEndDate = new Date(testDate);
                    low = mid + 1; // Try larger number
                } else {
                    high = mid - 1; // Try smaller number
                }
            }
        }
        
        // Calculate remaining days after the full months
        const remainingDays = Math.max(0, Math.ceil((endDate - calculatedEndDate) / (1000 * 60 * 60 * 24)));
        
        // Update tenure fields (always update when dates change, unless manually entered)
        if (tenureMonthsInput) {
            // Only update if not manually entered (check flag)
            if (!tenureMonthsInput.dataset.manualEntry || tenureMonthsInput.dataset.manualEntry !== 'true') {
                tenureMonthsInput.value = months;
                tenureMonthsInput.dataset.manualEntry = ''; // Clear manual flag
            }
        }
        
        // Update the days input field (#Day)
        if (tenureDaysInputField) {
            if (!tenureDaysInputField.dataset.manualEntry || tenureDaysInputField.dataset.manualEntry !== 'true') {
                tenureDaysInputField.value = remainingDays > 0 ? remainingDays : 0;
                tenureDaysInputField.dataset.manualEntry = ''; // Clear manual flag
            }
        }
    }
    
    // Clear flag after a short delay
    setTimeout(() => {
        if (startDateInput) {
            startDateInput.dataset.updatingFromDates = '';
        }
    }, 100);
}

// Update end date from tenure (No. of months and days) using EDATE logic
function updateEndDateFromTenure() {
    const startDateInput = document.getElementById('lease_start_date');
    const endDateInput = document.getElementById('lease_end_date');
    const tenureMonthsInput = document.getElementById('tenure_months');
    const tenureDaysInputField = document.getElementById('tenure_days_input');
    
    // Skip if currently updating from dates (to prevent infinite loop)
    if (endDateInput && endDateInput.dataset.updatingFromTenure === 'true') {
        return;
    }
    
    // Only update if start date is valid
    if (startDateInput && startDateInput.value) {
        // Check if start date is valid format
        const startDateStr = startDateInput.value.trim();
        const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
        
        if (!dateRegex.test(startDateStr)) {
            // Start date not complete yet, don't update
            return;
        }
        
        const startDate = new Date(startDateStr + 'T00:00:00');
        
        // Check if date is valid
        if (isNaN(startDate.getTime())) {
            return;
        }
        
        // Get months and days values
        const months = tenureMonthsInput ? (parseInt(tenureMonthsInput.value) || 0) : 0;
        const days = tenureDaysInputField ? (parseInt(tenureDaysInputField.value) || 0) : 0;
        
        if (months >= 0 && days >= 0) {
            // Mark as manual entry and set flag to prevent date update from triggering tenure update
            if (tenureMonthsInput) {
                tenureMonthsInput.dataset.manualEntry = 'true';
            }
            if (tenureDaysInputField) {
                tenureDaysInputField.dataset.manualEntry = 'true';
            }
            
            // Set flag to prevent recursive updates
            if (endDateInput) {
                endDateInput.dataset.updatingFromTenure = 'true';
            }
            
            // Calculate end date using EDATE logic: EDATE(startDate, months) - 1 + days
            // Step 1: Add months using EDATE (handles month-end dates properly, e.g., Jan 31 -> Feb 28/29)
            const endDate = edate(startDate, months);
            
            // Step 2: Subtract 1 day (as per EDATE formula)
            endDate.setDate(endDate.getDate() - 1);
            
            // Step 3: Add remaining days if any
            if (days > 0) {
                endDate.setDate(endDate.getDate() + days);
            }
            
            // Format as YYYY-MM-DD
            const year = endDate.getFullYear();
            const month = String(endDate.getMonth() + 1).padStart(2, '0');
            const day = String(endDate.getDate()).padStart(2, '0');
            const endDateStr = `${year}-${month}-${day}`;
            
            // Update end date field
            if (endDateInput) {
                endDateInput.value = endDateStr;
            }
            
            // Clear flags after a short delay
            setTimeout(() => {
                if (endDateInput) {
                    endDateInput.dataset.updatingFromTenure = '';
                }
            }, 100);
        } else if ((!tenureMonthsInput || tenureMonthsInput.value === '' || tenureMonthsInput.value === '0') && 
                   (!tenureDaysInputField || tenureDaysInputField.value === '' || tenureDaysInputField.value === '0')) {
            // Clear end date if tenure is cleared
            if (endDateInput) {
                endDateInput.value = '';
            }
            if (tenureDaysInputField) {
                tenureDaysInputField.value = '';
            }
            if (tenureMonthsInput) {
                tenureMonthsInput.dataset.manualEntry = '';
            }
            if (tenureDaysInputField) {
                tenureDaysInputField.dataset.manualEntry = '';
            }
        }
    }
}

// Helper function to parse date in dd/mm/yyyy or yyyy-mm-dd format
function parseDateInput(value) {
    if (!value) return null;
    
    // Try dd/mm/yyyy format
    const ddmmyyyy = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value);
    if (ddmmyyyy) {
        const day = parseInt(ddmmyyyy[1]);
        const month = parseInt(ddmmyyyy[2]);
        const year = parseInt(ddmmyyyy[3]);
        
        if (month >= 1 && month <= 12 && day >= 1 && day <= 31 && year >= 1900 && year <= 2100) {
            // Create date and verify it's valid (handles Feb 29, etc.)
            const date = new Date(year, month - 1, day);
            if (date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day) {
                // Format as YYYY-MM-DD for date input
                return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            }
        }
    }
    
    // Try yyyy-mm-dd format (standard HTML5 date format)
    const yyyymmdd = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (yyyymmdd) {
        return value;
    }
    
    return null;
}

// Format date as dd/mm/yyyy for display
function formatDateForDisplay(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr + 'T00:00:00');
    if (isNaN(date.getTime())) return '';
    
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
}

// Add date input handlers for better text entry support
function setupDateInputHandlers() {
    const startDateInput = document.getElementById('lease_start_date');
    const endDateInput = document.getElementById('lease_end_date');
    
    [startDateInput, endDateInput].forEach(input => {
        if (!input) return;
        
        // Handle paste with dd/mm/yyyy format
        input.addEventListener('paste', function(e) {
            e.preventDefault();
            const pastedText = (e.clipboardData || window.clipboardData).getData('text').trim();
            const parsedDate = parseDateInput(pastedText);
            if (parsedDate) {
                this.value = parsedDate;
                this.dispatchEvent(new Event('change', { bubbles: true }));
            } else {
                // If paste didn't work, try to auto-format
                const cleaned = pastedText.replace(/[^\d\/-]/g, '');
                if (cleaned.length >= 8) {
                    const parsed = parseDateInput(cleaned);
                    if (parsed) {
                        this.value = parsed;
                        this.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            }
        });
        
        // Handle manual text entry - allow typing dd/mm/yyyy
        let inputTimer;
        let lastValue = '';
        
        input.addEventListener('keydown', function(e) {
            // Allow backspace, delete, tab, escape, enter
            if ([46, 8, 9, 27, 13, 110, 190].indexOf(e.keyCode) !== -1 ||
                // Allow Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X
                (e.keyCode === 65 && e.ctrlKey === true) ||
                (e.keyCode === 67 && e.ctrlKey === true) ||
                (e.keyCode === 86 && e.ctrlKey === true) ||
                (e.keyCode === 88 && e.ctrlKey === true) ||
                // Allow home, end, left, right, down, up
                (e.keyCode >= 35 && e.keyCode <= 40)) {
                return;
            }
            // Ensure that it is a number and stop the keypress
            if ((e.shiftKey || (e.keyCode < 48 || e.keyCode > 57)) && (e.keyCode < 96 || e.keyCode > 105) && e.keyCode !== 191) {
                e.preventDefault();
            }
        });
        
        input.addEventListener('input', function(e) {
            clearTimeout(inputTimer);
            let value = this.value;
            
            // Remove non-digit, non-slash, non-dash characters
            value = value.replace(/[^\d\/-]/g, '');
            
            // Auto-format dd/mm/yyyy as user types
            if (value.length <= 10) {
                // If it looks like dd/mm/yyyy format (with or without slashes)
                if (/^\d{0,2}\/?\d{0,2}\/?\d{0,4}$/.test(value)) {
                    // Auto-insert slashes
                    if (value.length === 2 && !value.includes('/') && !value.includes('-')) {
                        value = value + '/';
                    } else if (value.length === 5 && value.split('/').length === 2) {
                        value = value + '/';
                    }
                    this.value = value;
                }
                
                // If complete dd/mm/yyyy format, parse it
                if (/^\d{1,2}\/\d{1,2}\/\d{4}$/.test(value)) {
                    inputTimer = setTimeout(() => {
                        const parsedDate = parseDateInput(value);
                        if (parsedDate) {
                            this.value = parsedDate;
                            this.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    }, 300);
                }
            }
            
            lastValue = value;
        });
        
        // On blur, try to parse any remaining text
        input.addEventListener('blur', function() {
            const value = this.value;
            if (value && !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
                const parsedDate = parseDateInput(value);
                if (parsedDate) {
                    this.value = parsedDate;
                    this.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        });
    });
}

// Initialize tenure calculations on page load
document.addEventListener('DOMContentLoaded', function() {
    const startDateInput = document.getElementById('lease_start_date');
    const endDateInput = document.getElementById('lease_end_date');
    const tenureMonthsInput = document.getElementById('tenure_months');
    const tenureDaysInputField = document.getElementById('tenure_days_input');
    
    // Setup date input handlers for better text entry
    setupDateInputHandlers();
    
    // Add blur event to tenure inputs to ensure sync on focus out
    if (tenureMonthsInput) {
        tenureMonthsInput.addEventListener('blur', function() {
            if (this.value) {
                updateEndDateFromTenure();
            }
        });
    }
    
    if (tenureDaysInputField) {
        tenureDaysInputField.addEventListener('blur', function() {
            if (this.value || tenureMonthsInput.value) {
                updateEndDateFromTenure();
            }
        });
    }
    
    // The onchange handlers are already in the HTML, but we can add additional listeners here if needed
    if (startDateInput && endDateInput) {
        // Initial calculation if dates are already filled
        updateTenureFromDates();
    }
});

// --- Document Management Functions ---

async function uploadExtractedFile(leaseId, file) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', 'contract'); // Default to 'contract' for AI extractions

    try {
        const response = await fetch(`/api/leases/${leaseId}/documents`, {
            method: 'POST',
            body: formData,
        });
        const result = await response.json();
        if (result.success) {
            console.log('Automatically uploaded AI extraction source document.');
            loadDocuments(leaseId); // Refresh the list
        } else {
            console.error('Failed to automatically upload AI extraction source:', result.error);
        }
    } catch (error) {
        console.error('Error during automatic upload of AI extraction source:', error);
    }
}

async function loadDocuments(leaseId) {
    if (!leaseId) return;
    try {
        const response = await fetch(`/api/leases/${leaseId}/documents`);
        const result = await response.json();
        const tbody = document.getElementById('documentsTableBody');
        const noDocsMessage = document.getElementById('noDocumentsMessage');

        if (result.success && result.documents.length > 0) {
            noDocsMessage.style.display = 'none';
            tbody.innerHTML = result.documents.map(doc => `
                <tr>
                    <td>${doc.file_name}</td>
                    <td>${doc.document_type}</td>
                    <td>${(doc.file_size / 1024).toFixed(2)} KB</td>
                    <td>${new Date(doc.uploaded_at).toLocaleString()}</td>
                    <td>
                        <a href="/api/documents/${doc.document_id}/download" class="btn-link">Download</a>
                    </td>
                </tr>
            `).join('');
        } else {
            tbody.innerHTML = '';
            noDocsMessage.style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading documents:', error);
    }
}

async function uploadDocument() {
    if (!currentLeaseId) {
        showModal('Error', 'Please save the lease as a draft before uploading documents.');
        return;
    }

    const fileInput = document.getElementById('documentUploadInput');
    const docTypeInput = document.getElementById('documentTypeSelect');
    const file = fileInput.files[0];
    const docType = docTypeInput.value;

    if (!file) {
        showModal('Error', 'Please select a file to upload.');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', docType);

    try {
        const response = await fetch(`/api/leases/${currentLeaseId}/documents`, {
            method: 'POST',
            body: formData,
        });

        const result = await response.json();
        if (result.success) {
            showModal('Success', 'Document uploaded successfully.');
            loadDocuments(currentLeaseId); // Refresh the list
            fileInput.value = ''; // Clear the file input
        } else {
            showModal('Error', 'Error uploading document: ' + result.error);
        }
    } catch (error) {
        console.error('Error uploading document:', error);
        showModal('Error', 'An unexpected error occurred during upload.');
    }
}
