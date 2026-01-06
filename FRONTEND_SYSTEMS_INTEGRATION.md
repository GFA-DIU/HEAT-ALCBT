# Frontend Integration Guide for Building Operational Systems

This document provides comprehensive documentation for frontend developers working with the building operational systems. All systems follow a consistent pattern for direct database persistence without session storage.

## Overview

The following operational systems have been implemented with direct database persistence:
1. Hot Water System
2. Lift & Escalator System
3. Lighting System
4. Ventilation System
5. Cooling System

All systems follow the same architectural pattern:
- **Direct DB saves** on modal "Save" button click
- **No session storage** - data is immediately persisted to the database
- **CRUD operations** via RESTful API endpoints
- **CSRF protection** for all POST/PUT/DELETE requests

---

## 1. Hot Water System

### API Endpoints

#### Create/Update Hot Water System
- **Endpoint**: `/hot-water-system/`
- **Methods**: POST (create), PUT (update)
- **Request Body**:
```json
{
  "building_id": "uuid-string",
  "system_id": 123,  // Optional, for updates only
  "type_of_hot_water_system": "solar_thermal",
  "year_of_installation": 2020,
  "fuel_type": "Natural Gas",
  "baseline_hot_water_energy_consumption": 5000.5,
  "baseline_hot_water_system_efficiency": 0.85,
  "baseline_hot_water_type_heating_efficiency": 0.90,
  "number_of_units": 2,
  "annual_operating_hours_per_day": 12.0,
  "annual_operating_days_per_week": 7,
  "annual_operating_weeks_per_year": 52
}
```

#### Get Hot Water Systems
- **Endpoint**: `/hot-water-system/<building_id>/`
- **Method**: GET
- **Response**: Array of hot water systems for the building

#### Delete Hot Water System
- **Endpoint**: `/hot-water-system/<system_id>/delete/`
- **Method**: DELETE

### Frontend Implementation

**File**: `templates/pages/add-building/components/operational-details/hot-water-system.html`

**Key Functions**:
```javascript
// Save system (create or update)
window.saveHotWaterSystem = async function() {
  const systemData = {
    building_id: buildingId,
    system_id: window.editingHotWaterSystemId, // Only for updates
    type_of_hot_water_system: formData.get('type_of_hot_water_system'),
    year_of_installation: parseInt(formData.get('year_of_installation')),
    // ... other fields
  };

  const method = window.editingHotWaterSystemId ? 'PUT' : 'POST';
  const response = await fetch('/hot-water-system/', {
    method: method,
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCSRFToken(),
    },
    body: JSON.stringify(systemData),
  });
}

// Load systems from database
async function loadHotWaterSystems() {
  const response = await fetch(`/hot-water-system/${buildingId}/`);
  const data = await response.json();
  // Render systems...
}

// Edit system
window.editHotWaterSystem = function(systemId) {
  // Find system in array and populate form
}

// Delete system
window.deleteHotWaterSystem = async function(systemId) {
  const response = await fetch(`/hot-water-system/${systemId}/delete/`, {
    method: 'DELETE',
    headers: { 'X-CSRFToken': getCSRFToken() },
  });
}
```

### Field Mapping (Frontend → Backend)

| Frontend Field Name | Backend Model Field |
|---------------------|---------------------|
| `type_of_hot_water_system` | `hot_water_system_type` |
| `year_of_installation` | `year_of_installation` |
| `fuel_type` | `fuel_type` |
| `baseline_hot_water_energy_consumption` | `baseline_hot_water_energy_consumption` |
| `baseline_hot_water_system_efficiency` | `baseline_hot_water_system_efficiency` |
| `baseline_hot_water_type_heating_efficiency` | `baseline_hot_water_type_heating_efficiency` |
| `number_of_units` | `number_of_units` |
| `annual_operating_hours_per_day` | `operation_hours_per_workday` |
| `annual_operating_days_per_week` | `workdays_per_week` |
| `annual_operating_weeks_per_year` | `workweeks_per_year` |

---

## 2. Lift & Escalator System

### API Endpoints

#### Create/Update Lift/Escalator System
- **Endpoint**: `/lift-escalator-system/`
- **Methods**: POST (create), PUT (update)
- **Request Body**:
```json
{
  "building_id": "uuid-string",
  "system_id": 123,  // Optional, for updates only
  "lift_type": "passenger",
  "year_of_installation": 2021,
  "number_of_lifts": 3,
  "baseline_lift_energy_consumption": 2500.75,
  "lift_load_factor": 0.70,
  "annual_operating_hours_per_day": 14.0,
  "annual_operating_days_per_week": 6,
  "annual_operating_weeks_per_year": 50
}
```

#### Get Lift/Escalator Systems
- **Endpoint**: `/lift-escalator-system/<building_id>/`
- **Method**: GET

