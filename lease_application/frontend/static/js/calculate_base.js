    <script>
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
                if (lease.end_date && !document.getElementById('toDate').value) {
                    document.getElementById('toDate').value = lease.end_date;
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
                const userResponse = await fetch('http://localhost:5001/api/user', {
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
                const response = await fetch('http://localhost:5001/api/leases', {
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
                
                select.innerHTML = '<option value="">Select a lease...</option>';
                
                // Filter to only approved leases for calculation
                const approvedLeases = leases.filter(lease => 
                    lease.approval_status === 'approved' || lease.approval_status === null || lease.approval_status === 'draft'
                );
                
                if (approvedLeases.length === 0) {
                    select.innerHTML = '<option value="">No approved leases found</option>';
                } else {
                approvedLeases.forEach(lease => {
                    const option = document.createElement('option');
                    option.value = lease.lease_id;
                    option.textContent = `${lease.lease_name || 'Lease_' + lease.lease_id} - ${lease.asset_id_code || 'N/A'}`;
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
                    showError('Please login to view your leases. Redirecting to login...');
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
                description: lease.description || '',
                asset_class: lease.asset_class || '',
                asset_id_code: lease.asset_id_code || '',
                lease_start_date: ensureDate(lease.lease_start_date),
                first_payment_date: ensureDate(lease.first_payment_date, lease.lease_start_date),
                end_date: ensureDate(lease.end_date),
                agreement_date: ensureDate(lease.agreement_date, null),
                termination_date: ensureDate(lease.termination_date, null),
                date_modified: ensureDate(lease.date_modified, null),
                tenure: lease.tenure || 0,
                frequency_months: lease.frequency_months || lease.rent_frequency || 1,  // Check frequency_months FIRST, then rent_frequency
                day_of_month: lease.day_of_month || '1',
                accrual_day: lease.accrual_day || 1,
                manual_adj: lease.manual_adj || 'No',
                // CRITICAL: Handle null/undefined but preserve 0 if explicitly set
                rental_1: (lease.rental_1 !== null && lease.rental_1 !== undefined) ? (lease.rental_1 || 0) : 0,
                rental_2: (lease.rental_2 !== null && lease.rental_2 !== undefined) ? (lease.rental_2 || 0) : 0,
                // Rental Schedule - always include if provided (source of truth for rentals)
                rental_schedule: lease.rental_schedule || null,
                escalation_start_date: ensureDate(lease.escalation_start_date, null),
                escalation_percent: lease.escalation_percent || 0,
                esc_freq_months: (lease.esc_freq_months || lease.escalation_frequency) ? (lease.esc_freq_months || lease.escalation_frequency) : null,
                index_rate_table: lease.index_rate_table || '',
                ibr: lease.ibr ?? null,  // Changed from borrowing_rate to ibr to match API
                compound_months: lease.compound_months || 12,
                fv_of_rou: lease.fv_of_rou || 0,
                currency: lease.currency || 'USD',
                cost_centre: lease.cost_centre || '',
                counterparty: lease.counterparty || '',
                security_deposit: lease.security_deposit || 0,
                security_discount: lease.security_discount || 0,
                aro: lease.aro || 0,
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
                const leaseResponse = await fetch(`http://localhost:5001/api/leases/${leaseId}`, {
                    credentials: 'include'
                });

                if (!leaseResponse.ok) {
                    throw new Error('Failed to load lease data');
                }

                const leaseResponseData = await leaseResponse.json();
                console.log('📋 Lease data from API:', leaseResponseData);
                
                // Extract lease object (API returns {success: true, lease: {...}})
                const lease = leaseResponseData.lease || leaseResponseData;
                console.log('📋 Extracted lease object:', lease);
                console.log('📋 rental_1 value:', lease.rental_1, 'type:', typeof lease.rental_1);
                
                // CRITICAL FIX: Ensure rental_1 is a number
                if (lease.rental_1 !== null && lease.rental_1 !== undefined) {
                    lease.rental_1 = parseFloat(lease.rental_1) || 0;
                } else {
                    lease.rental_1 = 0;
                }
                console.log('📋 rental_1 after parseFloat:', lease.rental_1);
                
                // Map lease to calculation format
                const calculationData = mapLeaseToCalculation(lease);
                console.log('📋 Mapped calculation data:', calculationData);
                console.log('📋 rental_1 after mapping:', calculationData.rental_1);
                calculationData.from_date = fromDate;
                calculationData.to_date = toDate;

                // Calculate
                const response = await fetch('http://localhost:5001/api/calculate_lease', {
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

        function displayResults(result) {
            const lr = result.lease_result || {};
            
            // Display summary with ALL available data
            const summaryGrid = document.getElementById('summaryGrid');
            summaryGrid.innerHTML = `
                <!-- Lease Information -->
                <div class="summary-item" style="grid-column: 1 / -1; background: rgba(255,255,255,0.15); padding: 20px; border-radius: 8px;">
                    <h3 style="margin-bottom: 10px; font-size: 1.1rem;">Lease Information</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;">
                        <div><strong>Description:</strong> ${lr.description || 'N/A'}</div>
                        <div><strong>Asset Code:</strong> ${lr.asset_code || 'N/A'}</div>
                        <div><strong>Asset Class:</strong> ${lr.asset_class || 'N/A'}</div>
                        <div><strong>Cost Center:</strong> ${lr.cost_center || 'N/A'}</div>
                        <div><strong>Currency:</strong> ${lr.currency || 'USD'}</div>
                        <div><strong>Borrowing Rate:</strong> ${lr.borrowing_rate ? (lr.borrowing_rate.toFixed(2) + '%') : 'N/A'}</div>
                    </div>
                </div>
                
                <!-- Opening Balances (Collapsible) -->
                <div class="summary-item" style="grid-column: 1 / -1; background: rgba(102, 126, 234, 0.15); padding: 15px; border-radius: 8px; margin-top: 10px; border: 1px solid rgba(102, 126, 234, 0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; cursor: pointer;" onclick="toggleOpeningBalances()">
                        <h3 style="margin: 0; font-size: 1rem; color: #ffffff; font-weight: 600;">📊 Opening Balances</h3>
                        <button id="openingBalancesToggle" style="background: #667eea; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85rem; font-weight: 500;">
                            Show Details
                        </button>
                    </div>
                    
                    <!-- Summary (Always Visible) -->
                    <div style="margin-top: 12px; padding: 10px; background: rgba(255, 255, 255, 0.15); border-radius: 6px;">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; font-size: 0.9rem;">
                            <div>
                                <strong style="color: #ffffff; opacity: 0.9;">Lease Liability:</strong>
                                <span style="color: #ffffff; font-weight: 700; display: block; margin-top: 4px; font-size: 1rem;">$${formatCurrency(lr.opening_lease_liability || 0)}</span>
                            </div>
                            <div>
                                <strong style="color: #ffffff; opacity: 0.9;">ROU Asset:</strong>
                                <span style="color: #ffffff; font-weight: 700; display: block; margin-top: 4px; font-size: 1rem;">$${formatCurrency(lr.opening_rou_asset || 0)}</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Detailed View (Collapsed by Default) -->
                    <div id="openingBalancesDetails" style="display: none; margin-top: 12px; padding-top: 12px; border-top: 2px solid rgba(255, 255, 255, 0.3);">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; font-size: 0.9rem;">
                            <div>
                                <strong style="color: #ffffff; opacity: 0.9;">Lease Liability:</strong>
                                <span style="color: #ffffff; font-weight: 700; display: block; margin-top: 4px; font-size: 1rem;">$${formatCurrency(lr.opening_lease_liability || 0)}</span>
                            </div>
                            <div>
                                <strong style="color: #ffffff; opacity: 0.9;">ROU Asset:</strong>
                                <span style="color: #ffffff; font-weight: 700; display: block; margin-top: 4px; font-size: 1rem;">$${formatCurrency(lr.opening_rou_asset || 0)}</span>
                            </div>
                            <div>
                                <strong style="color: #ffffff; opacity: 0.9;">ARO Liability:</strong>
                                <span style="color: #ffffff; font-weight: 700; display: block; margin-top: 4px; font-size: 1rem;">$${formatCurrency(lr.opening_aro_liability || 0)}</span>
                            </div>
                            <div>
                                <strong style="color: #ffffff; opacity: 0.9;">Security Deposit:</strong>
                                <span style="color: #ffffff; font-weight: 700; display: block; margin-top: 4px; font-size: 1rem;">$${formatCurrency(lr.opening_security_deposit || 0)}</span>
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
                <div class="summary-item" style="grid-column: 1 / -1; background: rgba(118, 75, 162, 0.2); padding: 15px; border-radius: 8px; margin-top: 10px;">
                    <h3 style="margin-bottom: 10px; font-size: 1rem;">💰 Closing Balances</h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px;">
                        <div><strong>Lease Liability (Total):</strong> <span>$${formatCurrency((lr.closing_lease_liability_non_current || 0) + (lr.closing_lease_liability_current || 0))}</span></div>
                        <div><strong>Lease Liability (Non-Current):</strong> <span>$${formatCurrency(lr.closing_lease_liability_non_current || 0)}</span></div>
                        <div><strong>Lease Liability (Current):</strong> <span>$${formatCurrency(lr.closing_lease_liability_current || 0)}</span></div>
                        <div><strong>ROU Asset:</strong> <span>$${formatCurrency(lr.closing_rou_asset || 0)}</span></div>
                        <div><strong>ARO Liability:</strong> <span>$${formatCurrency(lr.closing_aro_liability || 0)}</span></div>
                        <div><strong>Security Deposit:</strong> <span>$${formatCurrency(lr.closing_security_deposit || 0)}</span></div>
                    </div>
                </div>
                
                <!-- Gain/Loss & Other -->
                <div class="summary-item">
                    <strong>Gain/(Loss) P&L</strong>
                    <span style="color: ${(lr.gain_loss_pnl || 0) >= 0 ? '#4caf50' : '#f44336'}">
                        $${formatCurrency(lr.gain_loss_pnl || 0)}
                    </span>
                </div>
                <div class="summary-item">
                    <strong>Remaining ROU Life</strong>
                    <span>${lr.remaining_rou_life ? Math.round(lr.remaining_rou_life) + ' days' : 'N/A'}</span>
                </div>
                
                <!-- Future Projections Section (Collapsible) -->
                ${(lr.projections && lr.projections.length > 0) ? `
                <div class="summary-item" style="grid-column: 1 / -1; background: rgba(102, 126, 234, 0.15); padding: 15px; border-radius: 8px; margin-top: 20px; border: 1px solid rgba(102, 126, 234, 0.3);">
                    <div style="display: flex; justify-content: space-between; align-items: center; cursor: pointer;" onclick="toggleProjections()">
                        <h3 style="margin: 0; font-size: 1.1rem; color: #ffffff; font-weight: 600;">
                            📈 Future Projections 
                            <span style="font-size: 0.85rem; color: #ffffff; opacity: 0.85; font-weight: 400;">(${lr.projections.length} period${lr.projections.length > 1 ? 's' : ''})</span>
                        </h3>
                        <button id="projectionsToggle" style="background: #667eea; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85rem; font-weight: 500;">
                            Show Details
                        </button>
                    </div>
                    
                    <!-- Summary (Always Visible) -->
                    <div style="margin-top: 15px; padding: 12px; background: rgba(255, 255, 255, 0.15); border-radius: 6px;">
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; font-size: 0.9rem;">
                            <div>
                                <strong style="color: #ffffff; opacity: 0.9; font-size: 0.85rem; display: block; margin-bottom: 4px;">Next Period:</strong>
                                <span style="color: #ffffff; font-weight: 700; font-size: 0.95rem;">${formatDate(lr.projections[0].projection_date)}</span>
                            </div>
                            <div>
                                <strong style="color: #ffffff; opacity: 0.9; font-size: 0.85rem; display: block; margin-bottom: 4px;">Liability:</strong>
                                <span style="color: #ffffff; font-weight: 700; font-size: 0.95rem;">$${formatCurrency(lr.projections[0].closing_liability || 0)}</span>
                            </div>
                            <div>
                                <strong style="color: #ffffff; opacity: 0.9; font-size: 0.85rem; display: block; margin-bottom: 4px;">ROU Asset:</strong>
                                <span style="color: #ffffff; font-weight: 700; font-size: 0.95rem;">$${formatCurrency(lr.projections[0].closing_rou_asset || 0)}</span>
                            </div>
                            <div>
                                <strong style="color: #ffffff; opacity: 0.9; font-size: 0.85rem; display: block; margin-bottom: 4px;">Total Rent:</strong>
                                <span style="color: #ffffff; font-weight: 700; font-size: 0.95rem;">$${formatCurrency(lr.projections.reduce((sum, p) => sum + (p.rent_paid || 0), 0))}</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Detailed Table (Collapsed by Default) - Responsive -->
                    <div id="projectionsDetails" style="display: none; margin-top: 15px; padding-top: 15px; border-top: 2px solid rgba(102, 126, 234, 0.2); overflow-x: auto;">
                        <div style="min-width: 100%; overflow-x: auto;">
                            <table style="width: 100%; min-width: 800px; border-collapse: collapse; font-size: 0.9rem; background: white;">
                                <thead>
                                    <tr>
                                        <th style="padding: 12px; text-align: left; border: 1px solid #ddd; color: white; font-weight: 600; white-space: nowrap;">Period</th>
                                        <th style="padding: 12px; text-align: left; border: 1px solid #ddd; color: white; font-weight: 600; white-space: nowrap;">Projection Date</th>
                                        <th style="padding: 12px; text-align: right; border: 1px solid #ddd; color: white; font-weight: 600; white-space: nowrap;">Closing Liability</th>
                                        <th style="padding: 12px; text-align: right; border: 1px solid #ddd; color: white; font-weight: 600; white-space: nowrap;">Closing ROU Asset</th>
                                        <th style="padding: 12px; text-align: right; border: 1px solid #ddd; color: white; font-weight: 600; white-space: nowrap;">Depreciation</th>
                                        <th style="padding: 12px; text-align: right; border: 1px solid #ddd; color: white; font-weight: 600; white-space: nowrap;">Interest</th>
                                        <th style="padding: 12px; text-align: right; border: 1px solid #ddd; color: white; font-weight: 600; white-space: nowrap;">Rent Paid</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${lr.projections.map((proj, idx) => {
                                        const bgColor = idx % 2 === 0 ? '#f8f9ff' : '#ffffff';
                                        const rowColor = idx % 2 === 0 ? '#667eea' : '#764ba2';
                                        return `
                                            <tr style="background-color: ${bgColor};">
                                                <td style="padding: 10px; border: 1px solid #e0e0e0; font-weight: 600; color: ${rowColor}; white-space: nowrap;">
                                                    Period ${proj.projection_mode || (idx + 1)}
                                                </td>
                                                <td style="padding: 10px; border: 1px solid #e0e0e0; color: #333; font-weight: 500; white-space: nowrap;">
                                                    ${formatDate(proj.projection_date)}
                                                </td>
                                                <td style="padding: 10px; border: 1px solid #e0e0e0; text-align: right; color: #1e40af; font-weight: 700; font-size: 0.95rem; white-space: nowrap;">
                                                    $${formatCurrency(proj.closing_liability || 0)}
                                                </td>
                                                <td style="padding: 10px; border: 1px solid #e0e0e0; text-align: right; color: #1e40af; font-weight: 700; font-size: 0.95rem; white-space: nowrap;">
                                                    $${formatCurrency(proj.closing_rou_asset || 0)}
                                                </td>
                                                <td style="padding: 10px; border: 1px solid #e0e0e0; text-align: right; color: #b91c1c; font-weight: 600; font-size: 0.95rem; white-space: nowrap;">
                                                    $${formatCurrency(proj.depreciation || 0)}
                                                </td>
                                                <td style="padding: 10px; border: 1px solid #e0e0e0; text-align: right; color: #b91c1c; font-weight: 600; font-size: 0.95rem; white-space: nowrap;">
                                                    $${formatCurrency(proj.interest || 0)}
                                                </td>
                                                <td style="padding: 10px; border: 1px solid #e0e0e0; text-align: right; color: #047857; font-weight: 700; font-size: 0.95rem; white-space: nowrap;">
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

            // Display schedule with ALL columns including Principal and Remaining Balance
            const scheduleBody = document.getElementById('scheduleBody');
            scheduleBody.innerHTML = result.schedule.map((row, idx) => {
                const bgColor = idx % 2 === 0 ? '#f8f9fa' : '#ffffff';
                // Highlight opening/closing rows
                const rowStyle = idx === 0 ? 'background-color: #e3f2fd; font-weight: 500;' : 
                                idx === result.schedule.length - 1 ? 'background-color: #fff3e0; font-weight: 500;' : 
                                `background-color: ${bgColor};`;
                
                return `
                <tr style="${rowStyle}">
                    <td style="padding: 8px; border: 1px solid #ddd;">${formatDate(row.date)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(row.rental_amount || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(row.principal || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${(row.pv_factor || 0).toFixed(6)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(row.interest || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right; font-weight: ${idx === 0 || idx === result.schedule.length - 1 ? '600' : '400'};">
                        $${formatCurrency(row.lease_liability || 0)}
                    </td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${row.remaining_balance !== null && row.remaining_balance !== undefined ? '$' + formatCurrency(row.remaining_balance) : '-'}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(row.pv_of_rent || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right; font-weight: ${idx === 0 || idx === result.schedule.length - 1 ? '600' : '400'};">
                        $${formatCurrency(row.rou_asset || 0)}
                    </td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(row.depreciation || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(row.change_in_rou || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(row.security_deposit_pv || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${row.aro_gross !== null && row.aro_gross !== undefined ? '$' + formatCurrency(row.aro_gross) : '-'}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${row.aro_interest !== null && row.aro_interest !== undefined ? '$' + formatCurrency(row.aro_interest) : '-'}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">${row.aro_provision !== null && row.aro_provision !== undefined ? '$' + formatCurrency(row.aro_provision) : '-'}</td>
                </tr>
            `;
            }).join('');

            // Display journal entries with Opening Balance and IFRS/US-GAAP columns
            const journalBody = document.getElementById('journalBody');
            journalBody.innerHTML = result.journal_entries.map((entry, idx) => {
                // Check if entry has opening_balance field (new feature)
                const openingBal = entry.opening_balance !== undefined ? entry.opening_balance : entry.previous_period;
                const ifrsAdj = entry.ifrs_adjustment !== undefined ? entry.ifrs_adjustment : (entry.result_period || 0);
                const usgaapEntry = entry.usgaap_entry !== undefined ? entry.usgaap_entry : 0;
                const bgColor = idx % 2 === 0 ? '#f8f9fa' : '#ffffff';
                return `
                <tr style="background-color: ${bgColor};">
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: 500;">${entry.account_code || '-'}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: left;">${entry.account_name || ''}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: 500;">${entry.bs_pl || ''}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(openingBal || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(entry.previous_period || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(entry.result_period || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right; font-weight: 500;">$${formatCurrency(entry.incremental_adjustment || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(ifrsAdj || 0)}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: right;">$${formatCurrency(usgaapEntry || 0)}</td>
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
                if (detailsDiv.style.display === 'none') {
                    detailsDiv.style.display = 'block';
                    toggleBtn.textContent = 'Hide Details';
                    toggleBtn.style.background = '#dc2626';
                } else {
                    detailsDiv.style.display = 'none';
                    toggleBtn.textContent = 'Show Details';
                    toggleBtn.style.background = '#667eea';
                }
            }
        }
        
        // Toggle function for opening balances details
        function toggleOpeningBalances() {
            const detailsDiv = document.getElementById('openingBalancesDetails');
            const toggleBtn = document.getElementById('openingBalancesToggle');
            
            if (detailsDiv && toggleBtn) {
                if (detailsDiv.style.display === 'none') {
                    detailsDiv.style.display = 'block';
                    toggleBtn.textContent = 'Hide Details';
                    toggleBtn.style.background = '#dc2626';
                } else {
                    detailsDiv.style.display = 'none';
                    toggleBtn.textContent = 'Show Details';
                    toggleBtn.style.background = '#667eea';
                }
            }
        }
        // This ensures the heading and table always appear together when projections exist

        function formatCurrency(value) {
            return Math.abs(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        }

        function formatDate(dateStr) {
            if (!dateStr) return '-';
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
        }

        function showError(message) {
            const errorDiv = document.getElementById('errorMessage');
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
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
            
            alert('✅ Enhanced Excel report downloaded!\n\nFile: ' + filename + '\n\nContains:\n• Professional summary with metadata\n• Amortization schedule\n• Journal entries\n• Timestamped filename');
        }

        async function logout() {
            try {
                await fetch('http://localhost:5001/api/logout', {
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
            fetch('http://localhost:5001/api/user', {
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
                alert('❌ Please enter a valid recipient email');
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
                    alert('✅ Report sent to ' + toEmail + '!');
                } else {
                    alert('❌ Failed to send: ' + (result.error || 'Unknown error'));
                }
            } catch (error) {
                alert('❌ Error sending email: ' + error.message);
            }
        }
    </script>
