document.addEventListener('DOMContentLoaded', async function() {
    if (!await requireAuth()) { return; }
    updateUsername();
    loadUsers();
    loadConfig();
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
    tbody.innerHTML = (js.users || []).map(u => {
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
