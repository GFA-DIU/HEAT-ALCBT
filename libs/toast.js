/**
 * Toast Notification Library
 * A simple toast notification system using DaisyUI components
 *
 * Usage:
 *   Toast.success('Operation successful!');
 *   Toast.error('Something went wrong!');
 *   Toast.warning('Please check your input', { duration: 5000 });
 *   Toast.info('Processing...', { duration: 0, dismissible: true });
 */

class ToastNotification {
    constructor() {
        this.container = null;
        this.defaultOptions = {
            duration: 3000,
            position: 'top-right',
            dismissible: true,
            icon: true
        };
    }

    /**
     * Initialize the toast container if it doesn't exist
     * Always appends to document.body so toasts render above any open
     * <dialog> stacking context.
     */
    initContainer(position) {
        const containerId = `toast-stack-${position}`;

        // Always use body as parent — dialogs create their own stacking context
        // which would clip toasts rendered inside them.
        const parent = document.body;

        // Look for existing container in the correct parent
        let container = parent.querySelector(`#${containerId}`);

        if (!container) {
            container = document.createElement('div');
            container.id = containerId;
            container.className = `toast toast-${position}`;
            container.style.zIndex = '999999';
            container.style.pointerEvents = 'none'; // Allow clicks through container
            parent.appendChild(container);
        }

        return container;
    }

    /**
     * Get the appropriate icon SVG for the toast type
     */
    getIcon(type) {
        const icons = {
            success: `<svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`,
            error: `<svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`,
            warning: `<svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>`,
            info: `<svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>`
        };
        return icons[type] || icons.info;
    }

    /**
     * Create and show a toast notification
     */
    show(message, type = 'info', options = {}) {
        const opts = { ...this.defaultOptions, ...options };
        const container = this.initContainer(opts.position);

        // Create toast element
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} shadow-lg animate-slide-in`;
        toast.style.pointerEvents = 'auto'; // Enable clicks on individual toasts

        // Build toast content
        let content = '<div class="flex items-center gap-2">';

        // Add icon if enabled
        if (opts.icon) {
            content += this.getIcon(type);
        }

        // Add message
        content += `<span>${message}</span>`;
        content += '</div>';

        // Add close button if dismissible
        if (opts.dismissible) {
            content += `
                <button class="btn btn-sm btn-circle btn-ghost ml-auto" onclick="this.parentElement.remove()">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                </button>
            `;
        }

        toast.innerHTML = content;

        // Add to container
        container.appendChild(toast);

        // Auto-dismiss if duration is set
        if (opts.duration > 0) {
            setTimeout(() => {
                this.dismiss(toast);
            }, opts.duration);
        }

        return toast;
    }

    /**
     * Dismiss a toast with animation
     */
    dismiss(toast) {
        if (!toast || !toast.parentElement) return;

        toast.classList.add('animate-slide-out');
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 300);
    }

    /**
     * Show success toast
     */
    success(message, options = {}) {
        return this.show(message, 'success', options);
    }

    /**
     * Show error toast
     */
    error(message, options = {}) {
        return this.show(message, 'error', options);
    }

    /**
     * Show warning toast
     */
    warning(message, options = {}) {
        return this.show(message, 'warning', options);
    }

    /**
     * Show info toast
     */
    info(message, options = {}) {
        return this.show(message, 'info', options);
    }

    /**
     * Clear all toasts
     */
    clearAll() {
        const containers = document.querySelectorAll('[id^="toast-stack-"]');
        containers.forEach(container => {
            container.innerHTML = '';
        });
    }
}

// Create global Toast instance
const Toast = new ToastNotification();
window.Toast = Toast;

// Add animations to the page if they don't exist
if (!document.getElementById('toast-animations')) {
    const style = document.createElement('style');
    style.id = 'toast-animations';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }

        .animate-slide-in {
            animation: slideIn 0.3s ease-out;
        }

        .animate-slide-out {
            animation: slideOut 0.3s ease-in;
        }

        .toast {
            position: fixed;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            pointer-events: none;
        }

        .toast > * {
            min-width: 300px;
            max-width: 400px;
        }

        .toast-top-right {
            top: 1rem;
            right: 1rem;
        }

        .toast-top-left {
            top: 1rem;
            left: 1rem;
        }

        .toast-bottom-right {
            bottom: 1rem;
            right: 1rem;
        }

        .toast-bottom-left {
            bottom: 1rem;
            left: 1rem;
        }

        .toast-top-center {
            top: 1rem;
            left: 50%;
            transform: translateX(-50%);
        }

        .toast-bottom-center {
            bottom: 1rem;
            left: 50%;
            transform: translateX(-50%);
        }

        @media (max-width: 640px) {
            .toast {
                min-width: 280px;
                max-width: calc(100vw - 2rem);
            }
        }
    `;
    document.head.appendChild(style);
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Toast;
}
