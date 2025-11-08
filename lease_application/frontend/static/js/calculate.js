let currentLeaseId = null;
let leasesData = {}; // Store lease data for quick lookup

// Handle lease selection change
function onLeaseSelected() {
    const leaseId = document.getElementById('leaseSelect').value;
    if (leaseId && leasesData[leaseId]) {
        const lease = leasesData[leaseId];
        // Optionally auto-fill dates from lease
        if (lease.lease_start_date && !document.getElementById('fromDate').value) {
            document.getElementById('fromDate').value = lease.lease_start_date;
        }
        if (lease.lease_end_date && !document.getElementById('toDate').value) {
            document.getElementById('toDate').value = lease.lease_end_date;
        }
        currentLeaseId = leaseId;
    }
}

// Check for lease_id in URL
window.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    const leaseId = urlParams.get('lease_id');
    
    // Load user info
    try {
        const userResponse = await fetch('/api/user', {
            credentials: 'include'
        });
        
        // Parse response
        let userData = {};
        try {
            userData = await userResponse.json();
        } catch (parseError) {
            console.error('Failed to parse user response:', parseError);
        }
        
        const usernameEl = document.getElementById('username');
        if (!usernameEl) {
            console.error('Username element not found');
        } else if (userResponse.ok && userData.success && userData.user) {
            // API returns {success: true, user: {username: ...}}
            usernameEl.textContent = userData.user.username || 'Guest';
            console.log('✅ User loaded:', userData.user.username);
        } else if (userResponse.status === 401) {
            console.log('⚠️ Not authenticated (401) - showing Guest');
            usernameEl.textContent = 'Guest';
        } else if (userData.username) {
            // Fallback for different response format
            usernameEl.textContent = userData.username || 'Guest';
            console.log('✅ User loaded (fallback):', userData.username);
        } else {
            console.warn('⚠️ Could not extract username from response:', userData);
            usernameEl.textContent = 'Guest';
        }
    } catch (e) {
        console.error('Error loading user info:', e);
        const usernameEl = document.getElementById('username');
        if (usernameEl) {
            usernameEl.textContent = 'Guest';
        }
    }

    // Load leases - wait for it to complete before pre-selecting
    await loadLeases();

    // If lease_id in URL, pre-select it and optionally load lease data
    if (leaseId) {
        currentLeaseId = leaseId;
        // Wait a bit for dropdown to be populated, then set value
        setTimeout(() => {
            const select = document.getElementById('leaseSelect');
            if (select) {
                select.value = leaseId;
                // Trigger change event to optionally load lease details
                select.dispatchEvent(new Event('change'));
            }
        }, 100);
    }
});

async function loadLeases() {
    try {
        const response = await fetch('/api/leases', {
            credentials: 'include'
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('Authentication required. Please login.');
            }
            throw new Error(`Failed to load leases: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        const select = document.getElementById('leaseSelect');
        
        console.log('📋 Leases API response:', data);
        
        // Handle different response formats
        let leases = [];
        if (Array.isArray(data)) {
            leases = data;
        } else if (data.leases && Array.isArray(data.leases)) {
            leases = data.leases;
        } else if (data.success && Array.isArray(data.data)) {
            leases = data.data;
        } else {
            console.error('Unexpected leases response format:', data);
            throw new Error('Invalid response format from server');
        }
        
        console.log(`📋 Loaded ${leases.length} leases`);
        
        select.innerHTML = '<option value="">Select a lease...</option>';
        
        // Filter leases - allow all leases (no filter for now)
        const approvedLeases = leases.filter(lease => {
            // Include all leases regardless of status
            return true;
        });
        
        if (approvedLeases.length === 0) {
            select.innerHTML = '<option value="">No leases found</option>';
        } else {
            approvedLeases.forEach(lease => {
                const option = document.createElement('option');
                option.value = lease.lease_id;
                option.textContent = `${lease.agreement_title || 'Lease_' + lease.lease_id} - ${lease.asset_id_code || 'N/A'}`;
                select.appendChild(option);
                // Store lease data for quick lookup
                leasesData[lease.lease_id] = lease;
            });
            
            // If lease_id was in URL, make sure it's selected after dropdown is populated
            const urlParams = new URLSearchParams(window.location.search);
            const urlLeaseId = urlParams.get('lease_id');
            if (urlLeaseId) {
                // Check if the lease exists in the dropdown
                if (select.querySelector(`option[value="${urlLeaseId}"]`)) {
                    select.value = urlLeaseId;
                    currentLeaseId = urlLeaseId;
                    // Trigger selection handler to auto-fill dates
                    onLeaseSelected();
                    console.log('✅ Pre-selected lease from URL:', urlLeaseId);
                } else {
                    console.warn(`⚠️ Lease ID ${urlLeaseId} from URL not found in user's leases`);
                }
            }
        }
    } catch (error) {
        console.error('Error loading leases:', error);
        const select = document.getElementById('leaseSelect');
        if (select) {
            select.innerHTML = `<option value="">Error loading leases: ${error.message}</option>`;
        }
        // Show error message if authentication failed
        if (error.message.includes('401') || error.message.includes('Authentication')) {
            showModal('Authentication Error', 'Please login to view your leases. Redirecting to login...');
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 2000);
        }
    }
}

