// @ts-check

/**
 * Form Validation Utility for multi-step forms
 * Integrates with StepManager and provides comprehensive validation
 */
class FormValidator {
  /**
   * @param {HTMLFormElement} form - The form element to validate
   * @param {Object} options - Validation options
   * @param {Object<string, Function>} options.customValidators - Custom validation functions
   * @param {boolean} options.validateOnInput - Whether to validate on input events
   * @param {Function} options.onStatusChange - Callback when validation status changes
   */
  constructor(form, options = {}) {
    this.form = form;
    this.customValidators = options.customValidators || {};
    this.validateOnInput = options.validateOnInput !== false; // default true
    this.onStatusChange = options.onStatusChange || null;
    this.errors = {};

    this.init();
  }

  init() {
    if (!this.form) {
      console.error('FormValidator: No form element provided');
      return;
    }

    // Bind validation events
    if (this.validateOnInput) {
      this.form.addEventListener('input', (e) => this.handleInput(e));
      this.form.addEventListener('change', (e) => this.handleInput(e));
      this.form.addEventListener('blur', (e) => this.handleBlur(e), true); // Use capture for blur
    }

    // Initial validation
    this.validate(false);
  }

  /**
   * Handle input/change events
   * @param {Event} event
   */
  handleInput(event) {
    const field = event.target;
    if (field.name) {
      this.validateField(field);
      this.displayFieldError(field);
      this.updateFormStatus();
    }
  }

  /**
   * Handle blur events (show errors when user leaves field)
   * @param {Event} event
   */
  handleBlur(event) {
    const field = event.target;
    if (field.name) {
      this.validateField(field);
      this.displayFieldError(field);
    }
  }

  /**
   * Validate a single field
   * @param {HTMLInputElement|HTMLSelectElement|HTMLTextAreaElement} field
   * @returns {boolean} Whether the field is valid
   */
  validateField(field) {
    const fieldName = field.name;
    const value = field.type === 'checkbox' ? field.checked : field.value.trim();
    const errors = [];

    // HTML5 validation
    if (field.required && !value) {
      errors.push('This field is required');
    }

    if (field.type === 'email' && value && !this.isValidEmail(value)) {
      errors.push('Please enter a valid email address');
    }

    if (field.type === 'url' && value && !this.isValidUrl(value)) {
      errors.push('Please enter a valid URL');
    }

    if (field.type === 'number' || field.inputMode === 'numeric') {
      if (+field.min && parseFloat(value) < parseFloat(field.min)) {
        errors.push(`Value must be at least ${field.min}`);
      }
      if (+field.max && parseFloat(value) > parseFloat(field.max)) {
        errors.push(`Value must be at most ${field.max}`);
      }
    }

    if (+field.minlength && value.length < field.minlength) {
      errors.push(`Minimum length is ${field.minlength} characters`);
    }

    if (+field.maxlength && value.length > field.maxlength) {
      errors.push(`Maximum length is ${field.maxlength} characters`);
    }

    if (field.pattern && value) {
      const regex = new RegExp(field.pattern);
      if (!regex.test(value)) {
        errors.push(field.title || 'Invalid format');
      }
    }

    // Custom validators
    if (this.customValidators[fieldName]) {
      const customError = this.customValidators[fieldName](value, field, this.form);
      if (customError) {
        errors.push(customError);
      }
    } 
    // Update errors object
    if (errors.length > 0) {
      this.errors[fieldName] = errors;
      return false;
    } else {
      delete this.errors[fieldName];
      return true;
    }
  }

  /**
   * Validate entire form
   * @returns {boolean} Whether the form is valid
   * @param {boolean} showErrors - Whether to display errors immediately
   */
  validate(showErrors = true) {
    this.errors = {};
    let isValid = true;

    // Get all form fields
    const fields = this.form.querySelectorAll('input, select, textarea');
 
    fields.forEach(field => {
      if (field.name && !field.disabled) {
        const fieldValid = this.validateField(field);
        if (!fieldValid) {
          isValid = false;
        }
      }
    });

    if (showErrors) {
      this.displayErrors();
    }

    return isValid;
  }

