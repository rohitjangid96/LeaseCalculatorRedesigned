/**
 * Authentication Utilities
 * User session management and authentication helpers
 */

/**
 * Check if user is authenticated
 */
async function checkAuth() {
    try {
        const response = await AuthAPI.getCurrentUser();
        return response.success && response.user;
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
    try {
        const response = await AuthAPI.getCurrentUser();
        return response.success ? response.user : null;
    } catch (error) {
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
}