function mapLeaseToCalculation(lease) {
    // Helper to ensure date is valid - NO DEFAULTS, return null if not provided
    function ensureDate(dateValue, fallback = null) {
        if (!dateValue || dateValue === 'null' || dateValue === 'N/A' || dateValue === '' || dateValue === null || dateValue === undefined) {
            return fallback; // Return null if fallback is null (no default to today)
        }
        if (typeof dateValue === 'string' && dateValue.includes('T')) {
            return dateValue.split('T')[0];
        }
        return dateValue;
    }

    return {
        auto_id: lease.lease_id || lease.auto_id,
        description: lease.agreement_title || lease.description || '',
        asset_class: lease.asset_class || '',
        asset_id_code: lease.asset_id_code || '',
        lease_start_date: ensureDate(lease.lease_start_date),
        first_payment_date: ensureDate(lease.first_payment_date, lease.lease_start_date),
        end_date: ensureDate(lease.lease_end_date || lease.end_date),
        agreement_date: ensureDate(lease.rent_agreement_date || lease.agreement_date, null),
        termination_date: ensureDate(lease.termination_date, null),
        date_modified: ensureDate(lease.date_modified, null),
        tenure: lease.tenure || lease.tenure_months || 0,
        frequency_months: lease.frequency_months || lease.rent_frequency || 1,  // Check frequency_months FIRST, then rent_frequency
        day_of_month: lease.pay_day_of_month || lease.day_of_month || '1',
        accrual_day: lease.rent_accrual_day || lease.accrual_day || 1,
        manual_adj: lease.manual_adj || 'No',
        // CRITICAL: Handle null/undefined but preserve 0 if explicitly set
        rental_1: (lease.rental_amount !== null && lease.rental_amount !== undefined) ? (lease.rental_amount || 0) : (lease.rental_1 || 0),
        rental_2: (lease.rental_2 !== null && lease.rental_2 !== undefined) ? (lease.rental_2 || 0) : 0,
        // Rental Schedule - always include if provided (source of truth for rentals)
        rental_schedule: lease.rental_schedule || null,
        escalation_start_date: ensureDate(lease.escalation_start_date, null),
        escalation_percent: lease.escalation_percentage || lease.escalation_percent || 0,
        esc_freq_months: (lease.escalation_frequency || lease.esc_freq_months) ? (lease.escalation_frequency || lease.esc_freq_months) : null,
        index_rate_table: lease.index_rate_table || '',
        ibr: lease.ibr ?? null,  // Changed from borrowing_rate to ibr to match API
        compound_months: lease.compound_months || 12,
        fv_of_rou: lease.fair_value || lease.fv_of_rou || 0,
        currency: lease.currency || 'USD',
        cost_centre: lease.cost_center || lease.cost_centre || '',
        counterparty: lease.company_name || lease.counterparty || '',
        security_deposit: lease.security_deposit_amount || lease.security_deposit || 0,
        security_discount: lease.security_discount_rate || lease.security_discount || 0,
        aro: lease.aro_initial_estimate || lease.aro || 0,
        aro_table: lease.aro_table || 0,
        initial_direct_expenditure: lease.initial_direct_expenditure || 0,
        lease_incentive: lease.lease_incentive || 0,
        sublease: lease.sublease || 'No',
        sublease_rou: lease.sublease_rou || 0,
        finance_lease: lease.finance_lease_usgaap || 'No',
        short_term_ifrs: lease.shortterm_lease_ifrs_indas || 'No',
        bargain_purchase: lease.bargain_purchase || 'No',
        purchase_option_price: lease.purchase_option_price || 0,
        title_transfer: lease.title_transfer || 'No',
        practical_expedient: lease.practical_expedient || 'No',
        transition_option: lease.transition_option || '',
        transition_date: ensureDate(lease.transition_date),
        termination_penalty: lease.termination_penalty || 0,
        // Add all new fields
        useful_life_end_date: ensureDate(lease.useful_life_end_date),
    };
}

async function calculateLease() {
    const leaseId = document.getElementById('leaseSelect').value || currentLeaseId;
    const fromDate = document.getElementById('fromDate').value;
    const toDate = document.getElementById('toDate').value;

    if (!leaseId) {
        showError('Please select a lease from the dropdown');
        return;
    }

    if (!fromDate || !toDate) {
        showError('Please enter both From Date and To Date');
        return;
    }
    
    // Validate dates
    if (new Date(fromDate) > new Date(toDate)) {
        showError('From Date must be before To Date');
        return;
    }

    document.getElementById('loading').style.display = 'block';
    document.getElementById('results').style.display = 'none';
    document.getElementById('errorMessage').style.display = 'none';

    try {
        // Fetch lease data
        const user = await getCurrentUser();
        let leaseResponse;

        // Admins can access any lease, so we don't need to send the user_id
        if (user && user.role === 'admin') {
            leaseResponse = await fetch(`/api/leases/${leaseId}`, {
                credentials: 'include'
            });
        } else {
            leaseResponse = await fetch(`/api/leases/${leaseId}`, {
                credentials: 'include'
            });
        }

        if (!leaseResponse.ok) {
            throw new Error('Failed to load lease data');
        }

        const leaseResponseData = await leaseResponse.json();
        console.log('📋 Lease data from API:', leaseResponseData);
        
        // Extract lease object (API returns {success: true, lease: {...}})
        const lease = leaseResponseData.lease || leaseResponseData;
        console.log('📋 Extracted lease object:', lease);
        console.log('📋 rental_amount value:', lease.rental_amount, 'type:', typeof lease.rental_amount);
        console.log('📋 IBR value from lease:', lease.ibr, 'type:', typeof lease.ibr);
        
        // CRITICAL FIX: Ensure rental_amount is a number
        if (lease.rental_amount !== null && lease.rental_amount !== undefined) {
            lease.rental_amount = parseFloat(lease.rental_amount) || 0;
        } else {
            lease.rental_amount = 0;
        }
        console.log('📋 rental_amount after parseFloat:', lease.rental_amount);
        
        // Validate IBR before proceeding
        if (lease.ibr === null || lease.ibr === undefined || lease.ibr === '') {
            showError('IBR (Incremental Borrowing Rate) is required for calculation. Please set IBR in the lease form first.');
            document.getElementById('loading').style.display = 'none';
            return;
        }
        
        const ibrValue = parseFloat(lease.ibr);
        if (isNaN(ibrValue)) {
            showError(`Invalid IBR value: ${lease.ibr}. IBR must be a valid number.`);
            document.getElementById('loading').style.display = 'none';
            return;
        }
        console.log('✅ IBR validated:', ibrValue);
        
        // Map lease to calculation format
        const calculationData = mapLeaseToCalculation(lease);
        console.log('📋 Mapped calculation data:', calculationData);
        console.log('📋 rental_1 after mapping:', calculationData.rental_1);
        console.log('📋 IBR value in calculation data:', calculationData.ibr, 'Type:', typeof calculationData.ibr);
        
        // Ensure IBR is included and is a valid number
        if (calculationData.ibr === null || calculationData.ibr === undefined || calculationData.ibr === '') {
            console.error('❌ IBR is missing in calculation data! Lease IBR:', lease.ibr);
        } else {
            const ibrNum = parseFloat(calculationData.ibr);
            if (isNaN(ibrNum)) {
                console.error('❌ IBR is not a valid number:', calculationData.ibr);
            } else {
                calculationData.ibr = ibrNum;
                console.log('✅ IBR validated and set to:', calculationData.ibr);
            }
        }
        
        calculationData.from_date = fromDate;
        calculationData.to_date = toDate;

        // Calculate
        const response = await fetch('/api/calculate_lease', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(calculationData),
            credentials: 'include'
        });

        // Check response status first
        if (!response.ok) {
            let errorMsg = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorData = await response.json();
                errorMsg = errorData.error || errorMsg;
            } catch (e) {
                // Response might not be JSON
            }
            console.error('Calculation API error:', errorMsg);
            showError(errorMsg);
            return;
        }

        const result = await response.json();

        // Check for error in result
        if (result.error) {
            console.error('Calculation error:', result.error);
            showError(result.error || 'Calculation failed');
            return;
        }

        // Success case - API returns result directly, not wrapped in success
        displayResults(result);
    } catch (error) {
        console.error('Calculation error:', error);
        showError(`Error: ${error.message || 'Failed to connect to server. Please check if the server is running.'}`);
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
}