  /**
   * Display error for a specific field
   * @param {HTMLElement} field
   */
  displayFieldError(field) { 
    const fieldName = field.name;
    const errors = this.errors[fieldName];

    // Find the field container (usually a fieldset or label)
    const fieldContainer = field.closest('fieldset, .form-field, .field-group') || field.closest('label');

    if (!fieldContainer) return;

    // Find or create error message element
    let errorElement = fieldContainer.querySelector('.validator-hint, .error-message');

    if (!errorElement) {
      errorElement = document.createElement('p');
      errorElement.className = 'validator-hint error-message text-error';

      // Insert after the input/label
      const inputWrapper = field.closest('label') || field;
      if (inputWrapper.nextSibling) {
        inputWrapper.parentNode.insertBefore(errorElement, inputWrapper.nextSibling);
      } else {
        fieldContainer.appendChild(errorElement);
      }
    }
    fieldContainer.classList.add('input-error', 'border-error');
    if (errors && errors.length > 0) {
      // Show error
      field.setAttribute('aria-invalid', 'true');
      field.setAttribute('user-invalid', 'true');
      errorElement.textContent = errors[0]; // Show first error
      errorElement.style.display = 'block';
      errorElement.classList.add('text-error');

      // Add error class to input
      const inputElement = field.closest('label.input') || field.closest('.select');
      if (inputElement) {
        inputElement.classList.add('input-error', 'border-error');
      }
      field.classList.add('border-error');
    } else {
      // Hide error
      errorElement.style.display = 'none';
      errorElement.classList.remove('text-error');
      field.setAttribute('aria-invalid', 'false');
      field.setAttribute('user-invalid', 'false');
      // Remove error class from input
      const inputElement = field.closest('label.input') || field.closest('.select');
      if (inputElement) {
        inputElement.classList.remove('input-error', 'border-error');
      }
      field.classList.remove('border-error');
    }
  }

  /**
   * Display all errors in the form
   */
  displayErrors() {
    const fields = this.form.querySelectorAll('input, select, textarea');
    fields.forEach(field => {
      if (field.name) {
        this.displayFieldError(field);
      }
    });
  }

  /**
   * Clear all errors
   */
  clearErrors() {
    this.errors = {};
    const errorElements = this.form.querySelectorAll('.validator-hint, .error-message');
    errorElements.forEach(el => {
      el.style.display = 'none';
      el.textContent = '';
    });

    const inputsWithErrors = this.form.querySelectorAll('.input-error, .border-error');
    inputsWithErrors.forEach(el => {
      el.classList.remove('input-error', 'border-error');
    });
  }

  /**
   * Update form validation status and notify StepManager
   */
  updateFormStatus() {
    const isValid = Object.keys(this.errors).length === 0;

    // Get form data
    const formData = new FormData(this.form);
    const data = Object.fromEntries(formData.entries());

    // Dispatch custom event for StepManager
    const event = new CustomEvent('onFormStatus', {
      detail: {
        isValid: isValid,
        data: data,
        errors: this.errors
      },
      bubbles: true
    });
    document.dispatchEvent(event);

    // Call callback if provided
    if (this.onStatusChange) {
      this.onStatusChange(isValid, data, this.errors);
    }

    return isValid;
  }

  /**
   * Get form data
   * @returns {Object}
   */
  getFormData() {
    const formData = new FormData(this.form);
    return Object.fromEntries(formData.entries());
  }

  /**
   * Validate email format
   * @param {string} email
   * @returns {boolean}
   */
  isValidEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  }

  /**
   * Validate URL format
   * @param {string} url
   * @returns {boolean}
   */
  isValidUrl(url) {
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Set custom validator for a field
   * @param {string} fieldName
   * @param {Function} validator - Returns error message or null if valid
   */
  setCustomValidator(fieldName, validator) {
    this.customValidators[fieldName] = validator;
  }

  /**
   * Display server-side validation errors
   * @param {Object<string, string[]>} serverErrors - Django form errors format
   */
  displayServerErrors(serverErrors) {
    // Clear existing errors first
    this.clearErrors();

    // Set new errors
    this.errors = serverErrors;

    // Display each error
    Object.keys(serverErrors).forEach(fieldName => {
      const field = this.form.querySelector(`[name="${fieldName}"]`);
      if (field) {
        this.displayFieldError(field);
      }
    });

    this.updateFormStatus();
  }

  /**
   * Submit form with validation
   * @param {string} url - The URL to submit to
   * @param {Object} options - Additional fetch options
   * @returns {Promise<Response>}
   */
  async submit(url, options = {}) {
    // Validate before submitting
    const isValid = this.validate();

    if (!isValid) {
      this.displayErrors();
      throw new Error('Form validation failed');
    }

    // Get CSRF token
    const csrfToken = this.form.querySelector('[name=csrfmiddlewaretoken]')?.value;

    // Prepare form data
    const formData = new FormData(this.form);

    // Submit
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'X-CSRFToken': csrfToken || '',
        ...options.headers
      },
      body: formData,
      ...options
    });

    // Handle validation errors from server
    if (response.status === 400) {
      const errorData = await response.json();
      if (errorData.errors) {
        this.displayServerErrors(errorData.errors);
      }
    }

    return response;
  }
}

// Export for use in other scripts
if (typeof window !== 'undefined') {
  window.FormValidator = FormValidator;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = FormValidator;
}