#### Delete Lift/Escalator System
- **Endpoint**: `/lift-escalator-system/<system_id>/delete/`
- **Method**: DELETE

### Frontend Implementation

**File**: `templates/pages/add-building/components/operational-details/lift-escalator-system.html`

**Key Functions**: Same pattern as Hot Water System

### Field Mapping (Frontend → Backend)

| Frontend Field Name | Backend Model Field |
|---------------------|---------------------|
| `lift_type` | `lift_type` |
| `year_of_installation` | `year_of_installation` |
| `number_of_lifts` | `number_of_lifts` |
| `baseline_lift_energy_consumption` | `baseline_lift_energy_consumption` |
| `lift_load_factor` | `lift_load_factor` |
| `annual_operating_hours_per_day` | `operation_hours_per_workday` |
| `annual_operating_days_per_week` | `workdays_per_week` |
| `annual_operating_weeks_per_year` | `workweeks_per_year` |

---

## 3. Lighting System

### API Endpoints

#### Create/Update Lighting System
- **Endpoint**: `/lighting-system/`
- **Methods**: POST (create), PUT (update)
- **Request Body**:
```json
{
  "building_id": "uuid-string",
  "system_id": 123,  // Optional, for updates only
  "lighting_type": "led",
  "baseline_lighting_power_density": 8.5,
  "lighting_control_system": "daylight_sensors",
  "operating_hours_per_day": 10.0,
  "days_per_week": 5,
  "weeks_per_year": 52,
  "annual_baseline_lighting_energy_consumption": 12000.0
}
```

#### Get Lighting Systems
- **Endpoint**: `/lighting-system/<building_id>/`
- **Method**: GET

#### Delete Lighting System
- **Endpoint**: `/lighting-system/<system_id>/delete/`
- **Method**: DELETE

### Frontend Implementation

**File**: `templates/pages/add-building/components/operational-details/lighting-system.html`

**Key Functions**: Same pattern as Hot Water System

### Field Mapping (Frontend → Backend)

| Frontend Field Name | Backend Model Field |
|---------------------|---------------------|
| `lighting_type` | `lighting_type` |
| `baseline_lighting_power_density` | `baseline_lighting_power_density` |
| `lighting_control_system` | `lighting_control_system` |
| `operating_hours_per_day` | `operation_hours_per_workday` |
| `days_per_week` | `workdays_per_week` |
| `weeks_per_year` | `workweeks_per_year` |
| `annual_baseline_lighting_energy_consumption` | `baseline_lighting_energy_consumption` |

---

## 4. Ventilation System

### API Endpoints

#### Create/Update Ventilation System
- **Endpoint**: `/ventilation-system/`
- **Methods**: POST (create), PUT (update)
- **Request Body**:
```json
{
  "building_id": "uuid-string",
  "system_id": 123,  // Optional, for updates only
  "ventilation_type": "cassette_ac",
  "year_of_installation": 2022,
  "total_cooling_load": 1500.0,
  "baseline_efficiency": 0.88,
  "operating_hours_per_day": 12.0,
  "days_per_week": 6,
  "weeks_per_year": 50,
  "total_energy_consumption": 8500.0,
  "number_of_units": 5,
  "total_system_power": 45.0,
  "number_of_stars": 4
}
```

#### Get Ventilation Systems
- **Endpoint**: `/ventilation-system/<building_id>/`
- **Method**: GET

#### Delete Ventilation System
- **Endpoint**: `/ventilation-system/<system_id>/delete/`
- **Method**: DELETE

### Frontend Implementation

**File**: `templates/pages/add-building/components/operational-details/ventilation-system.html`

**Key Functions**: Same pattern as Hot Water System

### Field Mapping (Frontend → Backend)

| Frontend Field Name | Backend Model Field |
|---------------------|---------------------|
| `ventilation_type` | `ventilation_type` |
| `year_of_installation` | `year_of_installation` |
| `total_cooling_load` | `total_cooling_load_rt` |
| `baseline_efficiency` | `baseline_efficiency_w_cmh` |
| `operating_hours_per_day` | `operation_hours_per_workday` |
| `days_per_week` | `workdays_per_week` |
| `weeks_per_year` | `workweeks_per_year` |
| `total_energy_consumption` | `total_energy_consumption_kwh_per_year` |
| `number_of_units` | `number_of_units` |
| `total_system_power` | `total_system_power_kw` |
| `number_of_stars` | `energy_efficiency_label` |

---

## 5. Cooling System

### Overview
The Cooling System is **more complex** than other systems as it handles **TWO separate system types**:
1. **Chiller Systems** (water-cooled or air-cooled)
2. **Air Conditioner Systems** (VRV or split)

### API Endpoints