// Chart instances
let npvChart = null;
let liabilityAssetChart = null;
let interestDepreciationChart = null;

// Tab switching function
function showTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.style.display = 'none';
    });
    document.querySelectorAll('.nav-tab').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Show selected tab
    const tabElement = document.getElementById(tabName + 'Tab');
    if (tabElement) {
        tabElement.style.display = 'block';
    }
    
    // Activate button
    if (event && event.target) {
        event.target.classList.add('active');
    }
}

function displayResults(result) {
    const lr = result.lease_result || {};
    const schedule = result.schedule || [];
    
    // Display Key Values cards
    displayKeyValues(lr, schedule);
    
    // Create charts
    createCharts(lr, schedule);
    
    // Display summary with clean, minimal modern UI (keeping for backward compatibility)
    const summaryGrid = document.getElementById('summaryGrid');
    if (summaryGrid) {
        summaryGrid.innerHTML = `
        <!-- Lease Information -->
        <div class="summary-item" style="grid-column: 1 / -1;">
            <h3 style="margin-bottom: 16px; font-size: 1.1rem; color: #2c3e50; font-weight: 600;">Lease Information</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
                <div><strong>Description:</strong> <span style="color: #555;">${lr.description || 'N/A'}</span></div>
                <div><strong>Asset Code:</strong> <span style="color: #555;">${lr.asset_code || 'N/A'}</span></div>
                <div><strong>Asset Class:</strong> <span style="color: #555;">${lr.asset_class || 'N/A'}</span></div>
                <div><strong>Cost Center:</strong> <span style="color: #555;">${lr.cost_center || 'N/A'}</span></div>
                <div><strong>Currency:</strong> <span style="color: #555;">${lr.currency || 'USD'}</span></div>
                <div><strong>Borrowing Rate:</strong> <span style="color: #555;">${lr.borrowing_rate ? (lr.borrowing_rate.toFixed(2) + '%') : 'N/A'}</span></div>
            </div>
        </div>
        
        <!-- Opening Balances -->
        <div class="summary-item" style="grid-column: 1 / -1;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; cursor: pointer;" onclick="toggleOpeningBalances()">
                <h3 style="margin: 0; font-size: 1rem; color: #2c3e50; font-weight: 600;">📊 Opening Balances</h3>
                <button id="openingBalancesToggle" class="btn-secondary" style="padding: 6px 12px; font-size: 0.85rem;">
                    Show Details
                </button>
            </div>
            
            <!-- Summary (Always Visible) -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px;">
                <div>
                    <strong>Lease Liability:</strong>
                    <span style="display: block; margin-top: 6px; font-size: 1.1rem;">$${formatCurrency(lr.opening_lease_liability || 0)}</span>
                </div>
                <div>
                    <strong>ROU Asset:</strong>
                    <span style="display: block; margin-top: 6px; font-size: 1.1rem;">$${formatCurrency(lr.opening_rou_asset || 0)}</span>
                </div>
            </div>
            
            <!-- Detailed View (Collapsed by Default) -->
            <div id="openingBalancesDetails" style="display: none; margin-top: 16px; padding-top: 16px; border-top: 2px solid #e0e0e0;">
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px;">
                    <div>
                        <strong>Lease Liability:</strong>
                        <span style="display: block; margin-top: 6px; font-size: 1.1rem;">$${formatCurrency(lr.opening_lease_liability || 0)}</span>
                    </div>
                    <div>
                        <strong>ROU Asset:</strong>
                        <span style="display: block; margin-top: 6px; font-size: 1.1rem;">$${formatCurrency(lr.opening_rou_asset || 0)}</span>
                    </div>
                    <div>
                        <strong>ARO Liability:</strong>
                        <span style="display: block; margin-top: 6px; font-size: 1.1rem;">$${formatCurrency(lr.opening_aro_liability || 0)}</span>
                    </div>
                    <div>
                        <strong>Security Deposit:</strong>
                        <span style="display: block; margin-top: 6px; font-size: 1.1rem;">$${formatCurrency(lr.opening_security_deposit || 0)}</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Period Activity -->
        <div class="summary-item">
            <strong>Total Interest</strong>
            <span>$${formatCurrency(lr.interest_expense || 0)}</span>
        </div>
        <div class="summary-item">
            <strong>Total Depreciation</strong>
            <span>$${formatCurrency(lr.depreciation_expense || 0)}</span>
        </div>
        <div class="summary-item">
            <strong>Total Rent Paid</strong>
            <span>$${formatCurrency(lr.rent_paid || 0)}</span>
        </div>
        <div class="summary-item">
            <strong>ARO Interest</strong>
            <span>$${formatCurrency(lr.aro_interest || 0)}</span>
        </div>
        <div class="summary-item">
            <strong>Security Deposit Interest</strong>
            <span>$${formatCurrency(lr.security_deposit_change || 0)}</span>
        </div>
        <div class="summary-item">
            <strong>Total Payments</strong>
            <span>${result.schedule ? result.schedule.filter(r => r.rental_amount && r.rental_amount > 0).length : 0}</span>
        </div>
        
        <!-- Closing Balances -->
        <div class="summary-item" style="grid-column: 1 / -1;">
            <h3 style="margin-bottom: 16px; font-size: 1rem; color: #2c3e50; font-weight: 600;">💰 Closing Balances</h3>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
                <div><strong>Lease Liability (Total):</strong> <span style="display: block; margin-top: 6px;">$${formatCurrency((lr.closing_lease_liability_non_current || 0) + (lr.closing_lease_liability_current || 0))}</span></div>
                <div><strong>Lease Liability (Non-Current):</strong> <span style="display: block; margin-top: 6px;">$${formatCurrency(lr.closing_lease_liability_non_current || 0)}</span></div>
                <div><strong>Lease Liability (Current):</strong> <span style="display: block; margin-top: 6px;">$${formatCurrency(lr.closing_lease_liability_current || 0)}</span></div>
                <div><strong>ROU Asset:</strong> <span style="display: block; margin-top: 6px;">$${formatCurrency(lr.closing_rou_asset || 0)}</span></div>
                <div><strong>ARO Liability:</strong> <span style="display: block; margin-top: 6px;">$${formatCurrency(lr.closing_aro_liability || 0)}</span></div>
                <div><strong>Security Deposit:</strong> <span style="display: block; margin-top: 6px;">$${formatCurrency(lr.closing_security_deposit || 0)}</span></div>
            </div>
        </div>
        
        <!-- Gain/Loss & Other -->
        <div class="summary-item">
            <strong>Gain/(Loss) P&L</strong>
            <span style="color: ${(lr.gain_loss_pnl || 0) >= 0 ? '#27ae60' : '#e74c3c'}">
                $${formatCurrency(lr.gain_loss_pnl || 0)}
            </span>
        </div>
        <div class="summary-item">
            <strong>Remaining ROU Life</strong>
            <span>${lr.remaining_rou_life ? Math.round(lr.remaining_rou_life) + ' days' : 'N/A'}</span>
        </div>
        
        <!-- Future Projections Section (Collapsible) -->
        ${(lr.projections && lr.projections.length > 0) ? `
        <div class="summary-item" style="grid-column: 1 / -1;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; cursor: pointer;" onclick="toggleProjections()">
                <h3 style="margin: 0; font-size: 1.1rem; color: #2c3e50; font-weight: 600;">
                    📈 Future Projections 
                    <span style="font-size: 0.85rem; color: #666; font-weight: 400;">(${lr.projections.length} period${lr.projections.length > 1 ? 's' : ''})</span>
                </h3>
                <button id="projectionsToggle" class="btn-secondary" style="padding: 6px 12px; font-size: 0.85rem;">
                    Show Details
                </button>
            </div>
            
            <!-- Summary (Always Visible) -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px;">
                <div>
                    <strong style="font-size: 0.875rem;">Next Period:</strong>
                    <span style="display: block; margin-top: 6px; font-size: 1rem;">${formatDate(lr.projections[0].projection_date)}</span>
                </div>
                <div>
                    <strong style="font-size: 0.875rem;">Liability:</strong>
                    <span style="display: block; margin-top: 6px; font-size: 1rem;">$${formatCurrency(lr.projections[0].closing_liability || 0)}</span>
                </div>
                <div>
                    <strong style="font-size: 0.875rem;">ROU Asset:</strong>
                    <span style="display: block; margin-top: 6px; font-size: 1rem;">$${formatCurrency(lr.projections[0].closing_rou_asset || 0)}</span>
                </div>
                <div>
                    <strong style="font-size: 0.875rem;">Total Rent:</strong>
                    <span style="display: block; margin-top: 6px; font-size: 1rem;">$${formatCurrency(lr.projections.reduce((sum, p) => sum + (p.rent_paid || 0), 0))}</span>
                </div>
            </div>
            
            <!-- Detailed Table (Collapsed by Default) -->
            <div id="projectionsDetails" style="display: none; margin-top: 20px; padding-top: 20px; border-top: 2px solid #e0e0e0; overflow-x: auto;">
                <div style="min-width: 100%; overflow-x: auto;">
                    <table style="width: 100%; min-width: 800px; border-collapse: collapse; font-size: 0.9rem; background: white; border: 1px solid #e0e0e0; border-radius: 6px;">
                        <thead>
                            <tr style="background-color: #f8f9fa;">
                                <th style="padding: 12px; text-align: left; border: 1px solid #e0e0e0; color: #2c3e50; font-weight: 600; white-space: nowrap;">Period</th>
                                <th style="padding: 12px; text-align: left; border: 1px solid #e0e0e0; color: #2c3e50; font-weight: 600; white-space: nowrap;">Projection Date</th>
                                <th style="padding: 12px; text-align: right; border: 1px solid #e0e0e0; color: #2c3e50; font-weight: 600; white-space: nowrap;">Closing Liability</th>
                                <th style="padding: 12px; text-align: right; border: 1px solid #e0e0e0; color: #2c3e50; font-weight: 600; white-space: nowrap;">Closing ROU Asset</th>
                                <th style="padding: 12px; text-align: right; border: 1px solid #e0e0e0; color: #2c3e50; font-weight: 600; white-space: nowrap;">Depreciation</th>
                                <th style="padding: 12px; text-align: right; border: 1px solid #e0e0e0; color: #2c3e50; font-weight: 600; white-space: nowrap;">Interest</th>
                                <th style="padding: 12px; text-align: right; border: 1px solid #e0e0e0; color: #2c3e50; font-weight: 600; white-space: nowrap;">Rent Paid</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${lr.projections.map((proj, idx) => {
                                const bgColor = idx % 2 === 0 ? '#fafafa' : '#ffffff';
                                return `
                                    <tr style="background-color: ${bgColor};">
                                        <td style="padding: 12px; border: 1px solid #e0e0e0; font-weight: 600; color: #2c3e50; white-space: nowrap;">
                                            Period ${proj.projection_mode || (idx + 1)}
                                        </td>
                                        <td style="padding: 12px; border: 1px solid #e0e0e0; color: #555; font-weight: 500; white-space: nowrap;">
                                            ${formatDate(proj.projection_date)}
                                        </td>
                                        <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #2c3e50; font-weight: 600; white-space: nowrap;">
                                            $${formatCurrency(proj.closing_liability || 0)}
                                        </td>
                                        <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #2c3e50; font-weight: 600; white-space: nowrap;">
                                            $${formatCurrency(proj.closing_rou_asset || 0)}
                                        </td>
                                        <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555; white-space: nowrap;">
                                            $${formatCurrency(proj.depreciation || 0)}
                                        </td>
                                        <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555; white-space: nowrap;">
                                            $${formatCurrency(proj.interest || 0)}
                                        </td>
                                        <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #27ae60; font-weight: 600; white-space: nowrap;">
                                            $${formatCurrency(proj.rent_paid || 0)}
                                        </td>
                                    </tr>
                                `;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        ` : ''}
    `;
    }

    // Display schedule with clean, minimal styling
    const scheduleBody = document.getElementById('scheduleBody');
    scheduleBody.innerHTML = result.schedule.map((row, idx) => {
        const bgColor = idx % 2 === 0 ? '#fafafa' : '#ffffff';
        // Highlight opening/closing rows subtly
        const rowStyle = idx === 0 ? 'background-color: #e8f4f8; font-weight: 500;' : 
                        idx === result.schedule.length - 1 ? 'background-color: #fff8e1; font-weight: 500;' : 
                        `background-color: ${bgColor};`;
        
        return `
        <tr style="${rowStyle}">
            <td style="padding: 12px; border: 1px solid #e0e0e0; color: #555;">${formatDate(row.date)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.rental_amount || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.principal || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">${(row.pv_factor || 0).toFixed(6)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.interest || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; font-weight: ${idx === 0 || idx === result.schedule.length - 1 ? '600' : '400'}; color: #2c3e50;">
                $${formatCurrency(row.lease_liability || 0)}
            </td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">${row.remaining_balance !== null && row.remaining_balance !== undefined ? '$' + formatCurrency(row.remaining_balance) : '-'}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.pv_of_rent || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; font-weight: ${idx === 0 || idx === result.schedule.length - 1 ? '600' : '400'}; color: #2c3e50;">
                $${formatCurrency(row.rou_asset || 0)}
            </td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.depreciation || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.change_in_rou || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.security_deposit_pv || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">${row.aro_gross !== null && row.aro_gross !== undefined ? '$' + formatCurrency(row.aro_gross) : '-'}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">${row.aro_interest !== null && row.aro_interest !== undefined ? '$' + formatCurrency(row.aro_interest) : '-'}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">${row.aro_provision !== null && row.aro_provision !== undefined ? '$' + formatCurrency(row.aro_provision) : '-'}</td>
        </tr>
    `;
    }).join('');

    // Display journal entries with clean, minimal styling
    const journalBody = document.getElementById('journalBody');
    journalBody.innerHTML = result.journal_entries.map((entry, idx) => {
        // Check if entry has opening_balance field (new feature)
        const openingBal = entry.opening_balance !== undefined ? entry.opening_balance : entry.previous_period;
        const ifrsAdj = entry.ifrs_adjustment !== undefined ? entry.ifrs_adjustment : (entry.result_period || 0);
        const usgaapEntry = entry.usgaap_entry !== undefined ? entry.usgaap_entry : 0;
        const bgColor = idx % 2 === 0 ? '#fafafa' : '#ffffff';
        return `
        <tr style="background-color: ${bgColor};">
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: center; font-weight: 500; color: #2c3e50;">${entry.account_code || '-'}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: left; color: #555;">${entry.account_name || ''}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: center; font-weight: 500; color: #2c3e50;">${entry.bs_pl || ''}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(openingBal || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(entry.previous_period || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(entry.result_period || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; font-weight: 500; color: #2c3e50;">$${formatCurrency(entry.incremental_adjustment || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(ifrsAdj || 0)}</td>
            <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(usgaapEntry || 0)}</td>
        </tr>
    `;
    }).join('');

    // Projections are now included directly in summaryGrid HTML above
    // Log projections for debugging
    console.log('📊 Projections data:', result.lease_result?.projections);

    document.getElementById('results').style.display = 'block';
    
    // Show export and email buttons after successful calculation
    document.getElementById('actionButtons').style.display = 'flex';
}

// Toggle function for projections details
function toggleProjections() {
    const detailsDiv = document.getElementById('projectionsDetails');
    const toggleBtn = document.getElementById('projectionsToggle');
    
    if (detailsDiv && toggleBtn) {
        if (detailsDiv.style.display === 'none' || detailsDiv.style.display === '') {
            detailsDiv.style.display = 'block';
            toggleBtn.textContent = 'Hide Details';
        } else {
            detailsDiv.style.display = 'none';
            toggleBtn.textContent = 'Show Details';
        }
    }
}

// Toggle function for opening balances details
function toggleOpeningBalances() {
    const detailsDiv = document.getElementById('openingBalancesDetails');
    const toggleBtn = document.getElementById('openingBalancesToggle');
    
    if (detailsDiv && toggleBtn) {
        if (detailsDiv.style.display === 'none' || detailsDiv.style.display === '') {
            detailsDiv.style.display = 'block';
            toggleBtn.textContent = 'Hide Details';
        } else {
            detailsDiv.style.display = 'none';
            toggleBtn.textContent = 'Show Details';
        }
    }
}
// This ensures the heading and table always appear together when projections exist

function displayKeyValues(lr, schedule) {
    const keyValuesGrid = document.getElementById('keyValuesGrid');
    if (!keyValuesGrid) return;
    
    // Calculate interest incurred since inception (sum of all interest from start)
    const totalInterestIncurred = schedule.reduce((sum, row) => sum + (row.interest || 0), 0);
    
    // Calculate amortization incurred since inception (sum of all depreciation from start)
    const totalAmortizationIncurred = schedule.reduce((sum, row) => sum + (row.depreciation || 0), 0);
    
    // Calculate forecasted interest (from projections or remaining periods)
    const forecastedInterest = lr.projections ? 
        lr.projections.reduce((sum, proj) => sum + (proj.interest || 0), 0) : 
        (lr.interest_expense || 0);
    
    // Calculate forecasted amortization
    const forecastedAmortization = lr.projections ?
        lr.projections.reduce((sum, proj) => sum + (proj.depreciation || 0), 0) :
        (lr.depreciation_expense || 0);
    
    // Set default "As of" date to end date or today
    const asOfDateInput = document.getElementById('asOfDate');
    if (asOfDateInput && !asOfDateInput.value) {
        const endDate = schedule.length > 0 ? schedule[schedule.length - 1].date : new Date().toISOString().split('T')[0];
        asOfDateInput.value = endDate;
    }
    
    keyValuesGrid.innerHTML = `
        <div class="key-value-card">
            <div class="key-value-icon rou">ROU</div>
            <div class="key-value-content">
                <div class="key-value-label">ROU Asset value</div>
                <div class="key-value-amount">USD ${formatCurrency(lr.closing_rou_asset || 0)}</div>
            </div>
        </div>
        <div class="key-value-card">
            <div class="key-value-icon liability">LL</div>
            <div class="key-value-content">
                <div class="key-value-label">Lease Liability</div>
                <div class="key-value-amount">USD ${formatCurrency((lr.closing_lease_liability_non_current || 0) + (lr.closing_lease_liability_current || 0))}</div>
            </div>
        </div>
        <div class="key-value-card">
            <div class="key-value-icon lhi">LHI</div>
            <div class="key-value-content">
                <div class="key-value-label">Leasehold Improvement</div>
                <div class="key-value-amount">USD ${formatCurrency(0)}</div>
            </div>
        </div>
        <div class="key-value-card">
            <div class="key-value-icon aro">ARO</div>
            <div class="key-value-content">
                <div class="key-value-label">Asset Retirement Obligation</div>
                <div class="key-value-amount">USD ${formatCurrency(lr.closing_aro_liability || 0)}</div>
            </div>
        </div>
        <div class="key-value-card">
            <div class="key-value-icon interest">II</div>
            <div class="key-value-content">
                <div class="key-value-label">Interest Incurred Since Inception</div>
                <div class="key-value-amount">USD ${formatCurrency(totalInterestIncurred)}</div>
            </div>
        </div>
        <div class="key-value-card">
            <div class="key-value-icon forecast-interest">FI</div>
            <div class="key-value-content">
                <div class="key-value-label">Forecasted Interest To Be Incurred</div>
                <div class="key-value-amount">USD ${formatCurrency(forecastedInterest)}</div>
            </div>
        </div>
        <div class="key-value-card">
            <div class="key-value-icon amortization">AI</div>
            <div class="key-value-content">
                <div class="key-value-label">Amortization Incurred</div>
                <div class="key-value-amount">USD ${formatCurrency(totalAmortizationIncurred)}</div>
            </div>
        </div>
        <div class="key-value-card">
            <div class="key-value-icon forecast-amortization">AF</div>
            <div class="key-value-content">
                <div class="key-value-label">Amortization Forecasted</div>
                <div class="key-value-amount">USD ${formatCurrency(forecastedAmortization)}</div>
            </div>
        </div>
    `;
}

function updateKeyValues() {
    // This can be called when "As of" date changes to recalculate values
    // For now, we'll just reload if needed
}

function createCharts(lr, schedule) {
    // Destroy existing charts if they exist
    if (npvChart) npvChart.destroy();
    if (liabilityAssetChart) liabilityAssetChart.destroy();
    if (interestDepreciationChart) interestDepreciationChart.destroy();
    
    // Prepare data for charts
    const dates = schedule.map(row => new Date(row.date).toLocaleDateString('en-US', { year: '2-digit', month: '2-digit', day: '2-digit' }));
    const liabilities = schedule.map(row => row.lease_liability || 0);
    const rouAssets = schedule.map(row => row.rou_asset || 0);
    const interests = schedule.map(row => row.interest || 0);
    const depreciations = schedule.map(row => row.depreciation || 0);
    const rentals = schedule.map(row => row.rental_amount || 0);
    const pvOfRent = schedule.map(row => row.pv_of_rent || 0);
    
    // Net Present Value Chart (Bar Chart)
    const npvCtx = document.getElementById('npvChart');
    if (npvCtx) {
        npvChart = new Chart(npvCtx, {
            type: 'bar',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'Lease Liability',
                        data: liabilities,
                        backgroundColor: 'rgba(231, 76, 60, 0.6)',
                        borderColor: 'rgba(231, 76, 60, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'ROU Asset',
                        data: rouAssets,
                        backgroundColor: 'rgba(39, 174, 96, 0.6)',
                        borderColor: 'rgba(39, 174, 96, 1)',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    title: {
                        display: false
                    },
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: function(value) {
                                return 'USD ' + value.toLocaleString();
                            }
                        }
                    },
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                }
            }
        });
    }
    
    // Liability & Asset Trend Chart (Line Chart)
    const liabilityAssetCtx = document.getElementById('liabilityAssetChart');
    if (liabilityAssetCtx) {
        liabilityAssetChart = new Chart(liabilityAssetCtx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'Lease Liability',
                        data: liabilities,
                        borderColor: 'rgba(231, 76, 60, 1)',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'ROU Asset',
                        data: rouAssets,
                        borderColor: 'rgba(39, 174, 96, 1)',
                        backgroundColor: 'rgba(39, 174, 96, 0.1)',
                        tension: 0.4,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        ticks: {
                            callback: function(value) {
                                return 'USD ' + value.toLocaleString();
                            }
                        }
                    },
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                }
            }
        });
    }
    
    // Interest & Depreciation Chart (Line Chart)
    const interestDepreciationCtx = document.getElementById('interestDepreciationChart');
    if (interestDepreciationCtx) {
        interestDepreciationChart = new Chart(interestDepreciationCtx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'Interest',
                        data: interests,
                        borderColor: 'rgba(52, 152, 219, 1)',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Depreciation',
                        data: depreciations,
                        borderColor: 'rgba(243, 156, 18, 1)',
                        backgroundColor: 'rgba(243, 156, 18, 0.1)',
                        tension: 0.4,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return 'USD ' + value.toLocaleString();
                            }
                        }
                    },
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                }
            }
        });
    }
}

