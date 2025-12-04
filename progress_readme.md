# PROGRESS README

# Select Lists API Documentation

## 📋 Extended Select Lists Endpoint

The `/select_lists/` endpoint now provides comprehensive options for all building-related select fields.

## 🚀 Available Endpoints

### Geographic Data

```
GET /select_lists/?country=<id>         # Get regions for country
GET /select_lists/?region=<id>          # Get cities for region
```

### Material Categories

```
GET /select_lists/?category=<id>        # Get material subcategories
GET /select_lists/?subcategory=<id>     # Get child categories
GET /select_lists/?assembly_category=<id> # Get assembly techniques
```

### Building Types

```
GET /select_lists/?building_categories=1   # Get all building categories
GET /select_lists/?building_category=<id> # Get apartment types
```

### System Types

```
GET /select_lists/?climate_zones=1        # Get climate options
GET /select_lists/?heating_types=1        # Get heating systems
GET /select_lists/?cooling_types=1        # Get cooling systems
GET /select_lists/?ventilation_types=1    # Get ventilation systems
GET /select_lists/?lighting_types=1       # Get lighting types
```

### Unit Types

```
GET /select_lists/?temperature_units=1    # °C, °F
GET /select_lists/?power_units=1         # kW
GET /select_lists/?cooling_capacity_units=1 # kW, TR
GET /select_lists/?airflow_units=1       # m³/h, CFM
```

---

# Multi-Step Building Creation Flow

## 📁 File: `pages/views/building/add_building_steps.py`

### Overview

Handles the multi-step building creation wizard with session-based data persistence. Supports dynamic template loading and step-by-step data collection for building setup.

### Main View Function

#### `building_step_view(request)`

**Method**: GET  
**Authentication**: Required (`@login_required`)

Routes to appropriate step handler based on `step` query parameter.

**Request Example**:

```
GET /building-step/?step=building-information/building-name-location.html
```

**Response**: Renders the requested step template with context data.

### Step Handlers

#### Step 1: Building Information

- **1.1 `handle_name_location_step`**: Provides ALCBT countries for location selection
- **1.2 `handle_details_step`**: Provides building categories and types

#### Step 2: Operational Details (6 sub-steps)

- **2.1 `handle_schedule_temp_step`**: Operational schedule and temperature settings
- **2.2 `handle_cooling_system_step`**: Cooling system configuration
- **2.3 `handle_ventilation_system_step`**: Ventilation system configuration
- **2.4 `handle_lighting_system_step`**: Lighting system configuration
- **2.5 `handle_lift_escalator_step`**: Lift and escalator system configuration
- **2.6 `handle_hot_water_step`**: Hot water system configuration

#### Step 3: Operational Data Entry

- **`handle_operational_data_step`**: Energy carrier data entry

#### Step 4: Building Structural Components

- **`handle_structural_components_step`**: Assembly/component selection

### Data Management Functions

#### `save_building_step(request)`

**Method**: POST  
**Authentication**: Required

Saves step data to session storage.

**Request Body**:

```json
{
  "step_key": "building-information",
  "data": {
    "name": "Example Building",
    "country": 1
  }
}
```

**Response**:

```json
{
  "success": true,
  "message": "Step data saved successfully"
}
```

#### `get_building_step_data(request)`

**Method**: GET  
**Authentication**: Required

Retrieves previously saved step data from session.

**Request Example**:

```
GET /building-step-data/?step_key=building-information
```

**Response**:

```json
{
  "success": true,
  "data": {
    "name": "Example Building",
    "country": 1
  }
}
```

#### `complete_building_setup(request)`

**Method**: POST  
**Authentication**: Required

Finalizes building creation by combining all step data.

**Response**:

```json
{
  "success": true,
  "message": "Building created successfully",
  "redirect_url": "/dashboard/"
}
```

### Session Storage Structure

All step data is stored in `request.session["building_form_data"]`:

```python
{
  "building-information": {...},
  "operational-details": {...},
  "operational-data": {...},
  "structural-components": {...}
}
```

### Template Mapping

Templates are located at: `templates/pages/add-building/components/`

**Structure**:

- `building-information/`
  - `building-name-location.html`
  - `building-details.html`
- `operational-details/`
  - `operational-schedule-temperature.html`
  - `cooling-system.html`
  - `ventilation-system.html`
  - `lighting-system.html`
  - `lift-escalator-system.html`
  - `hot-water-system.html`
- `operational-data-entry/`
  - `operational-data-entry.html`
- `building-structural-components/`
  - `building-structural-components.html`

### Error Handling

- **400**: Missing required parameters (`step`, `step_key`, `data`)
- **404**: Unknown step template
- **500**: JSON parsing errors or unexpected exceptions

### Future Implementation

The `complete_building_setup` function has a TODO for creating actual Building and BuildingOperationalInfo model instances from the collected session data.

---

# Static Assets Structure

## 📁 Folder: `static/`

### Overview

Contains all static assets for the HEAT application including CSS, JavaScript, images, and icons. Files are served using Django's static files system (via WhiteNoise in production).

### Directory Structure

#### `assets/`

- **`icons/`**: SVG icon files for the application UI

#### `css/`

Core stylesheets for the application:

- **`base.css`**: Base application styles and global CSS rules
- **`bootstrap.min.css`**: Bootstrap CSS framework (minified) (to be removed)
- **`bootstrap-icons.min.css`**: Bootstrap icon font styles (to be removed)
- **`cookie-consent.css`**: Cookie consent banner styling (to be removed or replaced)
- **`home.css`**: Homepage-specific styles (to be removed)
- **`output.css`**: Compiled TailwindCSS output (auto-generated from `app.css`)
- **`resources.css`**: Resources page styling (to be removed)
- **`fonts/`**: Custom web font files
- **`account/`**: Account-related page styles
  - `signup.css`: Signup page styling

#### `images/`

Image assets organized by category:

- **`backgrounds/`**: Background images for pages and components
- **`logos/`**: Logo files organized by partner type
  - `development_partners/`: Development partner logos
  - `lead_partners/`: Lead partner logos
- **`svg/`**: SVG graphic files

#### `js/`

JavaScript files for client-side functionality:

- **`base.js`**: Core JavaScript utilities and base functionality
- **`bootstrap.bundle.min.js`**: Bootstrap JavaScript (minified with Popper.js) (to be removed)
- **`countries-registry.js`**: Country selection and management utilities
- **`geo-location.js`**: Geolocation and geocoding functionality
- **`icons-registry.js`**: Auto-generated icon registry (from `build-icons.mjs`)
- **`icons.js`**: Icon rendering and utility functions
- **`step-manager.js`**: Multi-step form state management (building creation wizard)
- **`htmx1.6.1/`**: HTMX library for dynamic HTML updates
  - `htmx.min.js`: HTMX core library (v1.6.1)

### Key Files

#### Auto-Generated Files

These files are generated by build processes and should NOT be edited directly:

- **`css/output.css`**: Generated by PostCSS from `app.css` (source in project root)
- **`js/icons-registry.js`**: Generated by `build-icons.mjs` from SVG files in `assets/icons/`

#### Build Sources

Source files are in the project root:

- `app.css` → compiles to → `static/css/output.css`
- `build-icons.mjs` → generates → `static/js/icons-registry.js`

### CSS Framework Stack

The application uses multiple CSS frameworks:

1. **Bootstrap 5**: Component library and grid system (to be removed)
2. **TailwindCSS + DaisyUI**: Utility-first CSS (compiled to `output.css`)
3. **Custom CSS**: Page-specific styles in individual CSS files

### JavaScript Libraries

- **Bootstrap 5.x**: Component interactions and utilities
- **HTMX 1.6.1**: AJAX requests and dynamic content loading
- **Custom modules**: Step management, geolocation, icon rendering
