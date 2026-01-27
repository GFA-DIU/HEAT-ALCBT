/**
 * Confirmation Modal Library
 * A reusable modal dialog system for user confirmations
 *
 * @example
 * const confirmed = await confirmDialog({
 *   title: "Delete Item?",
 *   message: "This action cannot be undone.",
 *   confirmText: "Delete",
 *   cancelText: "Cancel",
 *   type: "error"
 * });
 *
 * if (confirmed) {
 *   // User confirmed
 * }
 */

class ConfirmDialog {
  constructor(options = {}) {
    this.options = {
      allowMultiple: false,
      ...options
    };
    this.activeModals = new Map();
  }

  /**
   * Show a confirmation dialog
   * @param {Object} config - Configuration object
   * @param {string} config.title - Modal title (default: "Are you sure?")
   * @param {string} config.message - Modal message/description
   * @param {string} config.confirmText - Confirm button text (default: "Confirm")
   * @param {string} config.cancelText - Cancel button text (default: "Cancel")
   * @param {string} config.icon - Icon name from your icon system (default: "alert-fill")
   * @param {string} config.iconColor - Icon color CSS variable (default: "var(--state--warning--base)")
   * @param {string} config.iconBg - Icon background color (default: "var(--state--warning--lighter)")
   * @param {string} config.buttonStyle - Button style class: 'btn-error', 'btn-warning', 'btn-primary' (default: 'btn-error')
   * @returns {Promise<boolean>} - Returns true if confirmed, false if cancelled
   */
  confirm(options = {}) {
    const {
      title = 'Are you sure?',
      message = 'This action cannot be undone.',
      confirmText = 'Confirm',
      cancelText = 'Cancel',
      icon = 'alert-fill',
      iconColor = 'var(--state--warning--base)',
      iconBgColor = 'var(--state--warning--lighter)',
      buttonStyle = 'btn-error', // btn-error, btn-warning, btn-primary, etc.
      allowMultiple = false
    } = options;

    // If multiple modals are not allowed, close any existing ones
    if (!allowMultiple) {
      this.closeAll();
    }

    return new Promise((resolve) => {
      const modalId = `confirm_modal_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      // Create modal HTML
      const modalHTML = `
        <dialog id="${modalId}" class="modal modal-middle">
          <div class="modal-box w-full max-w-[26.375rem] p-0">
            <div class="flex flex-col items-center p-5">
              <div
                class="flex items-center p-2 justify-center rounded-[var(--radius-8)]"
                style="background-color: ${iconBgColor};"
              >
                <span
                  data-icon="${icon}"
                  data-size="24"
                  data-color="${iconColor}"
                ></span>
              </div>
              <h3 class="text-lg/6 font-medium mt-4">${title}</h3>
              <p class="text-sm/5 text-[var(--text--sub-600)] text-center mt-1">
                ${message}
              </p>
            </div>
            <div
              class="p-5 border-t border-[var(--stroke--soft-200)] flex gap-4 items-center justify-between w-full"
            >
              <button
                class="btn btn-sm btn-outline text-[var(--text--sub-600)] border-[var(--stroke--soft-200)] flex-1"
                data-action="cancel"
              >
                ${cancelText}
              </button>
              <button class="btn btn-sm ${buttonStyle} flex-1" data-action="confirm">${confirmText}</button>
            </div>
          </div>
        </dialog>
      `;

      // Insert modal into DOM
      document.body.insertAdjacentHTML('beforeend', modalHTML);

      const modalElement = document.getElementById(modalId);

      // Handle button clicks
      const handleAction = (confirmed) => {
        modalElement.close();
        // Remove modal from DOM after animation
        setTimeout(() => {
          modalElement.remove();
        }, 300);
        resolve(confirmed);
      };

      modalElement.querySelector('[data-action="cancel"]').addEventListener('click', () => handleAction(false));
      modalElement.querySelector('[data-action="confirm"]').addEventListener('click', () => handleAction(true));

      // Handle backdrop click (ESC key or clicking outside)
      modalElement.addEventListener('cancel', () => handleAction(false));
      modalElement.addEventListener('close', () => {
        if (modalElement.returnValue !== 'confirm' && modalElement.returnValue !== 'cancel') {
          handleAction(false);
        }
      });

      // Show modal
      modalElement.showModal();

      // Store reference for cleanup
      this.activeModals.set(modalId, modalElement);
    });
  }

  /**
   * Close all active modals
   */
  closeAll() {
    this.activeModals.forEach((modal) => {
      modal.close();
      modal.remove();
    });
    this.activeModals.clear();
  }

  /**
   * Preset configurations for common scenarios
   */
  static presets = {
    delete: {
      title: 'Are you sure?',
      icon: 'alert-fill',
      iconColor: 'var(--state--warning--base)',
      iconBgColor: 'var(--state--warning--lighter)',
      buttonStyle: 'btn-error',
      confirmText: 'Delete',
      cancelText: 'Cancel'
    },
    warning: {
      title: 'Warning',
      icon: 'alert-fill',
      iconColor: 'var(--state--warning--base)',
      iconBgColor: 'var(--state--warning--lighter)',
      buttonStyle: 'btn-warning',
      confirmText: 'Continue',
      cancelText: 'Cancel'
    },
    info: {
      title: 'Confirmation',
      icon: 'info-fill',
      iconColor: 'var(--state--info--base)',
      iconBgColor: 'var(--state--info--lighter)',
      buttonStyle: 'btn-primary',
      confirmText: 'OK',
      cancelText: 'Cancel'
    }
  };

  /**
   * Helper method to show delete confirmation
   */
  async delete(message, title = 'Are you sure?') {
    return this.confirm({
      ...ConfirmDialog.presets.delete,
      title,
      message
    });
  }

  /**
   * Helper method to show warning confirmation
   */
  async warning(message, title = 'Warning') {
    return this.confirm({
      ...ConfirmDialog.presets.warning,
      title,
      message
    });
  }

  /**
   * Helper method to show info confirmation
   */
  async info(message, title = 'Confirmation') {
    return this.confirm({
      ...ConfirmDialog.presets.info,
      title,
      message
    });
  }
}

// Create a global instance
window.confirmDialog = new ConfirmDialog();

// Example usage:
//
// Basic usage:
// const confirmed = await confirmDialog.confirm({
//   title: 'Delete Item',
//   message: 'Are you sure you want to delete this item?',
//   confirmText: 'Delete',
//   cancelText: 'Cancel'
// });
//
// if (confirmed) {
//   // User clicked confirm
//   console.log('Confirmed!');
// } else {
//   // User clicked cancel or closed the modal
//   console.log('Cancelled!');
// }
//
// Using presets:
// const confirmed = await confirmDialog.delete('This will permanently delete the cooling system.');
//
// Custom configuration:
// const confirmed = await confirmDialog.confirm({
//   title: 'Save Changes?',
//   message: 'You have unsaved changes. Do you want to save before leaving?',
//   icon: 'save-fill',
//   iconColor: 'var(--state--info--base)',
//   iconBgColor: 'var(--state--info--lighter)',
//   buttonStyle: 'btn-primary',
//   confirmText: 'Save',
//   cancelText: 'Discard',
//   allowMultiple: true
// });
