/**
 * Lease Form JavaScript
 * Handles form interactions, validations, and dynamic sections
 */

// Get lease ID from URL if editing
let currentLeaseId = null;
document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const leaseId = urlParams.get('id');
    if (leaseId) {
        currentLeaseId = parseInt(leaseId);
        loadLeaseData(currentLeaseId);
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
                extractAndPopulateForm(e.target.files[0]);
            }
        };
        document.body.appendChild(pdfInput);
    }
    
    // Trigger file upload dialog
    pdfInput.click();
}

// Extract lease data from PDF and populate form
async function extractAndPopulateForm(file) {
    console.log('📥 Starting extraction for file:', file.name);
    
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
        alert('Please select a PDF file');
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
            alert(`❌ Error: ${errorMsg}`);
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
            alert('❌ Error: Invalid response from server. Please check console for details.');
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
            
            alert('✅ Lease data extracted and form populated successfully!');
        } else {
            const errorMsg = result.error || 'Failed to extract lease data';
            console.error('❌ Extraction failed:', errorMsg);
            let errorDisplay = `❌ Error: ${errorMsg}`;
            if (result.help) {
                errorDisplay += `\n\n${result.help}`;
            }
            alert(errorDisplay);
        }
    } catch (error) {
        console.error('❌ Error extracting lease data:', error);
        console.error('   Stack:', error.stack);
        hideExtractionLoader();
        const errorMsg = error.message || 'Failed to extract lease data';
        alert(`❌ Error: ${errorMsg}\n\nPlease check the browser console for more details.`);
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
        const response = await fetch(`/api/leases/${leaseId}`, {
            method: 'GET',
            credentials: 'include'
        });
        
        const result = await response.json();
        if (result.success && result.lease) {
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
        alert('Please enter an asset class name');
        return;
    }
    
    if (assetClasses.includes(value)) {
        alert('Asset class already exists');
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
        alert('Please enter Lease Start Date and Lease End Date');
        return;
    }
    
    if (!rentalAmount || rentalAmount <= 0) {
        alert('Please enter Rental Amount in the escalation parameters section');
        return;
    }
    
    // Parse dates
    const startDate = new Date(leaseStartDate + 'T00:00:00');
    const endDate = new Date(leaseEndDate + 'T00:00:00');
    
    // Validate parsed dates
    if (isNaN(startDate.getTime())) {
        alert('Invalid Lease Start Date');
        return;
    }
    if (isNaN(endDate.getTime())) {
        alert('Invalid Lease End Date');
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
                alert('Invalid Escalation Start Date. Please enter a valid date.');
                return;
            }
        } else if (escalationStartDate instanceof Date) {
            escStartDate = new Date(escalationStartDate);
            if (isNaN(escStartDate.getTime())) {
                console.error('❌ Invalid escalation start date object');
                alert('Invalid Escalation Start Date. Please enter a valid date.');
                return;
            }
        }
    } else {
        // Escalation start date is required for escalation
        if (escalationPercentage > 0) {
            console.error('❌ Escalation Start Date is required when escalation percentage is set');
            alert('Please enter Escalation Start Date in the escalation parameters section');
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
    try {
        // Use AuthAPI from auth.js
        if (typeof AuthAPI !== 'undefined' && AuthAPI.getCurrentUser) {
            const user = await AuthAPI.getCurrentUser();
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
        alert('Transition Option is required when Transition Date is provided.');
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
            alert('Draft saved successfully!');
            // Update lease ID if new
            if (!currentLeaseId && result.lease_id) {
                currentLeaseId = result.lease_id;
                window.history.replaceState({}, '', `/lease_form.html?id=${result.lease_id}`);
            }
            // Update status display
            const statusEl = document.getElementById('formStatus');
            if (statusEl) {
                statusEl.textContent = 'Draft';
            }
        } else {
            console.error('❌ Save draft failed:', result);
            alert('Error saving draft: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('❌ Error saving draft:', error);
        alert('Error saving draft. Please try again. Check console for details.');
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
        alert('Please provide at least one rental amount. Either:\n' +
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
        alert('Transition Option is required when Transition Date is provided.');
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
            alert('Lease submitted successfully!');
            window.location.href = '/dashboard.html';
        } else {
            console.error('❌ Submit failed:', result);
            alert('Error submitting lease: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('❌ Error submitting form:', error);
        alert('Error submitting form. Please try again. Check console for details.');
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