#### Create/Update Cooling System
- **Endpoint**: `/cooling-system/`
- **Methods**: POST (create), PUT (update)
- **Request Body** (Chiller):
```json
{
  "building_id": "uuid-string",
  "cooling_system_id": 123,  // Optional, for updates only
  "cooling_system_type": "chiller",
  "chiller_system": "water-cooled",
  "year_of_installation": 2020,
  "type_of_refrigerants": "R-134a",
  "refrigerant_quantity": 100,
  "installation_of_variable_speed_drives": "yes",
  "installation_of_heat_recovery_systems": "no",
  "total_chiller_system": 500,
  "baseline_leakage_factor": 2,
  "number_of_chillers": 2,
  "annual_operating_hours_per_day": 10,
  "annual_operating_days_per_week": 5,
  "annual_operating_weeks_per_year": 50
}
```

- **Request Body** (Air Conditioner):
```json
{
  "building_id": "uuid-string",
  "cooling_system_id": 123,  // Optional, for updates only
  "cooling_system_type": "air_conditioner",
  "type_of_air_condition": "vrv",
  "year_of_installation": 2021,
  "type_of_refrigerants": "R-410A",
  "refrigerant_quantity": 50,
  "total_cooling_load_for_split_vrv": 300,
  "baseline_leakage_factor": 2,
  "number_of_split_vrv_units": 10,
  "hours_per_day": 8,
  "days_per_week": 5,
  "weeks_per_year": 50
}
```

#### Get Cooling Systems
- **Endpoint**: `/cooling-system/<building_id>/`
- **Method**: GET
- **Response**: Array containing both chiller and AC systems

#### Delete Cooling System
- **Endpoint**: `/cooling-system/<system_id>/delete/?cooling_system_type=<type>`
- **Method**: DELETE
- **Query Parameter**: `cooling_system_type` (required: "chiller" or "air_conditioner")

### Frontend Implementation

**File**: `templates/pages/add-building/components/operational-details/cooling-system.html`

**Key Features**:
- **Dynamic template loading** based on selected cooling system type
- Separate field sets for chiller vs air conditioner
- Type parameter required for delete operations

**Key Functions**:
```javascript
// Handle system type change (loads appropriate template)
window.handleCoolingSystemTypeChange = function(systemType) {
  const selectedText = systemType.options[systemType.selectedIndex].text;

  if (selectedText.toLowerCase().includes('chiller')) {
    loadTemplate('chiller-system-template', selectedSystemDiv);
  } else {
    loadTemplate('air-condition-system-template', selectedSystemDiv);
  }
}

// Save system (includes cooling_system_type)
window.saveCoolingSystem = async function() {
  const systemData = {
    building_id: buildingId,
    cooling_system_id: window.editingCoolingSystemId,
    cooling_system_type: determineSystemType(), // "chiller" or "air_conditioner"
    // ... type-specific fields
  };
}

// Delete requires type parameter
window.deleteCoolingSystem = async function(systemId, systemType) {
  const response = await fetch(
    `/cooling-system/${systemId}/delete/?cooling_system_type=${systemType}`,
    {
      method: 'DELETE',
      headers: { 'X-CSRFToken': getCSRFToken() },
    }
  );
}
```

### Field Mapping - Chiller Systems

| Frontend Field Name | Backend Model Field |
|---------------------|---------------------|
| `chiller_system` | `chiller_type` |
| `type_of_refrigerants` | `refrigerant_type` |
| `refrigerant_quantity` | `refrigerant_quantity_kg` |
| `installation_of_variable_speed_drives` | `variable_speed_drives` (boolean) |
| `installation_of_heat_recovery_systems` | `heat_recovery_system` (boolean) |
| `total_chiller_system` | `total_cooling_load_rt` |
| `baseline_leakage_factor` | `baseline_leakage_factor_percent` |
| `annual_operating_hours_per_day` | `operation_hours_per_workday` |
| `annual_operating_days_per_week` | `workdays_per_week` |
| `annual_operating_weeks_per_year` | `workweeks_per_year` |
| `baseline_cooling_efficiency` | `baseline_cooling_efficiency_kw_h` |
| `total_chiller_system_power_input` | `total_chiller_system_power_input_kw` |
| `water_cooled_chiller_cooling_load_factor` | `water_cooled_chiller_cooling_load_factor_percent` |
| `ipvl` | `ip_lv` |
| `number_of_stars` | `energy_efficiency_label` |

### Field Mapping - Air Conditioner Systems

