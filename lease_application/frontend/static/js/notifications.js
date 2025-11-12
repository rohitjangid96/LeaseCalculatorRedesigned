/**
 * Notification System Client-Side Logic
 * Handles fetching, displaying, and managing user notifications
 */

let notificationPollingInterval = null;

// Initialize notifications when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    setupNotificationEventListeners();
    setupPolling();
    fetchNotifications(); // Initial fetch
});

/**
 * Set up event listeners for notification UI
 */
function setupNotificationEventListeners() {
    const notificationArea = document.getElementById('notification-area');
    const notificationBell = notificationArea.querySelector('.notification-bell');

    // Toggle dropdown on bell click
    notificationBell.addEventListener('click', function(e) {
        e.stopPropagation();
        toggleNotificationDropdown();
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        const dropdown = document.getElementById('notification-dropdown');
        const notificationArea = document.getElementById('notification-area');

        if (!notificationArea.contains(e.target)) {
            dropdown.classList.add('hidden');
        }
    });
}

/**
 * Toggle the notification dropdown visibility
 */
function toggleNotificationDropdown() {
    const dropdown = document.getElementById('notification-dropdown');
    dropdown.classList.toggle('hidden');
}

/**
 * Set up polling for notifications every 60 seconds
 */
function setupPolling() {
    if (notificationPollingInterval) {
        clearInterval(notificationPollingInterval);
    }

    // Poll every 60 seconds
    notificationPollingInterval = setInterval(fetchNotifications, 60000);
}

/**
 * Fetch notifications from the server
 */
function fetchNotifications() {
    fetch('/api/notifications/inbox', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin'
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.success) {
            updateNotificationCount(data.unread_count);
            renderNotifications(data.notifications);
        } else {
            console.error('Failed to fetch notifications:', data.error);
        }
    })
    .catch(error => {
        console.error('Error fetching notifications:', error);
    });
}

/**
 * Update the notification count badge
 */
function updateNotificationCount(count) {
    const badge = document.getElementById('notification-count');
    badge.textContent = count;

    // Hide badge if no notifications
    if (count === 0) {
        badge.style.display = 'none';
    } else {
        badge.style.display = 'inline';
    }
}

/**
 * Render notifications in the dropdown
 */
function renderNotifications(notifications) {
    const notificationBody = document.querySelector('.notification-list-body');
    notificationBody.innerHTML = '';

    if (notifications.length === 0) {
        notificationBody.innerHTML = '<div class="no-notifications">No notifications</div>';
        return;
    }

    notifications.forEach(notification => {
        const notificationElement = createNotificationElement(notification);
        notificationBody.appendChild(notificationElement);
    });
}

/**
 * Create a notification element
 */
function createNotificationElement(notification) {
    const div = document.createElement('div');
    div.className = `notification-item ${notification.is_read ? 'read' : 'unread'}`;

    // Format the notification message
    const messageHtml = formatNotificationMessage(notification);

    div.innerHTML = `
        <div class="notification-content" onclick="handleNotificationClick(${notification.notification_id}, ${notification.is_read})">
            ${messageHtml}
            <div class="notification-time">${formatTime(notification.sent_at)}</div>
        </div>
        <div class="notification-actions">
            ${!notification.is_read ? '<button class="mark-read-btn" onclick="markAsRead(' + notification.notification_id + '); event.stopPropagation();">Mark as Read</button>' : ''}
            <button class="dismiss-btn" onclick="dismissNotification(${notification.notification_id}); event.stopPropagation();">×</button>
        </div>
    `;

    return div;
}

/**
 * Format notification message with clickable lease links
 */
function formatNotificationMessage(notification) {
    let message = notification.message;

    // Replace lease ID references with clickable links
    message = message.replace(/Lease (\d+)/g, '<a href="/lease_form.html?id=$1" class="lease-link">Lease $1</a>');

    return `<div class="notification-message">${message}</div>`;
}

/**
 * Format timestamp for display
 */
function formatTime(timestamp) {
    try {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffHours = diffMs / (1000 * 60 * 60);
        const diffDays = diffMs / (1000 * 60 * 60 * 24);

        if (diffHours < 1) {
            return 'Just now';
        } else if (diffHours < 24) {
            return `${Math.floor(diffHours)}h ago`;
        } else if (diffDays < 7) {
            return `${Math.floor(diffDays)}d ago`;
        } else {
            return date.toLocaleDateString();
        }
    } catch (e) {
        return timestamp;
    }
}

/**
 * Mark a notification as read
 */
function markAsRead(notificationId) {
    fetch(`/api/notifications/${notificationId}/read`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            fetchNotifications(); // Refresh the list
        } else {
            console.error('Failed to mark notification as read:', data.error);
        }
    })
    .catch(error => {
        console.error('Error marking notification as read:', error);
    });
}

/**
 * Dismiss a single notification
 */
function dismissNotification(notificationId) {
    fetch(`/api/notifications/${notificationId}/dismiss`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            fetchNotifications(); // Refresh the list
        } else {
            console.error('Failed to dismiss notification:', data.error);
        }
    })
    .catch(error => {
        console.error('Error dismissing notification:', error);
    });
}

/**
 * Dismiss all notifications
 */
function dismissAllNotifications() {
    fetch('/api/notifications/dismiss_all', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            fetchNotifications(); // Refresh the list
            // Close the dropdown
            document.getElementById('notification-dropdown').classList.add('hidden');
        } else {
            console.error('Failed to dismiss all notifications:', data.error);
        }
    })
    .catch(error => {
        console.error('Error dismissing all notifications:', error);
    });
}

/**
 * Handle notification click - mark as read if unread and close dropdown
 */
function handleNotificationClick(notificationId, isRead) {
    if (!isRead) {
        markAsRead(notificationId);
    }
    // Close the dropdown after clicking
    document.getElementById('notification-dropdown').classList.add('hidden');
}

/**
 * Clean up polling when page unloads
 */
window.addEventListener('beforeunload', function() {
    if (notificationPollingInterval) {
        clearInterval(notificationPollingInterval);
    }
});
