document.addEventListener('DOMContentLoaded', async function() {
    if (!await requireAuth()) { return; }
    updateUsername();
    loadUsers();
    loadConfig();
    loadNotificationSettings();
    setupSidebar();

    // Initialize tabs after all content is loaded, but only if needed
    setTimeout(() => {
        if (typeof initializeTabs === 'function') {
            // Check if tabs are already properly initialized
            const activeTabContents = document.querySelectorAll('.admin-tab-content.active');
            const activeTabButtons = document.querySelectorAll('.admin-tab.active');

            if (activeTabContents.length === 0 || activeTabButtons.length === 0) {
                console.log('Tabs not properly initialized, calling initializeTabs');
                initializeTabs();
            } else {
                console.log('Tabs already properly initialized');
            }
        }
    }, 100);
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

function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('collapsed');
}

async function logout() {
    try {
        const r = await fetch('/api/logout', { method: 'POST', credentials: 'include' });
        const d = await r.json();
        if (d.success) location.href = '/login.html';
    } catch (e) {
        location.href = '/login.html';
    }
}

async function loadUsers() {
    const res = await fetch('/api/users', { credentials: 'include' });
    const js = await res.json();
    const tbody = document.getElementById('usersTableBody');
    if (!js.success) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#e74c3c;padding:24px;">Failed to load</td></tr>';
        return
    }

    const users = js.users || [];

    // Update statistics
    document.getElementById('totalUsers').textContent = users.length;
    document.getElementById('activeUsers').textContent = users.filter(u => u.is_active).length;
    document.getElementById('adminUsers').textContent = users.filter(u => u.role === 'admin').length;

    tbody.innerHTML = users.map(u => {
        const badge = u.is_active ? '<span class="status-badge approved">Active</span>' : '<span class="status-badge rejected">Inactive</span>';
        return `<tr>
            <td>${u.user_id}</td>
            <td>${u.username}</td>
            <td>${u.email || '-'}</td>
            <td>
                <select onchange="setRole(${u.user_id}, this.value)">
                    <option value="user" ${u.role === 'user' ? 'selected' : ''}>User</option>
                    <option value="reviewer" ${u.role === 'reviewer' ? 'selected' : ''}>Reviewer</option>
                    <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Admin</option>
                </select>
            </td>
            <td>${badge}</td>
            <td>
                <a href="#" class="action-link" onclick="setActive(${u.user_id}, ${u.is_active ? 'false' : 'true'}); return false;">${u.is_active ? 'Deactivate' : 'Activate'}</a>
            </td>
        </tr>`;
    }).join('');
}

async function setRole(id, role) {
    await fetch(`/api/users/${id}/role`, { method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ role }) });
}

async function setActive(id, isActive) {
    await fetch(`/api/users/${id}/active`, { method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_active: isActive }) });
    loadUsers();
}

async function loadConfig() {
    const r = await fetch('/api/admin/config', { credentials: 'include' });
    const j = await r.json();
    if (!j.success) { showModal('Error', j.error || 'Failed to load config'); return; }
    const c = j.config || {};
    document.getElementById('cfg_smtp_host').value = c.SMTP_HOST || '';
    document.getElementById('cfg_smtp_port').value = c.SMTP_PORT || '';
    document.getElementById('cfg_smtp_user').value = c.SMTP_USERNAME || '';
    document.getElementById('cfg_smtp_from').value = c.SMTP_FROM || '';
    document.getElementById('cfg_smtp_pass').value = '';
    document.getElementById('cfg_gemini_key').value = '';
}