| Frontend Field Name | Backend Model Field |
|---------------------|---------------------|
| `type_of_air_condition` | `ac_type` |
| `hours_per_day` | `operation_hours_per_workday` |
| `days_per_week` | `workdays_per_week` |
| `weeks_per_year` | `workweeks_per_year` |
| `type_of_refrigerants` | `refrigerant_type` |
| `refrigerant_quantity` | `refrigerant_quantity_kg` |
| `total_cooling_load_for_split_vrv` | `total_cooling_load_rt` |
| `baseline_split_unit_system_efficiency` | `baseline_efficiency_kw_per_rt` |
| `baseline_leakage_factor` | `baseline_leakage_factor_percent` |
| `total_energy_consumption_of_split_vrv_annually` | `total_energy_consumption_kwh_per_year` |
| `number_of_split_vrv_units` | `number_of_units` |
| `total_split_unit_system_power` | `total_system_power_kw` |
| `iseer` | `iseer_rating` |
| `number_of_stars` | `energy_efficiency_label` |

---

## Common Patterns Across All Systems

### 1. CSRF Token Handling
All POST, PUT, and DELETE requests require CSRF token:
```javascript
function getCSRFToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]').value;
}
```

### 2. Error Handling
All API responses follow this format:
```json
// Success
{
  "success": true,
  "message": "System created successfully.",
  "system_data": { /* system object */ }
}

// Failure
{
  "success": false,
  "errors": {
    "field_name": ["Error message"]
  }
}
```

### 3. Edit Mode
Track the system being edited with a global variable:
```javascript
window.editingSystemId = null;  // null for create, ID for update
```

### 4. Form Data Collection
Use FormData API for collecting form values:
```javascript
const form = document.getElementById('systemForm');
const formData = new FormData(form);
```

### 5. Boolean Conversion (Chiller Systems)
The backend accepts "yes"/"no" strings and converts them to boolean:
- Frontend sends: `"yes"` or `"no"`
- Backend converts to: `true` or `false`

---

## Testing

Each system has comprehensive tests covering:
- Model creation and validation
- Cascade delete (systems deleted when building is deleted)
- API endpoint functionality (create, read, update, delete)
- Form validation and field mapping
- User permissions (can only access own buildings)

Test files location: `pages/tests/test_<system>_system.py`

Run tests:
```bash
pytest pages/tests/test_hot_water_system.py -v
pytest pages/tests/test_lift_escalator_system.py -v
pytest pages/tests/test_lighting_system.py -v
pytest pages/tests/test_ventilation_system.py -v
pytest pages/tests/test_cooling_system.py -v
```

---

## Backend Files Structure

```
pages/
├── forms/
│   ├── hot_water_system_form.py
│   ├── lift_escalator_system_form.py
│   ├── lighting_system_form.py
│   ├── ventilation_system_form.py
│   └── cooling_system_form.py
├── views/building/
│   ├── hot_water_system.py
│   ├── lift_escalator_system.py
│   ├── lighting_system.py
│   ├── ventilation_system.py
│   └── cooling_system.py
├── models/building_operation/
│   └── (model definitions)
└── tests/
    ├── test_hot_water_system.py
    ├── test_lift_escalator_system.py
    ├── test_lighting_system.py
    ├── test_ventilation_system.py
    └── test_cooling_system.py
```

---

## Migration Notes

If you're migrating from session-based storage to direct DB persistence:

1. **Remove** all session storage code:
   ```javascript
   // OLD - Remove this
   sessionStorage.setItem('systems', JSON.stringify(systems));

   // NEW - Fetch from API
   const response = await fetch(`/system-endpoint/${buildingId}/`);
   ```

2. **Update** save handlers to use fetch API

3. **Add** CSRF token to all mutation requests

4. **Handle** async operations with proper error handling

5. **Test** thoroughly with browser DevTools Network tab

---

## Troubleshooting

### Common Issues

1. **CSRF Token Missing**
   - Ensure `getCSRFToken()` function is available
   - Check that CSRF token input exists in the template

2. **404 on API Calls**
   - Verify URL patterns in `pages/urls.py`
   - Check building_id/system_id are valid UUIDs/integers

3. **400 Bad Request**
   - Check field name mapping matches backend expectations
   - Validate required fields are present
   - Ensure data types are correct (int, float, string)

4. **Permission Denied (403/404)**
   - Verify user owns the building
   - Check login status

5. **Cooling System Type Errors**
   - Ensure `cooling_system_type` parameter is included
   - For deletes, verify query parameter is present

---

## Best Practices

1. **Always validate form data** before sending to API
2. **Provide user feedback** (loading states, success/error messages)
3. **Handle network errors** gracefully
4. **Use consistent naming** between frontend and backend
5. **Test with various data types** and edge cases
6. **Clear edit mode** after save/cancel
7. **Refresh system list** after create/update/delete operations

---

## Support

For questions or issues:
- Review test files for usage examples
- Check Django server logs for detailed error messages
- Use browser DevTools to inspect network requests/responses