# Confirm Dialog Library - Usage Guide

A reusable, promise-based confirmation modal library that maintains your existing design system.

## Installation

Include the library in your base template:

```html
<script src="{% static 'js/confirm-dialog.js' %}"></script>
```

## Basic Usage

### Simple Confirmation

```javascript
const confirmed = await confirmDialog.confirm({
  title: 'Delete Item',
  message: 'Are you sure you want to delete this item? This action cannot be undone.',
  confirmText: 'Delete',
  cancelText: 'Cancel'
});

if (confirmed) {
  // User clicked "Delete"
  console.log('Item deleted');
} else {
  // User clicked "Cancel" or closed the modal
  console.log('Action cancelled');
}
```

### Using Presets

The library includes three built-in presets for common scenarios:

#### Delete Preset
```javascript
const confirmed = await confirmDialog.delete(
  'This will permanently delete the cooling system.'
);

if (confirmed) {
  // Proceed with deletion
}
```

#### Warning Preset
```javascript
const confirmed = await confirmDialog.warning(
  'This action will affect all related records.'
);
```

#### Info Preset
```javascript
const confirmed = await confirmDialog.info(
  'Please confirm to proceed with this operation.'
);
```

## Advanced Configuration

### Full Customization

```javascript
const confirmed = await confirmDialog.confirm({
  title: 'Save Changes?',
  message: 'You have unsaved changes. Do you want to save before leaving?',
  confirmText: 'Save',
  cancelText: 'Discard',
  icon: 'save-fill',                                  // Your icon system icon name
  iconColor: 'var(--state--info--base)',              // Icon color
  iconBgColor: 'var(--state--info--lighter)',         // Icon background color
  buttonStyle: 'btn-primary',                          // DaisyUI button class
  allowMultiple: true                                  // Allow multiple modals
});
```

### Available Button Styles

- `btn-error` - Red/danger button (default for delete)
- `btn-warning` - Yellow/warning button
- `btn-primary` - Blue/primary button
- `btn-success` - Green/success button
- `btn-info` - Info button

### Icon Configuration

Use any icon from your existing icon system. Common options:

- `alert-fill` - Warning/error icon (default)
- `info-fill` - Information icon
- `trash-fill` - Delete icon
- `save-fill` - Save icon
- `check-fill` - Success icon

## Real-World Examples

### Delete Cooling System

```javascript
async function deleteCoolingSystem() {
  const confirmed = await confirmDialog.confirm({
    title: 'Are you sure?',
    message: 'You are about to remove or delete added cooling system. This action will permanently remove it.',
    confirmText: 'Remove',
    cancelText: 'Cancel',
    icon: 'alert-fill',
    iconColor: 'var(--state--warning--base)',
    iconBgColor: 'var(--state--warning--lighter)',
    buttonStyle: 'btn-error'
  });

  if (confirmed) {
    // Call your delete API
    await fetch('/api/cooling-system/delete', { method: 'DELETE' });
    // Update UI
  }
}
```

### Form Unsaved Changes Warning

```javascript
window.addEventListener('beforeunload', async (e) => {
  if (hasUnsavedChanges()) {
    e.preventDefault();

    const confirmed = await confirmDialog.confirm({
      title: 'Unsaved Changes',
      message: 'You have unsaved changes. Are you sure you want to leave?',
      confirmText: 'Leave',
      cancelText: 'Stay',
      icon: 'alert-fill',
      iconColor: 'var(--state--warning--base)',
      buttonStyle: 'btn-warning'
    });

    if (!confirmed) {
      e.returnValue = '';
    }
  }
});
```

### Bulk Delete Confirmation

```javascript
async function deleteSelectedItems() {
  const count = getSelectedItemsCount();

  const confirmed = await confirmDialog.delete(
    `You are about to delete ${count} items. This action cannot be undone.`,
    'Delete Multiple Items?'
  );

  if (confirmed) {
    // Proceed with bulk delete
  }
}
```

### Custom Success Confirmation

```javascript
const proceed = await confirmDialog.confirm({
  title: 'Ready to Submit?',
  message: 'Your form is complete. Click Submit to send your data.',
  confirmText: 'Submit',
  cancelText: 'Review',
  icon: 'check-fill',
  iconColor: 'var(--state--success--base)',
  iconBgColor: 'var(--state--success--lighter)',
  buttonStyle: 'btn-success'
});
```

## Multiple Modals

By default, only one confirmation modal can be shown at a time. To allow multiple modals:

```javascript
// Global configuration
window.confirmDialog.options.allowMultiple = true;

// Or per-modal
const confirmed = await confirmDialog.confirm({
  title: 'Second Confirmation',
  message: 'Are you really sure?',
  allowMultiple: true
});
```

## Programmatic Control

### Close All Modals

```javascript
// Close all active confirmation modals
confirmDialog.closeAll();
```

## Migrating from Existing Modals

To migrate your existing modal like the cooling system modal:

**Before:**
```html
<dialog id="cooling_system_modal_delete" class="modal modal-middle">
  <!-- modal content -->
</dialog>

<script>
function deleteCoolingSystem() {
  cooling_system_modal_delete.showModal();
}
</script>
```

**After:**
```javascript
async function deleteCoolingSystem() {
  const confirmed = await confirmDialog.delete(
    'You are about to remove or delete added cooling system. This action will permanently remove it.'
  );

  if (confirmed) {
    // Your delete logic here
  }
}
```

## Notes

- The library automatically integrates with your existing icon system by calling `window.initializeIcons()` if available
- Modals are automatically cleaned up from the DOM after closing
- The library uses native HTML `<dialog>` elements with proper accessibility
- All styling is maintained from your existing design system (DaisyUI + TailwindCSS)
- ESC key and backdrop clicks will cancel the modal (same as clicking Cancel)