function formatCurrency(value) {
    return Math.abs(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function showError(message) {
    showModal('Error', message);
}

function openEmailModal() {
    const emailModal = document.getElementById('emailModal');
    const emailTo = document.getElementById('emailTo');
    const emailSubject = document.getElementById('emailSubject');
    const emailBody = document.getElementById('emailBody');

    // Pre-fill with logged-in user's email
    const currentUser = JSON.parse(sessionStorage.getItem('currentUser'));
    if (currentUser && currentUser.email) {
        emailTo.value = currentUser.email;
    }

    emailSubject.value = 'Lease Calculation Report';
    emailBody.value = 'Please find the attached lease calculation report.';
    emailModal.style.display = 'block';
}

function closeEmailModal() {
    const emailModal = document.getElementById('emailModal');
    emailModal.style.display = 'none';
}

async function sendEmail() {
    const to_email = document.getElementById('emailTo').value;
    const subject = document.getElementById('emailSubject').value;
    const body = document.getElementById('emailBody').value;

    // Show loading modal
    Swal.fire({
        title: 'Sending Email...',
        text: 'Please wait while the report is being sent.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });

    // Generate the Excel file content
    const wb = generateExcelWorkbook();
    const wbout = XLSX.write(wb, { bookType: 'xlsx', type: 'base64' });

    try {
        const response = await fetch('/api/send_report', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                to_email,
                subject,
                body,
                attachment_content: wbout,
                attachment_filename: 'Lease_Calculation_Report.xlsx'
            })
        });

        const result = await response.json();
        if (result.success) {
            Swal.close();
            showAlert('Email sent successfully!', 'success');
            closeEmailModal();
        } else {
            Swal.close();
            showAlert(`Error sending email: ${result.error}`, 'error');
        }
    } catch (error) {
        Swal.close();
        showAlert(`Error sending email: ${error.message}`, 'error');
    }
}

function generateExcelWorkbook() {
    const today = new Date();
    
    // Get data from displayed tables
    const scheduleData = Array.from(document.querySelectorAll('#scheduleBody tr')).map(row => {
        const cells = row.querySelectorAll('td');
        return {
            'Date': cells[0].textContent,
            'Rental': cells[1].textContent,
            'Principal': cells[2].textContent,
            'PV Factor': cells[3].textContent,
            'Interest': cells[4].textContent,
            'Lease Liability': cells[5].textContent,
            'Remaining Balance': cells[6].textContent,
            'PV of Rent': cells[7].textContent,
            'ROU Asset': cells[8].textContent,
            'Depreciation': cells[9].textContent,
            'Change ROU': cells[10].textContent,
            'Security PV': cells[11].textContent,
            'ARO Gross': cells[12].textContent,
            'ARO Interest': cells[13].textContent,
            'ARO Provision': cells[14].textContent
        };
    });

    const journalData = Array.from(document.querySelectorAll('#journalBody tr')).map(row => {
        const cells = row.querySelectorAll('td');
        return {
            'Account Code': cells[0].textContent,
            'Account Name': cells[1].textContent,
            'BS/PL': cells[2].textContent,
            'Result Period': cells[3].textContent,
            'Previous Period': cells[4].textContent,
            'Incremental': cells[5].textContent,
            'US-GAAP': cells[6].textContent,
            'IFRS Adjustment': cells[7].textContent
        };
    });
    
    // Get summary data from displayed HTML (using <strong> and <span> tags)
    const summaryValues = {};
    document.querySelectorAll('#summaryGrid .summary-item').forEach(item => {
        const strong = item.querySelector('strong');
        const span = item.querySelector('span');
        if (strong && span) {
            const label = strong.textContent.trim();
            const value = span.textContent.trim();
            // Skip items with specific styling (grid-column, etc.)
            const hasGridColumn = item.style.gridColumn || item.getAttribute('style')?.includes('grid-column');
            if (!hasGridColumn && label && value) {
                summaryValues[label] = value;
            }
        }
    });

    // Create workbook
    const wb = XLSX.utils.book_new();
    
    // 1. ENHANCED Summary Sheet
    const summarySheetData = [
        ['LEASE CALCULATION SUMMARY REPORT'],
        [],
        ['Report Information'],
        ['Generated Date', today.toLocaleDateString() + ' ' + today.toLocaleTimeString()],
        [],
        ['Financial Summary'],
        ...Object.entries(summaryValues).map(([label, value]) => [label, value]),
    ];
    const wsSummary = XLSX.utils.aoa_to_sheet(summarySheetData);
    wsSummary['!cols'] = [{ wch: 30 }, { wch: 22 }];
    XLSX.utils.book_append_sheet(wb, wsSummary, 'Summary');
    
    // 2. Schedule Sheet with formatting
    const wsSchedule = XLSX.utils.json_to_sheet(scheduleData);
    wsSchedule['!cols'] = [
        { wch: 12 }, { wch: 15 }, { wch: 12 }, { wch: 12 }, { wch: 15 },
        { wch: 18 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 },
        { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }
    ];
    XLSX.utils.book_append_sheet(wb, wsSchedule, 'Schedule');
    
    // 3. Journal Entries Sheet with formatting
    const wsJournal = XLSX.utils.json_to_sheet(journalData);
    wsJournal['!cols'] = [{ wch: 12 }, { wch: 35 }, { wch: 8 }, { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 18 }];
    XLSX.utils.book_append_sheet(wb, wsJournal, 'Journal Entries');

    return wb;
}

function exportToExcel() {
    const today = new Date();
    
    // Get data from displayed tables
    const scheduleData = Array.from(document.querySelectorAll('#scheduleBody tr')).map(row => {
        const cells = row.querySelectorAll('td');
        return {
            'Date': cells[0].textContent,
            'Rental': cells[1].textContent,
            'Principal': cells[2].textContent,
            'PV Factor': cells[3].textContent,
            'Interest': cells[4].textContent,
            'Lease Liability': cells[5].textContent,
            'Remaining Balance': cells[6].textContent,
            'PV of Rent': cells[7].textContent,
            'ROU Asset': cells[8].textContent,
            'Depreciation': cells[9].textContent,
            'Change ROU': cells[10].textContent,
            'Security PV': cells[11].textContent,
            'ARO Gross': cells[12].textContent,
            'ARO Interest': cells[13].textContent,
            'ARO Provision': cells[14].textContent
        };
    });

    const journalData = Array.from(document.querySelectorAll('#journalBody tr')).map(row => {
        const cells = row.querySelectorAll('td');
        return {
            'Account Code': cells[0].textContent,
            'Account Name': cells[1].textContent,
            'BS/PL': cells[2].textContent,
            'Result Period': cells[3].textContent,
            'Previous Period': cells[4].textContent,
            'Incremental': cells[5].textContent,
            'US-GAAP': cells[6].textContent,
            'IFRS Adjustment': cells[7].textContent
        };
    });
    
    // Get summary data from displayed HTML (using <strong> and <span> tags)
    const summaryValues = {};
    document.querySelectorAll('#summaryGrid .summary-item').forEach(item => {
        const strong = item.querySelector('strong');
        const span = item.querySelector('span');
        if (strong && span) {
            const label = strong.textContent.trim();
            const value = span.textContent.trim();
            // Skip items with specific styling (grid-column, etc.)
            const hasGridColumn = item.style.gridColumn || item.getAttribute('style')?.includes('grid-column');
            if (!hasGridColumn && label && value) {
                summaryValues[label] = value;
            }
        }
    });

    // Create workbook
    const wb = XLSX.utils.book_new();
    
    // 1. ENHANCED Summary Sheet
    const summarySheetData = [
        ['LEASE CALCULATION SUMMARY REPORT'],
        [],
        ['Report Information'],
        ['Generated Date', today.toLocaleDateString() + ' ' + today.toLocaleTimeString()],
        [],
        ['Financial Summary'],
        ...Object.entries(summaryValues).map(([label, value]) => [label, value]),
    ];
    const wsSummary = XLSX.utils.aoa_to_sheet(summarySheetData);
    wsSummary['!cols'] = [{ wch: 30 }, { wch: 22 }];
    XLSX.utils.book_append_sheet(wb, wsSummary, 'Summary');
    
    // 2. Schedule Sheet with formatting
    const wsSchedule = XLSX.utils.json_to_sheet(scheduleData);
    wsSchedule['!cols'] = [
        { wch: 12 }, { wch: 15 }, { wch: 12 }, { wch: 12 }, { wch: 15 },
        { wch: 18 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 },
        { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }, { wch: 15 }
    ];
    XLSX.utils.book_append_sheet(wb, wsSchedule, 'Schedule');
    
    // 3. Journal Entries Sheet with formatting
    const wsJournal = XLSX.utils.json_to_sheet(journalData);
    wsJournal['!cols'] = [{ wch: 12 }, { wch: 35 }, { wch: 8 }, { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 18 }];
    XLSX.utils.book_append_sheet(wb, wsJournal, 'Journal Entries');

    // Download with timestamp
    const timestamp = today.toISOString().split('T')[0].replace(/-/g, '');
    const leaseId = document.getElementById('leaseSelect').value;
    const filename = `Lease_${leaseId}_${timestamp}.xlsx`;
    XLSX.writeFile(wb, filename);
    
    showModal('Success', '✅ Enhanced Excel report downloaded!\n\nFile: ' + filename + '\n\nContains:\n• Professional summary with metadata\n• Amortization schedule\n• Journal entries\n• Timestamped filename');
}

async function logout() {
    try {
        await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
        window.location.href = 'login.html';
    } catch (error) {
        window.location.href = 'login.html';
    }
}

// Email Modal Functions
function showEmailModal() {
    // Get current user's email
    fetch('/api/user', {
        credentials: 'include'
    })
    .then(response => response.json())
    .then(data => {
        const defaultEmail = (data.success && data.user && data.user.email) ? data.user.email : '';
        document.getElementById('recipientEmail').value = defaultEmail;
        document.getElementById('emailModal').style.display = 'block';
    })
    .catch(err => {
        document.getElementById('recipientEmail').value = '';
        document.getElementById('emailModal').style.display = 'block';
    });
}

function hideEmailModal() {
    document.getElementById('emailModal').style.display = 'none';
}

async function sendReportEmail() {
    const toEmail = document.getElementById('recipientEmail').value.trim();
    if (!toEmail || !toEmail.match(/^\S+@\S+\.\S+$/)) {
        showModal('Error', '❌ Please enter a valid recipient email');
        return;
    }
    hideEmailModal();
    
    try {
        // Generate Excel file using same logic as exportToExcel
        const today = new Date();
        
        // Get data from summary
        const summaryItems = document.querySelectorAll('.summary-item');
        const summaryData = {};
        summaryItems.forEach(item => {
            const labelEl = item.querySelector('.summary-label');
            const valueEl = item.querySelector('.summary-value');
            if (labelEl && valueEl) {
                const label = labelEl.textContent.trim();
                const value = valueEl.textContent.trim();
                summaryData[label] = value;
            }
        });
        
        // Get schedule table data
        const scheduleData = [];
        const scheduleRows = document.querySelectorAll('#scheduleTable tbody tr');
        scheduleRows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length > 0) {
                scheduleData.push({
                    Date: cells[0]?.textContent || '',
                    Rental: cells[1]?.textContent || '',
                    Principal: cells[2]?.textContent || '',
                    'PV Factor': cells[3]?.textContent || '',
                    Interest: cells[4]?.textContent || '',
                    Liability: cells[5]?.textContent || '',
                    'PV of Rent': cells[6]?.textContent || '',
                    'ROU Asset': cells[7]?.textContent || '',
                    Depreciation: cells[8]?.textContent || ''
                });
            }
        });
        
        // Get journal entries data
        const journalData = [];
        const journalRows = document.querySelectorAll('#journalTable tbody tr');
        journalRows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length > 0) {
                journalData.push({
                    'BS/PL': cells[0]?.textContent || '',
                    'Account Name': cells[1]?.textContent || '',
                    'Result Period': cells[2]?.textContent || '',
                    'Previous Period': cells[3]?.textContent || '',
                    'Incremental': cells[4]?.textContent || '',
                    'IFRS Adjustment': cells[5]?.textContent || '',
                    'US-GAAP Entry': cells[6]?.textContent || '',
                    'Opening Balance': cells[7]?.textContent || ''
                });
            }
        });
        
        // Create Excel workbook
        const wb = XLSX.utils.book_new();
        
        // Summary sheet
        const summarySheetData = [
            ['Summary'],
            ...Object.entries(summaryData).map(([k, v]) => [k, v])
        ];
        const wsSummary = XLSX.utils.aoa_to_sheet(summarySheetData);
        XLSX.utils.book_append_sheet(wb, wsSummary, 'Summary');
        
        // Schedule sheet
        const wsSchedule = XLSX.utils.json_to_sheet(scheduleData);
        XLSX.utils.book_append_sheet(wb, wsSchedule, 'Amortization Schedule');
        
        // Journal sheet
        const wsJournal = XLSX.utils.json_to_sheet(journalData);
        XLSX.utils.book_append_sheet(wb, wsJournal, 'Journal Entries');
        
        // Convert to blob
        const wbout = XLSX.write(wb, {bookType: 'xlsx', type: 'array'});
        const fileBlob = new Blob([wbout], {type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
        
        // Send via API
        const formData = new FormData();
        formData.append('to_email', toEmail);
        formData.append('attachment', fileBlob, 'Lease_Report.xlsx');
        
        const timestamp = today.toISOString().split('T')[0].replace(/-/g, '');
        const leaseId = document.getElementById('leaseSelect').value;
        const filename = `Lease_${leaseId}_${timestamp}.xlsx`;
        
        // Add report data
        formData.append('report_json', JSON.stringify({
            filename: filename,
            summary: summaryData,
            timestamp: timestamp
        }));
        
        const response = await fetch('/api/email/send-report', {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showModal('Success', '✅ Report sent to ' + toEmail + '!');
        } else {
            showModal('Error', '❌ Failed to send: ' + (result.error || 'Unknown error'));
        }
    } catch (error) {
        showModal('Error', '❌ Error sending email: ' + error.message);
    }
}
