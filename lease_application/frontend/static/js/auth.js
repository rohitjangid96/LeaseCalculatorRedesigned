/**
 * Authentication Utilities
 * User session management and authentication helpers
 */

const API_BASE_URL = 'http://localhost:5001/api';

// Simple API helper
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const defaultOptions = {
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    };
    
    try {
        const response = await fetch(url, defaultOptions);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        return data;
    } catch (error) {
        console.error('Error checking auth status:', error);
        return false;
    }
}

function toggleUserMenu() {
    const userMenu = document.querySelector('.user-menu');
    if (userMenu) {
        userMenu.classList.toggle('active');
    }
}

function showModal(title, message) {
    let modal = document.getElementById('customModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'customModal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2 id="modalTitle"></h2>
                </div>
                <div class="modal-body">
                    <p id="modalMessage"></p>
                </div>
                <div class="modal-footer">
                    <button class="btn-primary" id="modalCloseBtn">Close</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        document.getElementById('modalCloseBtn').onclick = () => {
            modal.style.display = 'none';
        };
        window.onclick = (event) => {
            if (event.target == modal) {
                modal.style.display = 'none';
            }
        };
    }

    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalMessage').textContent = message;
    modal.style.display = 'block';
}

async function logout(event) {
    if (event) {
        event.stopPropagation();
    }
    try {
        const response = await fetch('/api/logout', { method: 'POST', credentials: 'include' });
        if (response.ok) {
            window.location.href = '/login.html';
        }
    } catch (error) {
        console.error('Logout failed:', error);
        window.location.href = '/login.html';
    }
}

// Auth API
const AuthAPI = {
    async login(username, password) {
        return apiRequest('/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
    },
    
    async register(username, email, password) {
        return apiRequest('/register', {
            method: 'POST',
            body: JSON.stringify({ username, email, password })
        });
    },
    
    async logout() {
        return apiRequest('/logout', {
            method: 'POST'
        });
    },
    
    async getCurrentUser() {
        return apiRequest('/user', {
            method: 'GET'
        });
    }
};


/**
 * Check if user is authenticated
 */
async function checkAuth() {
    // First, check sessionStorage for a quick check to prevent race conditions
    const storedUser = sessionStorage.getItem('currentUser');
    if (storedUser) {
        // Asynchronously re-validate with the server in the background
        AuthAPI.getCurrentUser().then(data => {
            if (!data.success) {
                sessionStorage.removeItem('currentUser');
            } else {
                // Update sessionStorage with the latest user data
                sessionStorage.setItem('currentUser', JSON.stringify(data.user));
            }
        });
        return true; // Assume authenticated for now
    }

    // If not in session, check with the server
    try {
        const response = await AuthAPI.getCurrentUser();
        if (response.success && response.user) {
            sessionStorage.setItem('currentUser', JSON.stringify(response.user));
            return true;
        }
        return false;
    } catch (error) {
        return false;
    }
}

/**
 * Require authentication - redirect to login if not authenticated
 */
async function requireAuth(redirectTo = 'login.html') {
    const isAuthenticated = await checkAuth();
    if (!isAuthenticated) {
        window.location.href = redirectTo;
        return false;
    }
    return true;
}

/**
 * Get current user info
 */
async function getCurrentUser() {
    // First, try to get user from sessionStorage for immediate UI updates
    const storedUser = sessionStorage.getItem('currentUser');
    if (storedUser) {
        try {
            return JSON.parse(storedUser);
        } catch (e) {
            sessionStorage.removeItem('currentUser');
        }
    }

    // If not in session, fetch from API
    try {
        const response = await fetch('/api/user', { credentials: 'include' });
        if (!response.ok) {
            return null;
        }
        const result = await response.json();
        if (result.success && result.user) {
            sessionStorage.setItem('currentUser', JSON.stringify(result.user));
            return result.user;
        }
        return null;
    } catch (error) {
        console.error('Error fetching current user:', error);
        return null;
    }
}

/**
 * Update username display in header
 */
async function updateUserDisplay(elementId = 'username') {
    const user = await getCurrentUser();
    const element = document.getElementById(elementId);
    if (element && user) {
        element.textContent = user.username || 'Guest';
    }
    updateAdminLinkVisibility(user);
}

function updateAdminLinkVisibility(user) {
    const adminLink = document.getElementById('admin-link');
    if (adminLink && user && user.role === 'admin') {
        adminLink.style.display = 'block';
    } else if (adminLink) {
        adminLink.style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    updateUserDisplay();
});
