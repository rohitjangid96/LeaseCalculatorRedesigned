/**
 * Dashboard JavaScript - Modern UI
 */

document.addEventListener('DOMContentLoaded', async function() {
    if (!await requireAuth()) { return; }
    updateUsername();
    loadLeases();
    loadStats();
    setupSidebar();
});

// Update username display
async function updateUsername() {
    try {
        const user = await getCurrentUser();
        if (user) {
            const usernameEl = document.getElementById('username');
            if (usernameEl) {
                usernameEl.textContent = user.username || 'User';
            }
        }
    } catch (error) {
        console.error('Error fetching user:', error);
    }
}

// Logout


// Navigation
function editLease(leaseId) {
    window.location.href = `/lease_form.html?id=${leaseId}`;
}

function calculateLease(leaseId) {
    window.location.href = `/calculate.html?lease_id=${leaseId}`;
}

// API Calls
async function deleteLease(leaseId) {
    if (!confirm('Are you sure you want to delete this lease?')) return;
    
    try {
        const response = await fetch(`/api/leases/${leaseId}`, { method: 'DELETE', credentials: 'include' });
        const result = await response.json();
        if (result.success) {
            showToast('Lease deleted successfully!');
            loadLeases();
            loadStats();
        } else {
            showToast(result.error || 'Error deleting lease', 'error');
        }
    } catch (error) {
        console.error('Error deleting lease:', error);
        showToast('An error occurred. Please try again.', 'error');
    }
}

async function copyLease(leaseId) {
    if (!confirm('Are you sure you want to copy this lease?')) return;

    try {
        const response = await fetch(`/api/leases/${leaseId}/copy`, { method: 'POST', credentials: 'include' });
        const result = await response.json();
        if (result.success) {
            showToast('Lease copied successfully!');
            loadLeases();
        } else {
            showToast(result.error || 'Error copying lease', 'error');
        }
    } catch (error) {
        console.error('Error copying lease:', error);
        showToast('An error occurred. Please try again.', 'error');
    }
}

// Data Loading
async function loadLeases() {
    const tbody = document.getElementById('leasesTableBody');
    const noLeasesMessage = document.getElementById('noLeasesMessage');
    const leasesTable = document.querySelector('.leases-table');

    if (!tbody || !noLeasesMessage || !leasesTable) {
        return; // Elements not found, do nothing
    }

    try {
        const response = await fetch('/api/leases', { credentials: 'include' });
        const result = await response.json();

        if (!result.success || !result.leases || result.leases.length === 0) {
            tbody.innerHTML = '';
            leasesTable.style.display = 'none';
            noLeasesMessage.style.display = 'block';
            return;
        }

        leasesTable.style.display = 'table';
        noLeasesMessage.style.display = 'none';
        
        const user = await getCurrentUser();
        const isReviewer = user && (user.role === 'admin' || user.role === 'reviewer');

        tbody.innerHTML = result.leases.map(lease => {
            const startDate = lease.lease_start_date ? new Date(lease.lease_start_date).toLocaleDateString() : 'N/A';
            const endDate = lease.lease_end_date ? new Date(lease.lease_end_date).toLocaleDateString() : 'N/A';
            const status = lease.status || 'draft';
            const canCalculate = status === 'approved';
            const isRejected = status === 'rejected';
            const isApproved = status === 'approved';
            const rejectionReason = lease.rejection_reason || '';
            const approvalComment = lease.approval_comment || '';

            let rowHtml = `
                <tr class="${isRejected ? 'lease-rejected' : ''} ${isApproved ? 'lease-approved' : ''}">
                    <td>${lease.lease_id}</td>
                    <td>${lease.agreement_title || 'N/A'}</td>
                    <td>${lease.company_name || 'N/A'}</td>
                    <td>${lease.asset_class || 'N/A'}</td>
                    <td>${startDate}</td>
                    <td>${endDate}</td>
                    <td><span class="status-badge ${status}">${status}</span></td>
                    <td>
                        <a href="#" class="action-link" onclick="editLease(${lease.lease_id})"><i class="fas fa-edit"></i></a>
                        <a href="#" class="action-link" onclick="copyLease(${lease.lease_id})"><i class="fas fa-copy"></i></a>
                        ${canCalculate ? `<a href="#" class="action-link" onclick="calculateLease(${lease.lease_id})"><i class="fas fa-calculator"></i></a>` : ''}
                        <a href="#" class="action-link delete-link" onclick="deleteLease(${lease.lease_id})"><i class="fas fa-trash"></i></a>
                    </td>
                </tr>
            `;

            if (isRejected && rejectionReason) {
                rowHtml += `
                    <tr class="rejection-reason-row">
                        <td colspan="8">
                            <div class="rejection-reason">
                                <strong>Rejection Reason:</strong> ${rejectionReason}
                            </div>
                        </td>
                    </tr>
                `;
            }

            if (isApproved && approvalComment) {
                rowHtml += `
                    <tr class="approval-comment-row">
                        <td colspan="8">
                            <div class="approval-comment">
                                <strong>Approval Comment:</strong> ${approvalComment}
                            </div>
                        </td>
                    </tr>
                `;
            }

            return rowHtml;
        }).join('');
    } catch (error) {
        console.error('Error loading leases:', error);
        document.getElementById('noLeasesMessage').textContent = 'Error loading leases.';
        document.getElementById('noLeasesMessage').style.display = 'block';
        document.querySelector('.leases-table').style.display = 'none';
    }
}

async function loadStats() {
    const statsTotal = document.getElementById('statsTotal');
    if (!statsTotal) {
        return; // Element not found, do nothing
    }

    try {
        const response = await fetch('/api/leases/stats', { credentials: 'include' });
        const result = await response.json();
        if (!result.success) return;

        statsTotal.textContent = result.total || 0;
        document.getElementById('statsActive').textContent = result.active || 0;
        document.getElementById('statsExpired').textContent = result.expired || 0;
        document.getElementById('statsSubmitted').textContent = (result.counts && result.counts.submitted) || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}


// Utility for showing toast messages (optional, can be expanded)
function showToast(message, type = 'success') {
    // A simple alert for now, can be replaced with a proper toast component
    showModal(type === 'success' ? 'Success' : 'Error', message);
}

async function setupSidebar() {
    try {
        const user = await getCurrentUser();
        if (user && user.role === 'admin') {
            const adminLink = document.getElementById('admin-link');
            if (adminLink) {
                adminLink.style.display = 'block';
            }
        }
    } catch (error) {
        console.error('Error setting up sidebar:', error);
    }
}
