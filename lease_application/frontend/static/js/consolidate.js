// Consolidate Reports JavaScript
let allLeases = [];
let selectedLeaseIds = [];

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
    
    // Activate button - find by onclick attribute
    document.querySelectorAll('.nav-tab').forEach(btn => {
        if (btn.getAttribute('onclick') && btn.getAttribute('onclick').includes(tabName)) {
            btn.classList.add('active');
        }
    });
}

// Expose globally for onclick handlers
window.showTab = showTab;

// Load leases on page load
window.addEventListener('DOMContentLoaded', async () => {
    // Load user info
    try {
        const userResponse = await fetch('/api/user', {
            credentials: 'include'
        });
        
        let userData = {};
        try {
            userData = await userResponse.json();
        } catch (parseError) {
            console.error('Failed to parse user response:', parseError);
        }
        
        const usernameEl = document.getElementById('username');
        if (usernameEl) {
            if (userResponse.ok && userData.success && userData.user) {
                usernameEl.textContent = userData.user.username || 'Guest';
            } else if (userResponse.status === 401) {
                usernameEl.textContent = 'Guest';
            } else if (userData.username) {
                usernameEl.textContent = userData.username || 'Guest';
            } else {
                usernameEl.textContent = 'Guest';
            }
        }
    } catch (e) {
        console.error('Error loading user info:', e);
    }

    // Load leases
    await loadLeases();
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
        const selectDiv = document.getElementById('leaseSelection');
        
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
        
        allLeases = leases;
        console.log(`📋 Loaded ${leases.length} leases`);
        
        // Render lease checkboxes
        if (leases.length === 0) {
            selectDiv.innerHTML = '<div class="lease-selection-empty">No leases found. Please create leases first.</div>';
        } else {
            selectDiv.innerHTML = leases.map(lease => {
                const displayName = `${lease.lease_id} - ${lease.agreement_title || 'Untitled'}`;
                const companyInfo = lease.company_name ? ` (${lease.company_name})` : '';
                const assetInfo = lease.asset_class ? ` • ${lease.asset_class}` : '';
                return `
                    <div class="lease-checkbox-item">
                        <input type="checkbox" 
                               id="lease_${lease.lease_id}" 
                               value="${lease.lease_id}"
                               onchange="updateSelectedLeases()">
                        <label for="lease_${lease.lease_id}">
                            ${displayName}${companyInfo}${assetInfo}
                        </label>
                    </div>
                `;
            }).join('');
            
            // Initialize selected count
            updateSelectedLeases();
        }
    } catch (error) {
        console.error('Error loading leases:', error);
        const selectDiv = document.getElementById('leaseSelection');
        if (selectDiv) {
            selectDiv.innerHTML = `<p style="padding: 12px; color: #e74c3c;">Error loading leases: ${error.message}</p>`;
        }
        if (error.message.includes('401') || error.message.includes('Authentication')) {
            showError('Please login to view your leases. Redirecting to login...');
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 2000);
        }
    }
}

function updateSelectedLeases() {
    const checkboxes = document.querySelectorAll('#leaseSelection input[type="checkbox"]:checked');
    selectedLeaseIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    
    // Update selected count display
    const countElement = document.getElementById('selectedCount');
    if (countElement) {
        countElement.textContent = selectedLeaseIds.length;
    }
    
    console.log(`✅ Selected ${selectedLeaseIds.length} leases:`, selectedLeaseIds);
}

// Expose functions globally for onclick handlers
function selectAllLeases() {
    const checkboxes = document.querySelectorAll('#leaseSelection input[type="checkbox"]');
    checkboxes.forEach(cb => {
        if (!cb.disabled) {
            cb.checked = true;
        }
    });
    updateSelectedLeases();
}

