
// Toast Notification System
function showToast(message, type = 'success', duration = 5000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = { success: '✅', error: '❌', warning: '⚠️' };

    // Support both simple string message and title/message object or format
    // If message is the only arg, treat as message. If title is passed...
    // The signatures were slightly different in files.
    // ivyApplication: showToast(message, type, duration)
    // admin: showToast(title, message, type, duration)
    // We will standardize on: showToast(title, message, type, duration) OR showToast(message, type, duration)
    // But since this is a refactor, let's keep it simple.
    // If arguments.length > 3 or second arg is string (and type is 3rd)...

    // Let's analyze usage:
    // ivy: showToast('msg', 'type')
    // admin: showToast('Title', 'Msg', 'type')

    // Implementation to support both:
    let titleText = '';
    let messageText = message;
    let toastType = type;
    let toastDuration = duration;

    // Check if called with 4 args (Admin style) or 3 args but 2nd is string and 3rd is type
    // Actually, Admin: showToast(title, message, type, duration)
    // Ivy: showToast(message, type, duration)

    if (arguments.length === 4 || (arguments.length === 3 && typeof arguments[1] === 'string' && ['success', 'error', 'warning'].includes(arguments[2]))) {
        // Admin style likely
        titleText = arguments[0];
        messageText = arguments[1];
        toastType = arguments[2] || 'success';
        toastDuration = arguments[3] || 4000;
    }

    toast.innerHTML = `
        <div class="toast-icon">${icons[toastType] || '📢'}</div>
        <div class="toast-content" style="flex:1">
            ${titleText ? `<div class="toast-title" style="font-weight:600; margin-bottom:2px;">${titleText}</div>` : ''}
            <div class="toast-message">${messageText}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()" style="background:none; border:none; font-size:20px; color:#999; cursor:pointer;">×</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, toastDuration);
}

// API Helper
async function apiFetch(url, options = {}) {
    const API_BASE = window.location.protocol === 'file:' ? 'http://localhost:3000' : '';
    const fullUrl = url.startsWith('http') ? url : `${API_BASE}${url}`;

    // Add auth token if available (for admin)
    const token = localStorage.getItem('adminToken');
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    return fetch(fullUrl, {
        ...options,
        headers
    });
}
