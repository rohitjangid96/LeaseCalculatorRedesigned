document.addEventListener('DOMContentLoaded', loadAuditLogs);

const auditLogsUrl = '/api/audit_logs';

/**
 * Step 1: Groups flat audit logs into transactions based on time, user, and action.
 */
function groupLogsByTransaction(logs) {
    const grouped = [];
    if (!logs || logs.length === 0) return grouped;

    let currentGroup = null;

    // Logs should be sorted descending by timestamp from the API for this logic to work
    for (const log of logs) {
        // Use a composite key for grouping
        const groupKey = `${log.change_timestamp}-${log.lease_id}-${log.changed_by_username}-${log.action}`;

        // If the key is new, start a new group
        if (!currentGroup || currentGroup.key !== groupKey) {
            currentGroup = {
                key: groupKey,
                timestamp: log.change_timestamp,
                lease_id: log.lease_id,
                user: log.changed_by_username,
                action: log.action,
                changes: [],
            };
            grouped.push(currentGroup);
        }

        currentGroup.changes.push({
            field_name: log.field_name,
            old_value: log.old_value,
            new_value: log.new_value,
        });
    }

    return grouped;
}

/**
 * Step 2: Renders the consolidated table rows and sets up event listeners.
 */
function renderConsolidatedTable(groupedLogs) {
    const tbody = document.getElementById('auditTableBody');
    tbody.innerHTML = ''; // Clear existing rows
    const noLogsMessage = document.getElementById('noLogsMessage');

    if (groupedLogs.length === 0) {
        noLogsMessage.style.display = 'block';
        return;
    }
    noLogsMessage.style.display = 'none';

    groupedLogs.forEach((group, index) => {
        // Main Summary Row
        const summaryRow = tbody.insertRow();
        summaryRow.className = 'audit-table-summary';
        summaryRow.dataset.groupId = index;
        summaryRow.onclick = () => toggleDetails(index);

        summaryRow.innerHTML = `
            <td>${group.timestamp}</td>
            <td>${group.lease_id}</td>
            <td>${group.user}</td>
            <td><span class="status-badge ${group.action}">${group.action}</span></td>
            <td>${group.changes.length} field${group.changes.length === 1 ? '' : 's'} modified</td>
            <td><i class="fas fa-caret-down toggle-icon" id="toggle-${index}"></i></td>
        `;

        // Detail Row (initially hidden)
        const detailRow = tbody.insertRow();
        detailRow.style.display = 'none';
        detailRow.className = 'audit-detail-row';
        detailRow.dataset.detailId = index;
        
        const detailCell = detailRow.insertCell(0);
        detailCell.colSpan = 6;
        detailCell.innerHTML = renderDetailTable(group.changes);
    });
}

/**
 * Step 3: Renders the detailed table for a single transaction.
 */
function renderDetailTable(changes) {
    let html = '<table class="audit-detail-table"><thead><tr><th style="width: 25%;">Field Name</th><th style="width: 75%;">Change (Old → New)</th></tr></thead><tbody>';

    changes.forEach(change => {
        const oldValue = formatValue(change.old_value);
        const newValue = formatValue(change.new_value);
        
        // Use a simplified diff display (Old Value | New Value)
        html += `
            <tr>
                <td class="field-name-col">${change.field_name.replace(/_/g, ' ')}</td>
                <td>
                    <span class="old-value">${oldValue}</span>
                    <i class="fas fa-arrow-right" style="margin-right: 10px; color: #aaa;"></i>
                    <span class="new-value">${newValue}</span>
                </td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    return html;
}

/**
 * Helper: Formats string values, truncating long JSON.
 */
function formatValue(value) {
    if (value === null || value === undefined) return '';
    let strValue = String(value);

    // Check if it's a long JSON string (e.g., rental_schedule)
    if ((strValue.startsWith('[') || strValue.startsWith('{')) && strValue.length > 100) {
        return strValue.substring(0, 75) + '... (JSON)';
    }

    // Truncate other long strings for readability
    if (strValue.length > 80) {
        return strValue.substring(0, 75) + '...';
    }

    return strValue;
}

/**
 * Step 4: Toggle function for expanding/collapsing details.
 */
function toggleDetails(index) {
    const detailRow = document.querySelector(`[data-detail-id="${index}"]`);
    const toggleIcon = document.getElementById(`toggle-${index}`);
    
    if (detailRow.style.display === 'none') {
        detailRow.style.display = 'table-row';
        toggleIcon.classList.replace('fa-caret-down', 'fa-caret-up');
    } else {
        detailRow.style.display = 'none';
        toggleIcon.classList.replace('fa-caret-up', 'fa-caret-down');
    }
}

/**
 * Main loading function.
 */
async function loadAuditLogs() {
    try {
        const response = await fetch(auditLogsUrl, { credentials: 'include' });
        const data = await response.json();

        if (data.success && data.logs) {
            const groupedLogs = groupLogsByTransaction(data.logs);
            renderConsolidatedTable(groupedLogs);
            // Setup search listener after rendering
            setupSearchListener(groupedLogs);
        } else {
            console.error('Failed to load audit logs:', data.error);
            document.getElementById('noLogsMessage').style.display = 'block';
        }
    } catch (error) {
        console.error('Error fetching audit logs:', error);
        document.getElementById('noLogsMessage').innerHTML = 'Error loading logs.';
        document.getElementById('noLogsMessage').style.display = 'block';
    }
}


/**
 * Setup Search Listener
 */
function setupSearchListener(groupedLogs) {
    const searchInput = document.getElementById('auditSearchInput');
    if (!searchInput) return;

    searchInput.addEventListener('keyup', function() {
        const filter = this.value.toUpperCase();
        const tbody = document.getElementById('auditTableBody');
        const rows = Array.from(tbody.children).filter(row => row.className === 'audit-table-summary');
        
        rows.forEach(row => {
            // Get text content from Lease ID and User columns
            const leaseId = row.cells[1].textContent.toUpperCase();
            const user = row.cells[2].textContent.toUpperCase();
            
            if (leaseId.indexOf(filter) > -1 || user.indexOf(filter) > -1) {
                row.style.display = '';
                // Ensure detail rows stay hidden or visible based on the summary row state (optional for simplicity)
            } else {
                row.style.display = 'none';
                // Hide the corresponding detail row too
                const detailRow = document.querySelector(`[data-detail-id="${row.dataset.groupId}"]`);
                if (detailRow) detailRow.style.display = 'none';
            }
        });
    });
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

    emailSubject.value = 'Audit Log Report';
    emailBody.value = 'Please find the attached audit log report.';
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
                attachment_filename: 'Audit_Log_Report.xlsx'
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
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.json_to_sheet(
        Array.from(document.querySelectorAll('#auditTableBody tr.audit-table-summary')).map(row => {
            const cells = row.querySelectorAll('td');
            return {
                'Timestamp': cells[0].textContent,
                'Lease ID': cells[1].textContent,
                'User': cells[2].textContent,
                'Action': cells[3].textContent,
                'Summary': cells[4].textContent,
            };
        })
    );
    XLSX.utils.book_append_sheet(wb, ws, 'Audit Log');
    return wb;
}