function deselectAllLeases() {
    const checkboxes = document.querySelectorAll('#leaseSelection input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
    updateSelectedLeases();
}

// Make sure functions are accessible globally
window.selectAllLeases = selectAllLeases;
window.deselectAllLeases = deselectAllLeases;
window.consolidateLeases = consolidateLeases;

async function consolidateLeases() {
    // Get selected leases
    updateSelectedLeases();
    
    if (selectedLeaseIds.length === 0) {
        showError('Please select at least one lease');
        return;
    }
    
    // Get date range
    const fromDate = document.getElementById('fromDate').value;
    const toDate = document.getElementById('toDate').value;
    const gaapStandard = document.getElementById('gaapStandard').value;
    
    if (!fromDate || !toDate) {
        showError('Please select both From Date and To Date');
        return;
    }
    
    // Show loading
    document.getElementById('loading').style.display = 'block';
    document.getElementById('errorMessage').style.display = 'none';
    document.getElementById('results').style.display = 'none';
    
    try {
        const response = await fetch('/api/consolidate_reports', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'include',
            body: JSON.stringify({
                lease_ids: selectedLeaseIds,
                from_date: fromDate,
                to_date: toDate,
                gaap_standard: gaapStandard
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || `Server error: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.error) {
            throw new Error(result.error);
        }
        
        // Display results
        displayResults(result);
        
    } catch (error) {
        console.error('Consolidation error:', error);
        showError(`Error: ${error.message || 'Failed to generate consolidated report'}`);
    } finally {
        document.getElementById('loading').style.display = 'none';
    }
}

function displayResults(result) {
    // Display statistics
    const statisticsGrid = document.getElementById('statisticsGrid');
    if (result.statistics && statisticsGrid) {
        statisticsGrid.innerHTML = `
            <div class="statistics-item">
                <strong>Total Leases</strong>
                <span>${result.statistics.total_count || 0}</span>
            </div>
            <div class="statistics-item">
                <strong>Processed</strong>
                <span>${result.statistics.processed_count || 0}</span>
            </div>
            <div class="statistics-item">
                <strong>Skipped</strong>
                <span>${result.statistics.skipped_count || 0}</span>
            </div>
            <div class="statistics-item">
                <strong>Success Rate</strong>
                <span>${result.statistics.total_count > 0 
                    ? Math.round((result.statistics.processed_count / result.statistics.total_count) * 100) 
                    : 0}%</span>
            </div>
        `;
    }
    
    // Display Key Values
    displayKeyValues(result);
    
    // Create charts
    createCharts(result);
    
    // Note: Aggregated totals are now displayed in Key Values cards, no longer needed here
    
    // Display individual lease results
    const resultsBody = document.getElementById('resultsBody');
    if (!resultsBody) {
        console.error('resultsBody element not found');
        return;
    }
    
    if (result.results && Array.isArray(result.results)) {
        resultsBody.innerHTML = result.results.map((row, idx) => {
            const bgColor = idx % 2 === 0 ? '#fafafa' : '#ffffff';
            return `
                <tr style="background-color: ${bgColor};">
                    <td style="padding: 12px; border: 1px solid #e0e0e0; color: #2c3e50; font-weight: 500;">${row.lease_id || row.auto_id || '-'}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; color: #555;">${row.description || '-'}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; color: #555;">${row.asset_class || '-'}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.opening_liability || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.opening_rou_asset || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.interest_expense || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.depreciation_expense || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(row.rent_paid || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; font-weight: 500; color: #2c3e50;">$${formatCurrency(row.closing_liability_total || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; font-weight: 500; color: #2c3e50;">$${formatCurrency(row.closing_rou_asset || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: ${(row.gain_loss_pnl || 0) >= 0 ? '#27ae60' : '#e74c3c'}; font-weight: 500;">$${formatCurrency(row.gain_loss_pnl || 0)}</td>
                </tr>
            `;
        }).join('');
    } else {
        resultsBody.innerHTML = '<tr><td colspan="11" style="text-align: center; padding: 20px; color: #666;">No results available</td></tr>';
    }
    
    // Display consolidated journal entries
    const journalBody = document.getElementById('journalBody');
    if (!journalBody) {
        console.error('journalBody element not found');
        return;
    }
    
    if (result.consolidated_journals && Array.isArray(result.consolidated_journals)) {
        journalBody.innerHTML = result.consolidated_journals.map((entry, idx) => {
            const bgColor = idx % 2 === 0 ? '#fafafa' : '#ffffff';
            return `
                <tr style="background-color: ${bgColor};">
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: center; font-weight: 500; color: #2c3e50;">${entry.account_code || '-'}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: left; color: #555;">${entry.account_name || ''}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: center; font-weight: 500; color: #2c3e50;">${entry.bs_pl || ''}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(entry.opening_balance || entry.previous_period || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(entry.previous_period || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(entry.result_period || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; font-weight: 500; color: #2c3e50;">$${formatCurrency(entry.incremental_adjustment || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(entry.ifrs_adjustment || 0)}</td>
                    <td style="padding: 12px; border: 1px solid #e0e0e0; text-align: right; color: #555;">$${formatCurrency(entry.usgaap_entry || 0)}</td>
                </tr>
            `;
        }).join('');
    } else {
        journalBody.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 20px; color: #666;">No journal entries available</td></tr>';
    }
    
    // Show results
    document.getElementById('results').style.display = 'block';
    document.getElementById('actionButtons').style.display = 'flex';
}

function displayKeyValues(result) {
    const keyValuesGrid = document.getElementById('keyValuesGrid');
    if (!keyValuesGrid || !result.aggregated_totals) return;
    
    const totals = result.aggregated_totals;
    
    // Set default "As of" date
    const asOfDateInput = document.getElementById('asOfDate');
    if (asOfDateInput && !asOfDateInput.value) {
        const toDate = document.getElementById('toDate').value || new Date().toISOString().split('T')[0];
        asOfDateInput.value = toDate;
    }
    
    // Calculate total interest incurred (sum of all individual leases' interest)
    const totalInterestIncurred = result.results ? 
        result.results.reduce((sum, row) => sum + (row.interest_expense || 0), 0) : 
        (totals.total_interest_expense || 0);
    
    // Calculate total amortization incurred
    const totalAmortizationIncurred = totals.total_depreciation_expense || 0;
    
    // Forecasted values (can be calculated from projections if available)
    const forecastedInterest = totals.total_interest_expense || 0;
    const forecastedAmortization = totals.total_depreciation_expense || 0;
    
    keyValuesGrid.innerHTML = `
        <div class="key-value-card">
            <div class="key-value-icon rou">ROU</div>
            <div class="key-value-content">
                <div class="key-value-label">ROU Asset value</div>
                <div class="key-value-amount">USD ${formatCurrency(totals.total_closing_rou_asset || 0)}</div>
            </div>
        </div>
        <div class="key-value-card">
            <div class="key-value-icon liability">LL</div>
            <div class="key-value-content">
                <div class="key-value-label">Lease Liability</div>
                <div class="key-value-amount">USD ${formatCurrency(totals.total_closing_liability || 0)}</div>
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
                <div class="key-value-amount">USD ${formatCurrency(totals.total_closing_aro_liability || 0)}</div>
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

// Expose globally
function updateKeyValues() {
    // This can be called when "As of" date changes to recalculate values
    // For now, we'll just reload if needed
}
window.updateKeyValues = updateKeyValues;

function createCharts(result) {
    // Destroy existing charts if they exist
    if (npvChart) npvChart.destroy();
    if (liabilityAssetChart) liabilityAssetChart.destroy();
    if (interestDepreciationChart) interestDepreciationChart.destroy();
    
    // For consolidated charts, we'll aggregate data across all leases
    // Create a timeline based on date range
    const fromDate = document.getElementById('fromDate').value;
    const toDate = document.getElementById('toDate').value;
    
    if (!fromDate || !toDate) return;
    
    // Generate date labels (monthly intervals)
    const dates = generateDateLabels(fromDate, toDate);
    
    // Aggregate data by date from individual results
    // For now, we'll use aggregated totals for the main chart
    const totals = result.aggregated_totals || {};
    
    // Prepare chart data - using aggregated totals
    const liabilities = dates.map(() => totals.total_closing_liability || 0);
    const rouAssets = dates.map(() => totals.total_closing_rou_asset || 0);
    const interests = dates.map(() => totals.total_interest_expense || 0);
    const depreciations = dates.map(() => totals.total_depreciation_expense || 0);
    
    // Net Present Value Chart (Bar Chart) - Consolidated view
    const npvCtx = document.getElementById('npvChart');
    if (npvCtx) {
        npvChart = new Chart(npvCtx, {
            type: 'bar',
            data: {
                labels: dates,
                datasets: [
                    {
                        label: 'Total Lease Liability',
                        data: liabilities,
                        backgroundColor: 'rgba(231, 76, 60, 0.6)',
                        borderColor: 'rgba(231, 76, 60, 1)',
                        borderWidth: 1
                    },
                    {
                        label: 'Total ROU Asset',
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
                        label: 'Total Lease Liability',
                        data: liabilities,
                        borderColor: 'rgba(231, 76, 60, 1)',
                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Total ROU Asset',
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
                        label: 'Total Interest',
                        data: interests,
                        borderColor: 'rgba(52, 152, 219, 1)',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Total Depreciation',
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

function generateDateLabels(fromDate, toDate) {
    const dates = [];
    const start = new Date(fromDate);
    const end = new Date(toDate);
    const current = new Date(start);
    
    while (current <= end) {
        dates.push(current.toLocaleDateString('en-US', { year: '2-digit', month: '2-digit', day: '2-digit' }));
        // Increment by month
        current.setMonth(current.getMonth() + 1);
    }
    
    // Limit to reasonable number of labels (max 24 months)
    if (dates.length > 24) {
        return dates.filter((_, idx) => idx % Math.ceil(dates.length / 24) === 0);
    }
    
    return dates;
}

function formatCurrency(value) {
    return Math.abs(value || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
}

// Expose globally
function exportToExcel() {
    const today = new Date();
    
    // Get data from displayed tables
    const resultsData = Array.from(document.querySelectorAll('#resultsBody tr')).map(row => {
        const cells = row.querySelectorAll('td');
        return {
            'Lease ID': cells[0]?.textContent || '',
            'Description': cells[1]?.textContent || '',
            'Asset Class': cells[2]?.textContent || '',
            'Opening Liability': cells[3]?.textContent || '',
            'Opening ROU Asset': cells[4]?.textContent || '',
            'Interest Expense': cells[5]?.textContent || '',
            'Depreciation': cells[6]?.textContent || '',
            'Rent Paid': cells[7]?.textContent || '',
            'Closing Liability Total': cells[8]?.textContent || '',
            'Closing ROU Asset': cells[9]?.textContent || '',
            'Gain/(Loss) P&L': cells[10]?.textContent || ''
        };
    });

    const journalData = Array.from(document.querySelectorAll('#journalBody tr')).map(row => {
        const cells = row.querySelectorAll('td');
        return {
            'Account Code': cells[0]?.textContent || '',
            'Account Name': cells[1]?.textContent || '',
            'BS/PL': cells[2]?.textContent || '',
            'Opening Balance': cells[3]?.textContent || '',
            'Previous Period': cells[4]?.textContent || '',
            'Result Period': cells[5]?.textContent || '',
            'Incremental': cells[6]?.textContent || '',
            'IFRS Adjustment': cells[7]?.textContent || '',
            'US-GAAP': cells[8]?.textContent || ''
        };
    });
    
    // Get aggregated totals
    const totalsData = {};
    document.querySelectorAll('#aggregatedTotalsGrid .summary-item').forEach(item => {
        const strong = item.querySelector('strong');
        const span = item.querySelector('span');
        if (strong && span) {
            totalsData[strong.textContent.trim()] = span.textContent.trim();
        }
    });
    
    // Create workbook
    const wb = XLSX.utils.book_new();
    
    // 1. Aggregated Totals Sheet
    const totalsSheetData = [
        ['CONSOLIDATED LEASE REPORT'],
        [],
        ['Report Information'],
        ['Generated Date', today.toLocaleDateString() + ' ' + today.toLocaleTimeString()],
        [],
        ['Aggregated Totals'],
        ...Object.entries(totalsData).map(([label, value]) => [label, value]),
    ];
    const wsTotals = XLSX.utils.aoa_to_sheet(totalsSheetData);
    wsTotals['!cols'] = [{ wch: 30 }, { wch: 22 }];
    XLSX.utils.book_append_sheet(wb, wsTotals, 'Aggregated Totals');
    
    // 2. Individual Results Sheet
    const wsResults = XLSX.utils.json_to_sheet(resultsData);
    wsResults['!cols'] = [
        { wch: 10 }, { wch: 30 }, { wch: 15 }, { wch: 18 }, { wch: 18 },
        { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 22 }, { wch: 18 }, { wch: 15 }
    ];
    XLSX.utils.book_append_sheet(wb, wsResults, 'Individual Results');
    
    // 3. Consolidated Journal Entries Sheet
    const wsJournal = XLSX.utils.json_to_sheet(journalData);
    wsJournal['!cols'] = [{ wch: 12 }, { wch: 35 }, { wch: 8 }, { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 18 }, { wch: 18 }];
    XLSX.utils.book_append_sheet(wb, wsJournal, 'Consolidated Journals');

    // Download with timestamp
    const timestamp = today.toISOString().split('T')[0].replace(/-/g, '');
    const filename = `Consolidated_Report_${timestamp}.xlsx`;
    XLSX.writeFile(wb, filename);
    
    alert('✅ Consolidated Excel report downloaded!\n\nFile: ' + filename + '\n\nContains:\n• Aggregated totals\n• Individual lease results\n• Consolidated journal entries\n• Timestamped filename');
}

// Expose globally
window.exportToExcel = exportToExcel;

