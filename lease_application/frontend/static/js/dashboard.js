/**
 * Dashboard JavaScript
 */

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

// Create Lease - Navigate to form
function createLease() {
    window.location.href = '/lease_form.html';
}

// Calculate Lease - Navigate to calculate page
function calculateLease(leaseId) {
    window.location.href = `/calculate.html?lease_id=${leaseId}`;
}

// Edit Lease - Navigate to form with lease ID
function editLease(leaseId) {
    window.location.href = `/lease_form.html?id=${leaseId}`;
}

// Delete Lease
async function deleteLease(leaseId) {
    if (!confirm('Are you sure you want to delete this lease?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/leases/${leaseId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        const result = await response.json();
        if (result.success) {
            alert('Lease deleted successfully!');
            loadLeases();
        } else {
            alert('Error deleting lease');
        }
    } catch (error) {
        console.error('Error deleting lease:', error);
        alert('Error deleting lease. Please try again.');
    }
}

// Load and display leases
async function loadLeases() {
    try {
        const response = await fetch('/api/leases', {
            method: 'GET',
            credentials: 'include'
        });
        
        const result = await response.json();
        const tbody = document.getElementById('leasesTableBody');
        
        if (!result.success || !result.leases || result.leases.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align: center; padding: 40px; color: #999;">
                        No leases found. <button class="btn-link" onclick="createLease()">Create your first lease</button>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = result.leases.map(lease => {
            const startDate = lease.lease_start_date ? new Date(lease.lease_start_date).toLocaleDateString() : 'N/A';
            const endDate = lease.lease_end_date ? new Date(lease.lease_end_date).toLocaleDateString() : 'N/A';
            const status = lease.status || 'draft';
            
            return `
                <tr>
                    <td>${lease.lease_id}</td>
                    <td>${lease.agreement_title || 'N/A'}</td>
                    <td>${lease.company_name || 'N/A'}</td>
                    <td>${lease.asset_class || 'N/A'}</td>
                    <td>${startDate}</td>
                    <td>${endDate}</td>
                    <td><span class="status-badge ${status}">${status.charAt(0).toUpperCase() + status.slice(1)}</span></td>
                    <td>
                        <a href="#" class="action-link" onclick="editLease(${lease.lease_id}); return false;">Edit</a>
                        <span style="margin: 0 8px;">|</span>
                        <a href="#" class="action-link" onclick="calculateLease(${lease.lease_id}); return false;">Calculate</a>
                        <span style="margin: 0 8px;">|</span>
                        <a href="#" class="action-link delete-link" onclick="deleteLease(${lease.lease_id}); return false;">Delete</a>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error('Error loading leases:', error);
        const tbody = document.getElementById('leasesTableBody');
        tbody.innerHTML = `
            <tr>
                <td colspan="8" style="text-align: center; padding: 40px; color: #e74c3c;">
                    Error loading leases. Please refresh the page.
                </td>
            </tr>
        `;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    updateUsername();
    loadLeases();
});