async function saveConfig() {
    const body = {
        SMTP_HOST: document.getElementById('cfg_smtp_host').value,
        SMTP_PORT: document.getElementById('cfg_smtp_port').value,
        SMTP_USERNAME: document.getElementById('cfg_smtp_user').value,
        SMTP_FROM: document.getElementById('cfg_smtp_from').value,
        SMTP_PASSWORD: document.getElementById('cfg_smtp_pass').value,
        GEMINI_API_KEY: document.getElementById('cfg_gemini_key').value
    };
    const r = await fetch('/api/admin/config', { method: 'PUT', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json();
    if (!j.success) { showModal('Error', j.error || 'Failed to save config'); return; }
    showModal('Success', 'Saved');
    loadConfig();
}

// ============ NOTIFICATION SETTINGS ============
async function loadNotificationSettings() {
    const res = await fetch('/api/notifications/settings', { credentials: 'include' });
    const js = await res.json();
    const tbody = document.getElementById('notificationSettingsTableBody');
    if (!js.success) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#e74c3c;padding:24px;">Failed to load</td></tr>';
        return;
    }

    const settings = js.settings || [];

    // Update statistics
    document.getElementById('totalRules').textContent = settings.length;
    document.getElementById('activeRules').textContent = settings.filter(s => s.is_active).length;

    tbody.innerHTML = settings.map(s => {
        const statusBadge = s.is_active ? '<span class="status-badge approved">Active</span>' : '<span class="status-badge rejected">Inactive</span>';
        const triggerDisplay = s.trigger_field === 'lease_end_date' ? 'Lease Expiration' : 'Termination Date';
        const recipientDisplay = s.recipient_role === 'user' ? 'Users' : s.recipient_role === 'reviewer' ? 'Reviewers' : 'Admins';
        const messagePreview = s.message_template.length > 50 ? s.message_template.substring(0, 50) + '...' : s.message_template;

        return `<tr>
            <td>${s.rule_id}</td>
            <td>${triggerDisplay}</td>
            <td>${s.days_in_advance} days</td>
            <td>${recipientDisplay}</td>
            <td title="${s.message_template}">${messagePreview}</td>
            <td>${statusBadge}</td>
            <td>
                <a href="#" class="action-link" onclick="editNotificationSetting(${s.rule_id}); return false;">Edit</a> |
                <a href="#" class="action-link" onclick="deleteNotificationSetting(${s.rule_id}); return false;">Delete</a>
            </td>
        </tr>`;
    }).join('');
}

async function createNotificationSetting() {
    const triggerField = document.getElementById('ns_trigger_field').value;
    const daysAdvance = parseInt(document.getElementById('ns_days_advance').value);
    const recipientRole = document.getElementById('ns_recipient_role').value;
    const messageTemplate = document.getElementById('ns_message_template').value;

    if (!triggerField || !daysAdvance || !recipientRole || !messageTemplate) {
        showModal('Error', 'All fields are required');
        return;
    }

    const body = {
        trigger_field: triggerField,
        days_in_advance: daysAdvance,
        recipient_role: recipientRole,
        message_template: messageTemplate
    };

    const r = await fetch('/api/notifications/settings', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    const j = await r.json();
    if (!j.success) {
        showModal('Error', j.error || 'Failed to create notification setting');
        return;
    }
    showModal('Success', 'Notification setting created');
    loadNotificationSettings();
    clearNotificationForm();
}

async function editNotificationSetting(ruleId) {
    // Get the setting details
    const res = await fetch('/api/notifications/settings', { credentials: 'include' });
    const js = await res.json();
    if (!js.success) return;

    const setting = js.settings.find(s => s.rule_id === ruleId);
    if (!setting) return;

    // Populate form
    document.getElementById('ns_trigger_field').value = setting.trigger_field;
    document.getElementById('ns_days_advance').value = setting.days_in_advance;
    document.getElementById('ns_recipient_role').value = setting.recipient_role;
    document.getElementById('ns_message_template').value = setting.message_template;
    document.getElementById('ns_is_active').checked = setting.is_active;

    // Change button to update mode
    const btn = document.getElementById('ns_save_btn');
    btn.innerHTML = '<i class="fas fa-save"></i> Update Rule';
    btn.onclick = () => updateNotificationSetting(ruleId);

    // Switch to notifications tab if not already active
    switchTab('notifications');
}

async function updateNotificationSetting(ruleId) {
    const triggerField = document.getElementById('ns_trigger_field').value;
    const daysAdvance = parseInt(document.getElementById('ns_days_advance').value);
    const recipientRole = document.getElementById('ns_recipient_role').value;
    const messageTemplate = document.getElementById('ns_message_template').value;
    const isActive = document.getElementById('ns_is_active').checked;

    if (!triggerField || !daysAdvance || !recipientRole || !messageTemplate) {
        showModal('Error', 'All fields are required');
        return;
    }

    const body = {
        trigger_field: triggerField,
        days_in_advance: daysAdvance,
        recipient_role: recipientRole,
        message_template: messageTemplate,
        is_active: isActive
    };

    const r = await fetch(`/api/notifications/settings/${ruleId}`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    });
    const j = await r.json();
    if (!j.success) {
        showModal('Error', j.error || 'Failed to update notification setting');
        return;
    }
    showModal('Success', 'Notification setting updated');
    loadNotificationSettings();
    clearNotificationForm();
}

async function deleteNotificationSetting(ruleId) {
    if (!confirm('Are you sure you want to delete this notification setting?')) return;

    const r = await fetch(`/api/notifications/settings/${ruleId}`, {
        method: 'DELETE',
        credentials: 'include'
    });
    const j = await r.json();
    if (!j.success) {
        showModal('Error', j.error || 'Failed to delete notification setting');
        return;
    }
    showModal('Success', 'Notification setting deleted');
    loadNotificationSettings();
}

function clearNotificationForm() {
    document.getElementById('ns_trigger_field').value = 'lease_end_date';
    document.getElementById('ns_days_advance').value = '30';
    document.getElementById('ns_recipient_role').value = 'user';
    document.getElementById('ns_message_template').value = 'Lease {lease_id} expires in {days_in_advance} days. Please review and take necessary action.';
    document.getElementById('ns_is_active').checked = true;

    const btn = document.getElementById('ns_save_btn');
    btn.innerHTML = '<i class="fas fa-plus"></i> Create Rule';
    btn.onclick = createNotificationSetting;
}
