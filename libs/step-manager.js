
// @ts-check
class StepManager {

  editMode = false;
  isPopStateNavigation = false;

  constructor() {
    this.currentStep = 1;
    this.currentSubStep = 1;
    this.totalSteps = 4;
    this.editMode = window.location.pathname.includes('/building/edit');

    if(this.editMode){
      document.getElementById('page-title').textContent = gettext('Edit Building Information');
      document.getElementById('page-description').textContent = gettext('Update the building information as needed.');
    }


    // Weighted progress: Building Info 20%, Operational Data 30%, Structural 40%, Systems 10%
    // System sub-steps (cooling/ventilation/lighting/lift/hot-water) each carry 2% (5×2=10%)
    // Schedule + energy-summary + data-entry each carry 10% (3×10=30%)
    // Building info sub-steps each carry 10% (2×10=20%)
    // Structural carries 40%
    this.stepConfig = {
      1: {
        name: gettext("Building Information"),
        id: "building-information",
        subSteps: [
          {
            id: "building-name-location",
            name: gettext("Building Name & Location"),
            weight: 10,
            component: "building-information/building-name-location.html",
            requiredFields: ["building_name", "address", "country"],
            title: gettext("Building Name & Location"),
            description: gettext("Add details concerning building name and locations of building."),
          },
          {
            id: "building-details",
            name: gettext("Building Details"),
            weight: 10,
            component: "building-information/building-details.html",
            requiredFields: ["building_type", "assessment_period", "total_floor_area"],
            title: gettext("Building Details"),
            description: gettext("Add detailed information about your building."),
          },
        ],
      },
      2: {
        name: gettext("Operational Details"),
        id: "operational-details",
        subSteps: [
          {
            id: "operational-schedule-temperature",
            name: gettext("Operational Schedule & Temperature"),
            weight: 10,
            component:
              "operational-details/operational-schedule-temperature.html",
            requiredFields: ["operating_hours", "default_temperature"],
            title: gettext("Operational Schedule & Temperature"),
            description: gettext("Complete field below to add operations information about your building."),
          },
          {
            id: "cooling-system",
            name: gettext("Cooling System"),
            weight: 2,
            component: "operational-details/cooling-system.html",
            requiredFields: ["cooling_system_type"],
            title: gettext("Cooling System"),
            description: gettext("Enter details of the building's cooling system, including type and capacity."),
          },
          {
            id: "ventilation-system",
            name: gettext("Ventilation System"),
            weight: 2,
            component: "operational-details/ventilation-system.html",
            requiredFields: ["ventilation_type"],
            title: gettext("Ventilation System"),
            description: gettext("Provide details on the building,s ventilation type, capacity, and coverage to assess airflow and indoor air quality."),
          },
          {
            id: "lighting-system",
            name: gettext("Lighting System"),
            weight: 2,
            component: "operational-details/lighting-system.html",
            requiredFields: ["lighting_type"],
            title: gettext("Lighting System"),
            description: gettext("Provide details on lighting types, power use, and controls to assess efficiency."),
          },
          {
            id: "lift-escalator-system",
            name: gettext("Lift & Escalator System"),
            weight: 2,
            component: "operational-details/lift-escalator-system.html",
            requiredFields: [],
            title: gettext("Lift & Escalator System"),
            description: gettext("Provide details on lift & escalator systems in your building if any."),
          },
          {
            id: "hot-water-system",
            formId: "hot-water-system",
            name: gettext("Hot Water System"),
            weight: 2,
            component: "operational-details/hot-water-system.html",
            requiredFields: ["hot_water_type"],
            title: gettext("Hot Water System"),
            description: gettext("Defines the building's method of producing and distributing hot water, including equipment type, energy source, and usage patterns."),
          },
          {
            id: "energy-consumption-summary",
            name: gettext("Energy Consumption Summary"),
            weight: 10,
            component: "operational-details/energy-consumption-summary.html",
            requiredFields: [],
            title: gettext("Energy Consumption Summary"),
            description: gettext(
              "Review annual energy consumed by each building system. Values auto-calculated from system sheets above. If only energy bill data is available, enter values manually here."
            ),
          },
        ],
      },
      3: {
        name: gettext("Operational Data Entry"),
        id: "operational-data-entry",
        subSteps: [
          {
            id: "operational-data-entry",
            name: gettext("Data Entry"),
            weight: 10,
            component: "operational-data-entry/operational-data-entry.html",
            requiredFields: ["energy_consumption"],
            title: gettext("Annual Operational Energy Carriers"),
            description: gettext("Tell us what fuels or energy sources your building runs on annually."),
          },
        ],
      },
      4: {
        name: gettext("Building Structural Components"),
        id: "building-structural-components",
        subSteps: [
          {
            id: "building-structural-components",
            name: gettext("Structural Components"),
            weight: 40,
            component:
              "building-structural-components/building-structural-components.html",
            requiredFields: ["foundation_type", "structure_type"],
            title: gettext("Building Structural Components"),
            description: gettext("Enter information about the building's walls, floors, roofs, and other structural parts."),
          },
        ],
      },
    };

    // Store form data
     
    /** @type {Record<string, Record<string, any>>} */
    this.formData = {};

    // Store form validation status for each step
    this.formValidationStatus = {};

    this.init();
  }

  init() {
    this.initUrlNavigation();
    this.renderStepNavigation();
    this.updateCurrentStepInfo();
    this.loadCurrentStep();
    this.updateProgress();
    this.bindEvents();
  }

  bindEvents() {
    // Bind navigation buttons
    const goBackBtn = document.getElementById("go-back");
    const skipBtn = document.getElementById("skip");
    const saveAndContinueBtn = document.getElementById("save-and-continue");

    if (goBackBtn) {
      goBackBtn.addEventListener("click", () => this.goBack());
    }

    if (skipBtn) {
      skipBtn.addEventListener("click", () => this.skip());
    }

    if (saveAndContinueBtn) {
      saveAndContinueBtn.addEventListener("click", () =>
        this.saveAndContinue()
      );
    }

    // Listen for custom form validation events
    document.addEventListener("onFormStatus", (event) => {
      this.handleFormStatusChange(event.detail);
    });

    // Update button states when form inputs change (fallback)
    document.addEventListener("input", () => {
      this.updateButtonStates();
    });

    document.addEventListener("change", () => {
      this.updateButtonStates();
    });
  }

  // ========== URL Navigation Methods ==========

  /**
   * Initialize URL-based navigation
   * Parses URL params and binds popstate handler
   */
  initUrlNavigation() {
    const urlParams = this.parseUrlParams();

    // Restore step from URL if valid
    if (urlParams.step && urlParams.substep) {
      const resolved = this.resolveStepFromIds(urlParams.step, urlParams.substep);
      if (resolved) {
        // Validate access - can't skip to later steps without building_uuid in create mode
        if (!this.editMode && !urlParams.building_uuid && resolved.step > 1) {
          console.warn('Cannot access this step without creating a building first');
          this.currentStep = 1;
          this.currentSubStep = 1;
        } else {
          this.currentStep = resolved.step;
          this.currentSubStep = resolved.subStep;
        }
      } else {
        console.warn(`Invalid step params: step=${urlParams.step}, substep=${urlParams.substep}`);
      }
    }

    // Bind popstate handler for browser back/forward
    window.addEventListener('popstate', (event) => this.handlePopState(event));

    // Set initial history state
    this.updateUrl({ replaceState: true });
  }

  /**
   * Parse URL query parameters
   * @returns {{ step: string|null, substep: string|null, building_uuid: string|null }}
   */
  parseUrlParams() {
    const params = new URLSearchParams(window.location.search);
    return {
      step: params.get('step'),
      substep: params.get('substep'),
      building_uuid: params.get('building_uuid')
    };
  }

  /**
   * Convert semantic step/substep IDs to numeric values
   * @param {string} stepId - The step ID (e.g., "building-information")
   * @param {string} subStepId - The substep ID (e.g., "building-name-location")
   * @returns {{ step: number, subStep: number }|null}
   */
  resolveStepFromIds(stepId, subStepId) {
    for (const [stepNum, config] of Object.entries(this.stepConfig)) {
      if (config.id === stepId) {
        const subStepIndex = config.subSteps.findIndex(s => s.id === subStepId);
        if (subStepIndex !== -1) {
          return {
            step: parseInt(stepNum),
            subStep: subStepIndex + 1
          };
        }
      }
    }
    return null;
  }

  /**
   * Convert numeric step/substep to semantic IDs
   * @param {number} step - The step number (1-4)
   * @param {number} subStep - The substep number (1-N)
   * @returns {{ stepId: string, subStepId: string }|null}
   */
  resolveIdsFromStep(step, subStep) {
    // @ts-ignore - stepConfig uses numeric keys
    const config = this.stepConfig[step];
    if (!config) return null;

    const subStepConfig = config.subSteps[subStep - 1];
    if (!subStepConfig) return null;

    return {
      stepId: config.id,
      subStepId: subStepConfig.id
    };
  }

  /**
   * Update browser URL with current step state
   * @param {{ pushState?: boolean, replaceState?: boolean }} options
   */
  updateUrl(options = {}) {
    const { pushState = false, replaceState = false } = options;

    const ids = this.resolveIdsFromStep(this.currentStep, this.currentSubStep);
    if (!ids) return;

    const url = new URL(window.location.href);

    // Set step params
    url.searchParams.set('step', ids.stepId);
    url.searchParams.set('substep', ids.subStepId);

    // Preserve building_uuid if it exists
    const buildingUuid = this.getBuildingId() ||
      this.formData['building-information/building-name-location']?.building_uuid;
    if (buildingUuid) {
      url.searchParams.set('building_uuid', buildingUuid);
    }

    // Store state for popstate handling
    const state = {
      step: this.currentStep,
      subStep: this.currentSubStep,
      building_uuid: buildingUuid || null
    };

    if (pushState) {
      window.history.pushState(state, '', url);
    } else if (replaceState) {
      window.history.replaceState(state, '', url);
    }
  }

  /**
   * Handle browser back/forward button navigation
   * @param {PopStateEvent} event
   */
  handlePopState(event) {
    this.isPopStateNavigation = true;

    if (event.state && typeof event.state.step === 'number' && typeof event.state.subStep === 'number') {
      // Use state from history entry
      this.currentStep = event.state.step;
      this.currentSubStep = event.state.subStep;
    } else {
      // Parse from URL (for manual URL changes or missing state)
      const urlParams = this.parseUrlParams();
      if (urlParams.step && urlParams.substep) {
        const resolved = this.resolveStepFromIds(urlParams.step, urlParams.substep);
        if (resolved) {
          this.currentStep = resolved.step;
          this.currentSubStep = resolved.subStep;
        } else {
          this.currentStep = 1;
          this.currentSubStep = 1;
        }
      } else {
        this.currentStep = 1;
        this.currentSubStep = 1;
      }
    }

    // Update UI without pushing new history
    this.renderStepNavigation();
    this.updateCurrentStepInfo();
    this.loadCurrentStep();
    this.updateProgress();

    this.isPopStateNavigation = false;
  }

  // ========== End URL Navigation Methods ==========

  handleFormStatusChange(statusData) {
    // statusData should contain: { isValid: boolean, stepKey?: string, data?: object }
    const currentStepKey = `step-${this.currentStep}-${this.currentSubStep}`;
    const stepKey = statusData.stepKey || currentStepKey;

    // Update validation status
    this.formValidationStatus[stepKey] = {
      isValid: statusData.isValid,
      timestamp: Date.now(),
      data: statusData.data || {},
    };

    // Update button states immediately
    this.updateButtonStates();

    // Optionally auto-save form data if provided
    if (statusData.data) {
      this.formData[stepKey] = {
        ...this.formData[stepKey],
        ...statusData.data,
      };
    }
  }

  renderStepNavigation() {
    const navigation = document.getElementById("step-navigation");
    if (!navigation) return;

    const stepperItems = [];

    Object.keys(this.stepConfig).forEach((stepNum, index) => {
      const step = this.stepConfig[stepNum];
      const stepNumber = parseInt(stepNum);
      const isActive = stepNumber === this.currentStep;
      const isCompleted = stepNumber < this.currentStep;

      // Generate sub-steps HTML
      const subStepsHTML = step.subSteps
        .map((subStep, subIndex) => {
          const subStepNum = subIndex + 1;
          const isSubActive = isActive && subStepNum === this.currentSubStep;
          const isSubCompleted =
            isCompleted || (isActive && subStepNum < this.currentSubStep);

          const icon = isSubCompleted
            ? `<input
              type="checkbox"
              class="checkbox checkbox-primary checkbox-xs rounded-full pointer-events-none"
              checked/>`
            : isSubActive
            ? `<span class="stepper-sub-item-active-dot"></span>`
            : "";

          return `
          <div class="stepper-sub-item${isSubActive ? " active" : ""}" onclick="stepManager.goToSubStep(${stepNum}, ${subStepNum})">
            ${icon}
            <span class="stepper-sub-item-text ${
              isSubActive ? "text-[var(--text--strong-950)]" : ""
            } ${
            isSubCompleted ? "text-[var(--text--strong-950)]" : ""
          }">${subStep.name}</span>
            <span data-icon="arrow-right-up-line" data-size="12"></span>
          </div>
        `;
        })
        .join("");

      // Create stepper item
      stepperItems.push(`
        <li class="stepper-item ${isActive ? "active" : ""} ${
        isCompleted ? "completed" : ""
      }">
          <div class="stepper-item-icon-container">
            ${
              isCompleted
                ? `<input
                type="checkbox"
                class="checkbox checkbox-primary checkbox-sm rounded-full pointer-events-none"
                checked/>`
                : isActive
                ? `<div class="stepper-item-icon stepper-item-icon--active">
                <span data-icon="alert-fill" data-size="12" data-color="var(--color-warning-content)"></span>
              </div>`
                : `<div class="stepper-item-icon"></div>`
            }
            <div class="stepper-item-line"></div>
          </div>
          <div class="stepper-item-content">
            <h3 class="stepper-item-title" onclick="stepManager.goToStep(${stepNum})">${
        step.name
      }</h3>
            ${step.subSteps.length > 1 ? subStepsHTML : ""}
          </div>
        </li>
      `);
    });

    navigation.innerHTML = `
      <ul class="stepper">
        ${stepperItems.join("")}
      </ul>
    `;
  }

  async loadCurrentStep() {
    const step = this.stepConfig[this.currentStep];
    const subStep = step.subSteps[this.currentSubStep - 1];
    const contentArea = document.getElementById("dynamic-content");

    if (!contentArea) return;

    // In add mode, guard any step beyond step 1 substep 1 when there is no building UUID.
    // This prevents accessing later steps without completing Name & Location first.
    // Check both URL and formData — after saving step 1 the UUID is stored in formData
    // before updateUrl() has had a chance to put it in the URL.
    const hasUuid = this.getBuildingId()
      || this.formData['building-information/building-name-location']?.building_uuid;
    const isNameLocationStep = this.currentStep === 1 && this.currentSubStep === 1;
    if (!this.editMode && !hasUuid && !isNameLocationStep) {
      contentArea.innerHTML = `
        <div class="flex flex-col items-center justify-center h-64 text-center gap-4">
          <div class="alert alert-warning max-w-md">
            <div>
              <p class="font-semibold">${gettext("No building found.")}</p>
              <p class="text-sm mt-1">${gettext("Please start by filling in the Building Name & Location, or go to an existing building to edit it.")}</p>
            </div>
          </div>
          <div class="flex gap-3">
            <a href="/building/_new" class="btn btn-primary btn-sm">${gettext("Create New Building")}</a>
            <a href="/" class="btn btn-outline btn-sm">${gettext("Go to Dashboard")}</a>
          </div>
        </div>
      `;
      return;
    }

    // Show loading state
    contentArea.innerHTML = `
      <div class="flex items-center justify-center h-64">
        <div class="loading loading-spinner loading-lg text-primary"></div>
      </div>
    `;

    try {
      // Use the new Django step view endpoint
      // Get building UUID from URL params first (covers refresh/shared links), then fall back to formData
      const buildingUuid = this.getBuildingId()
        || this.formData['building-information/building-name-location']?.building_uuid
        || '';
      const url = buildingUuid
        ? `/building/step?step=${subStep.component}&building_uuid=${buildingUuid}`
        : `/building/step?step=${subStep.component}`;

      // Update browser URL with current step and building_uuid (uses replaceState to avoid extra history entries)
      if (buildingUuid) {
        this.updateUrl({ replaceState: true });
      }

      const response = await fetch(url);

      // If the session expired, the server redirects to login.
      if (response.url && response.url.indexOf('/accounts/login/') !== -1) {
        window.location.href = '/accounts/login/?next=' + encodeURIComponent(window.location.pathname + window.location.search);
        return;
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const html = await response.text();
      contentArea.innerHTML = html;

      // Initialize icons for dynamically loaded content before scripts run
      // @ts-ignore - IconComponent is set globally by icons.js module
      if (window.IconComponent) { window.IconComponent.initialize(contentArea); }

      // Reset validation status for the new step (let the component re-validate)
      const currentStepKey = `step-${this.currentStep}-${this.currentSubStep}`;
      delete this.formValidationStatus[currentStepKey];

      // Restore form data if it exists
      this.restoreFormData();

      // Update button states
      this.updateButtonStates();

      // Process HTMX for dynamically loaded content
      if (typeof htmx !== 'undefined') {
        htmx.process(contentArea);
      }

      // Execute any inline scripts in the loaded content
      const scripts = contentArea.querySelectorAll('script');
      scripts.forEach(script => {
        const newScript = document.createElement('script');
        if (script.src) {
          newScript.src = script.src;
        } else {
          newScript.textContent = script.textContent;
        }
        document.body.appendChild(newScript);
        // Clean up script element after execution
        newScript.remove();
      });
    } catch (error) {
      console.error("Failed to load step component:", error);
      contentArea.innerHTML = `
        <div class="flex flex-col items-center justify-center h-64 text-center">
          <div class="alert alert-error max-w-md">
            <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h3 class="font-bold">Failed to load step content</h3>
              <div class="text-xs">Component: ${subStep.component}</div>
            </div>
          </div>
          <button onclick="stepManager.loadCurrentStep()" class="btn btn-primary mt-4">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Retry
          </button>
        </div>
      `;
    }
  }

  getBuildingId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('building_uuid');
  }
  
  updateProgress() {
    // Weighted progress: sum weights of completed sub-steps
    let completedWeight = 0;

    for (let i = 1; i < this.currentStep; i++) {
      for (const ss of this.stepConfig[i].subSteps) {
        completedWeight += (ss.weight || 0);
      }
    }
    // Count completed sub-steps within the current step (not including the active one)
    const currentStepSubSteps = this.stepConfig[this.currentStep].subSteps;
    for (let j = 0; j < this.currentSubStep - 1; j++) {
      completedWeight += (currentStepSubSteps[j].weight || 0);
    }

    const percentage = Math.min(100, completedWeight);

    const progressText = document.getElementById("progress-text");
    const progressBar = document.getElementById("progress-bar");

    if (progressText) {
      progressText.textContent = interpolate(gettext("%s% completed"), [percentage]);
    }

    if (progressBar) {
      progressBar.value = percentage;
    }
  }

  updateButtonStates() {
    const step = this.stepConfig[this.currentStep];
    const subStep = step.subSteps[this.currentSubStep - 1];
    const saveBtn = document.getElementById("save-and-continue");
    const goBackBtn = document.getElementById("go-back");
    const skipBtn = document.getElementById("skip");

    if (saveBtn) {
      const isValid = this.validateCurrentStep();
      saveBtn.disabled = false;

      // Update button text based on progress
      const isLastSubStep = this.currentSubStep === step.subSteps.length;
      const isLastStep = this.currentStep === this.totalSteps;

      if (isLastStep && isLastSubStep) {
        saveBtn.innerHTML = "<span>Complete Setup</span>";
      } else {
        saveBtn.innerHTML = "<span>Save & continue</span>";
      }
    }

    if (goBackBtn) {
      const isFirstSubStep = this.currentStep === 1 && this.currentSubStep === 1;
      // In add mode, disable Go Back on step 1 substep 2 (Building Details) —
      // once a building is created the user cannot go back to Name & Location.
      const hasUuid = this.getBuildingId()
        || this.formData['building-information/building-name-location']?.building_uuid;
      const isLockedOnBuildingDetails = !this.editMode && hasUuid &&
        this.currentStep === 1 && this.currentSubStep === 2;
      goBackBtn.disabled = isFirstSubStep || !!isLockedOnBuildingDetails;
    }

    if (skipBtn) {
      // In add mode: hide skip on step 1 substep 1 (Name & Location) and
      // step 1 substep 2 (Building Details) — both are unskippable.
      if (!this.editMode) {
        const isUnskippable = this.currentStep === 1;
        skipBtn.style.display = isUnskippable ? 'none' : '';
      } else {
        skipBtn.style.display = '';
      }
    }
  }

  validateCurrentStep() {
    const currentStepKey = `step-${this.currentStep}-${this.currentSubStep}`;

    // Check if we have validation status from the form component
    if (this.formValidationStatus[currentStepKey]) {
      return this.formValidationStatus[currentStepKey].isValid;
    }

    // Fallback: Check if there are any required fields defined
    const step = this.stepConfig[this.currentStep];
    const subStep = step.subSteps[this.currentSubStep - 1];

    if (!subStep.requiredFields || subStep.requiredFields.length === 0) {
      return true; // No required fields, consider valid
    }

    // Fallback validation: Check if all required fields are filled
    return subStep.requiredFields.every((fieldName) => {
      const field = document.querySelector(
        `[name="${fieldName}"], [data-field="${fieldName}"]`
      );
      if (!field) return false;

      const value =
        field.type === "checkbox" ? field.checked : field.value.trim();
      return value !== "" && value !== false;
    });
  }

  /**
   * @param {string} stepKey
   * @returns {Record<string, any>}
   */
  getFormData(stepKey) {
    // Handle structural components step
    if (stepKey === 'building-structural-components/building-structural-components') {
      if (typeof window.getStructuralFormData === 'function') {
        const structuralData = window.getStructuralFormData();
        if (!structuralData.boq_items?.length && !structuralData.component_items?.length) {
          Toast.error("Please add at least one BOQ or component.");
          throw new Error("No structural components found.");
        }
        return {
          building_uuid: this.getBuildingId(),
          structural_components: structuralData
        };
      }
      return { building_uuid: this.getBuildingId() };
    }

    if (stepKey === 'operational-data-entry/operational-data-entry'){
      console.log('[StepManager] Checking operational data entry');
      const productsList = document.getElementById('selected_op_products');
      const productItems = productsList?.querySelectorAll("li[id^='epd-']");
      console.log('[StepManager] Found product items:', productItems ? productItems.length : 0);

      if (!productItems || productItems.length === 0) {
        console.error('[StepManager] No product items found in #selected_op_products');
        Toast.error("Please add at least one energy carrier.");
        throw new Error("No operational products found.");
      }

      // Check if products are saved to database
      const form = document.getElementById('operational-products-form');
      console.log('[StepManager] Form found?', !!form);
      console.log('[StepManager] Form dataset.saved value:', form?.dataset?.saved);
      const isSaved = form && form.dataset.saved === 'true';
      console.log('[StepManager] Is saved?', isSaved);

      if (!isSaved) {
        // Products need to be saved - trigger the form submission
        console.log('[StepManager] Triggering save for operational products...');

        // Return a marker that tells saveToServer to use custom save logic
        return {
          _useCustomEndpoint: true,
          _customEndpoint: 'operational-products',
          _customFormId: 'operational-products-form',
          building_uuid: this.getBuildingId()
        };
      }

      // Products are already saved, just verify and continue
      console.log('[StepManager] Operational products already saved, continuing...');
      return {
        building_uuid: this.getBuildingId(),
        operational_data_saved: true
      };

    } else if (stepKey === 'building-information/building-details') {
      const form = document.getElementById("form");
      if (form) {
        const formData = new FormData(form);
        let validator = new window.FormValidator(form);
        let isValid = validator.validate();
        if (!isValid) {
          Toast.error("Please correct the errors in the form before proceeding.");
          throw new Error("Form validation failed.");
        }
        return {
          building_uuid: this.getBuildingId(),
          _useCustomEndpoint: true,
          _customEndpoint: 'building-details-files',
          ...Object.fromEntries(formData.entries())
        };
      }
      throw new Error("Form not found.");
    } else if (stepKey === 'operational-details/operational-schedule-temperature') {
      // For operational schedule, we need to call our custom save function
      // Return a marker that tells saveToServer to use custom logic
      const form = document.getElementById("form");
      if (form) {
        const formData = new FormData(form);
        let validator = new window.FormValidator(form);
        let isValid = validator.validate();
        if (!isValid) {
          Toast.error("Please correct the errors in the form before proceeding.");
          throw new Error("Form validation failed.");
        }
        return {
          building_uuid: this.getBuildingId(),
          _useCustomEndpoint: true,
          _customEndpoint: 'operational-schedule',
          ...Object.fromEntries(formData.entries())
        };
      }
      throw new Error("Form not found.");
    } else {
      const form = document.getElementById("form");
      if (form) {

        const formData = new FormData(form);
        let validator = new window.FormValidator(form);

        let isValid = validator.validate();
        if (!isValid) {
          Toast.error("Please correct the errors in the form before proceeding.");
          throw new Error("Form validation failed.");
        }
        return formData.entries ? Object.fromEntries(formData.entries()) : {};
      } else {
        const object = this.formData[stepKey] || {};
        return object;
      }
    }
    
  }

  /**
   * Save form data - returns the saved data or null if failed
   * @returns {Promise<Record<string, any> | null>}
   */
  async saveFormData() {
    const stepKey = this.getCurrentStepKey();
    const stepData = this.getFormData(stepKey);

    if(!stepData || Object.keys(stepData).length === 0){
      console.warn("No data to save for this step.");
      return null;
    }
    this.formData[stepKey] = stepData;

    // Save to server via Django
    return await this.saveToServer(stepKey, stepData);
  }

  /**
   * Save to server and return response with UUID
   * @param {string} stepKey
   * @param {Record<string, any>} stepData
   * @returns {Promise<{success: boolean, building_uuid?: string, error?: string}>}
   */
  async saveToServer(stepKey, stepData) {
    try {
      console.log('[StepManager] saveToServer called with stepKey:', stepKey);
      console.log('[StepManager] saveToServer stepData:', stepData);

      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

      // Handle custom endpoints (like operational schedule and operational products)
      if (stepData._useCustomEndpoint && stepData._customEndpoint) {
        console.log('[StepManager] Using custom endpoint:', stepData._customEndpoint);

        // Special handling for operational products - trigger the form submission
        if (stepData._customEndpoint === 'operational-products') {
          const formId = stepData._customFormId || 'operational-products-form';
          const form = document.getElementById(formId);

          if (!form) {
            console.error('[StepManager] Form not found:', formId);
            return { success: false, error: 'Form not found' };
          }

          console.log('[StepManager] Triggering form submission for operational products');

          // Use HTMX to submit the form and wait for response
          return new Promise((resolve) => {
            // Listen for the custom trigger event from server
            const handleSaved = () => {
              console.log('[StepManager] Operational products saved successfully');
              document.body.removeEventListener('operationalProductsSaved', handleSaved);
              resolve({ success: true, building_uuid: this.getBuildingId() });
            };

            document.body.addEventListener('operationalProductsSaved', handleSaved);

            // Trigger the form submission
            htmx.trigger(form, 'submit');

            // Timeout fallback
            setTimeout(() => {
              document.body.removeEventListener('operationalProductsSaved', handleSaved);
              console.warn('[StepManager] Save timeout, checking form state');
              const savedForm = document.getElementById(formId);
              if (savedForm?.dataset?.saved === 'true') {
                resolve({ success: true, building_uuid: this.getBuildingId() });
              } else {
                resolve({ success: false, error: 'Save timeout' });
              }
            }, 5000);
          });
        }

        // Handle building-details-files: save text fields via JSON, then upload files
        if (stepData._customEndpoint === 'building-details-files') {
          // Validate file uploads before proceeding
          if (typeof window.validateBuildingFiles === 'function') {
            if (!window.validateBuildingFiles()) {
              return { success: false, error: 'File validation failed' };
            }
          }

          const buildingUuid = this.getBuildingId();
          if (!buildingUuid) {
            return { success: false, error: 'Building UUID not found. Please complete step 1 first.' };
          }

          // 1. Save the text fields via the existing JSON endpoint
          const textData = { ...stepData };
          delete textData._useCustomEndpoint;
          delete textData._customEndpoint;
          delete textData._customFormId;
          // Strip file-only fields that can't be serialized as JSON
          delete textData.certification_file;
          delete textData.boq_files;
          // Strip radio fields handled by file upload endpoint
          // (has_certification and has_boq are saved by the file upload endpoint)
          delete textData.has_certification;
          delete textData.has_boq;

          const jsonPayload = {
            building_uuid: buildingUuid,
            step_key: 'building-information/building-details',
            data: { ...textData, building_uuid: buildingUuid }
          };

          const jsonResponse = await fetch('/building/step/save', {
            method: this.editMode ? 'PUT' : 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken || '' },
            body: JSON.stringify(jsonPayload)
          });
          const jsonResult = await jsonResponse.json();
          if (!jsonResponse.ok || !jsonResult.success) {
            return { success: false, error: jsonResult.error || 'Failed to save building details' };
          }

          // 2. Upload files via multipart endpoint
          if (typeof window.uploadBuildingFiles === 'function') {
            const uploadOk = await window.uploadBuildingFiles(buildingUuid);
            if (!uploadOk) {
              Toast.error('Failed to upload files. Please try again.');
              return { success: false, error: 'File upload failed' };
            }
          }

          return { success: true, building_uuid: buildingUuid };
        }

        // Handle other custom endpoints (like operational schedule)
        // Remove the markers from the data
        const cleanData = { ...stepData };
        delete cleanData._useCustomEndpoint;
        delete cleanData._customEndpoint;
        delete cleanData._customFormId;

        const response = await fetch(`/building/step/${stepData._customEndpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken || '',
          },
          body: JSON.stringify(cleanData)
        });

        const result = await response.json();
        console.log('[StepManager] Custom endpoint response:', result);

        if (!response.ok || !result.success) {
          console.error('[StepManager] Failed to save via custom endpoint:', result);
          return { success: false, error: result.error || 'Failed to save' };
        }

        return { success: true, building_uuid: this.getBuildingId() };
      }

      // Get building_uuid from URL params or from formData
      const urlParams = new URLSearchParams(window.location.search);
      const urlUuid = urlParams.get('building_uuid');
      const formUuid = this.formData['building-information/building-name-location']?.building_uuid;

      // Add building_uuid to stepData if it exists
      const dataWithUuid = {
        ...stepData,
        building_uuid: urlUuid || formUuid || stepData.building_uuid || ''
      };

      const payload = {
        building_uuid: this.getBuildingId(),
        step_key: stepKey,
        data: dataWithUuid
      };

      console.log('[StepManager] Sending payload to /building/step/save:', payload);

      const response = await fetch('/building/step/save', {
        method: this.editMode ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || '',
        },
        body: JSON.stringify(payload)
      });

      const result = await response.json();
      console.log('[StepManager] Server response:', result);

      if (!response.ok) {
        console.error('[StepManager] Failed to save step data to server:', result);
        return { success: false, error: result.error || 'Failed to save' };
      }

      // Store building_uuid if returned
      if (result.building_uuid) {
        if (!this.formData['building-information/building-name-location']) {
          this.formData['building-information/building-name-location'] = {};
        }
        this.formData['building-information/building-name-location'].building_uuid = result.building_uuid;
      }

      return { success: true, building_uuid: result.building_uuid };
    } catch (error) {
      console.error('Error saving to server:', error);
      return { success: false, error: error.message };
    }
  }

  async restoreFormData() {
    const stepKey = this.getCurrentStepKey();

    // Get UUID from URL if available
    const urlParams = new URLSearchParams(window.location.search);
    const buildingUuid = urlParams.get('building_uuid');

    // If we have a UUID, fetch data from server
    if (buildingUuid) {
      try {
        const response = await fetch(`/building/step/data?building_uuid=${buildingUuid}`);
        if (response.ok) {
          const result = await response.json();
          if (result.success && result.data) {
            // Store in formData for consistency
            this.formData['building-information/building-name-location'] = result.data;
            this.formData['building-information/building-name-location'].building_uuid = buildingUuid;
            this.formData['building-information/building-details'] = result.data;

            // Restore form fields
            Object.keys(result.data).forEach((key) => {
              const element = document.querySelector(
                `[name="${key}"], [data-field="${key}"]`
              );
              if (element && result.data[key]) {
                if (element.type === "checkbox") {
                  element.checked = result.data[key];
                } else {
                  element.value = result.data[key];
                }
              }
            });

            // For step 1.1, handle cascading dropdowns for region and city
            if (stepKey === 'building-information/building-name-location') {
              const regionSelect = document.getElementById('region-select');
              // Check if regions are already pre-populated by server (edit mode)
              const hasPrePopulatedRegions = regionSelect && regionSelect.options.length > 1;

              if (hasPrePopulatedRegions) {
                // Edit mode: server already populated regions/cities with correct selections
                // No HTMX cascade needed - just trigger form validation
                // console.log('Edit mode: regions/cities pre-populated by server');
              } else {
                // Create mode or fallback: use HTMX cascade logic
                setTimeout(() => {
                  const countrySelect = document.getElementById('country-select');
                  const citySelect = document.getElementById('city-select');

                  if (countrySelect && result.data.country && typeof htmx !== 'undefined') {
                    // Listen for when regions are loaded
                    const regionLoadHandler = (event) => {
                      if (event.detail.target === regionSelect && result.data.region) {
                        regionSelect.value = result.data.region;

                        // Now trigger city loading
                        htmx.trigger(regionSelect, 'change');

                        // Listen for when cities are loaded
                        const cityLoadHandler = (event) => {
                          if (event.detail.target === citySelect && result.data.city) {
                            citySelect.value = result.data.city;
                            document.body.removeEventListener('htmx:afterSwap', cityLoadHandler);
                          }
                        };
                        document.body.addEventListener('htmx:afterSwap', cityLoadHandler);

                        document.body.removeEventListener('htmx:afterSwap', regionLoadHandler);
                      }
                    };

                    document.body.addEventListener('htmx:afterSwap', regionLoadHandler);
                    htmx.trigger(countrySelect, 'change');
                  }
                }, 200);
              }
            }

            // For step 1.2, handle cascading dropdowns for apartment type and climate type
            if (stepKey === 'building-information/building-details') {
              const apartmentTypeSelect = document.getElementById('apartment-type-select');
              // Check if apartment_types are already pre-populated by server (edit mode)
              const hasPrePopulatedApartments = apartmentTypeSelect && apartmentTypeSelect.options.length > 1;

              if (hasPrePopulatedApartments) {
                // Edit mode: server already populated building_type/apartment_type/climate_type
                // No HTMX cascade needed - just trigger form validation
                // console.log('Edit mode: building details pre-populated by server');
              } else {
                // Create mode: use HTMX cascade logic
                setTimeout(() => {
                  const buildingTypeSelect = document.getElementById('building-type-select');
                  const climateTypeSelect = document.getElementById('climate-type-select');

                  // Trigger building type dropdown to load
                  if (buildingTypeSelect && typeof htmx !== 'undefined') {
                    htmx.trigger(buildingTypeSelect, 'load');
                  }

                  // Trigger climate type dropdown to load
                  if (climateTypeSelect && typeof htmx !== 'undefined') {
                    htmx.trigger(climateTypeSelect, 'load');

                    // Wait for it to load then set value
                    const climateLoadHandler = (event) => {
                      if (event.detail.target === climateTypeSelect && result.data.climate_type) {
                        setTimeout(() => {
                          climateTypeSelect.value = result.data.climate_type;
                        }, 50);
                        document.body.removeEventListener('htmx:afterSwap', climateLoadHandler);
                      }
                    };
                    document.body.addEventListener('htmx:afterSwap', climateLoadHandler);
                  }

                  // Handle apartment type after building type loads
                  if (buildingTypeSelect && result.data.building_type) {
                    const buildingTypeLoadHandler = (event) => {
                      if (event.detail.target === buildingTypeSelect) {
                        setTimeout(() => {
                          buildingTypeSelect.value = result.data.building_type;

                          // Trigger apartment type loading
                          if (apartmentTypeSelect && result.data.apartment_type) {
                            const apartmentLoadHandler = (event) => {
                              if (event.detail.target === apartmentTypeSelect) {
                                setTimeout(() => {
                                  apartmentTypeSelect.value = result.data.apartment_type;
                                }, 100);
                                document.body.removeEventListener('htmx:afterSwap', apartmentLoadHandler);
                              }
                            };
                            document.body.addEventListener('htmx:afterSwap', apartmentLoadHandler);

                            // Trigger the change event to load apartment types
                            htmx.trigger(buildingTypeSelect, 'change');
                          }
                        }, 100);

                        document.body.removeEventListener('htmx:afterSwap', buildingTypeLoadHandler);
                      }
                    };
                    document.body.addEventListener('htmx:afterSwap', buildingTypeLoadHandler);
                  }
                }, 300);
              }
            }
          }
        }else {
          Toast.error("Failed to fetch building data from server.");

          setTimeout(() => {
            history.back();
          }, 2000);

        }
      } catch (error) {
        console.error('Error fetching building data:', error);
      }
    }
  }

  updateCurrentStepInfo() {
    const currentStepInfo = this.getCurrentStepInfo();
    const currentStepTitle = document.getElementById("current-step-title");
    const currentStepDescription = document.getElementById(
      "current-step-description"
    );
    const currentStepProgress = document.getElementById(
      "current-step-progress"
    );

    // Hide current step progress if sub step is 1
    if (this.stepConfig[this.currentStep].subSteps.length === 1) {
      currentStepProgress.style.display = "none";
    } else {
      currentStepProgress.style.display = "flex";

      currentStepProgress.innerHTML = `
        <span class="text-[0.813rem]/5 font-semibold align-middle"
          >${interpolate(gettext("%s out of"), [this.currentSubStep])}
          <span class="font-normal text-[var(--text--sub-600)]"
            >${interpolate(gettext("%s steps"), [this.stepConfig[this.currentStep].subSteps.length])}</span
          ></span
        >
      `;
    }

    if (currentStepTitle) {
      currentStepTitle.textContent = currentStepInfo.title;
    }

    if (currentStepDescription) {
      currentStepDescription.textContent = currentStepInfo.description;
    }
  }

  
  goToStep(step) {
    const targetStep = parseInt(step);
    // In add mode, once a building is created, step 1 substep 1 (Name & Location) is locked.
    // Clicking step 1 in the nav would land on substep 1, so block it entirely.
    const hasUuid = this.getBuildingId()
      || this.formData['building-information/building-name-location']?.building_uuid;
    if (!this.editMode && hasUuid && targetStep === 1) {
      return;
    }
    this.currentStep = targetStep;
    this.currentSubStep = 1;
    this.renderStepNavigation();
    this.updateCurrentStepInfo();
    this.loadCurrentStep();
    this.updateProgress();
    this.updateUrl({ pushState: true });
  }

  goToSubStep(step, subStep) {
    const targetStep = parseInt(step);
    const targetSubStep = parseInt(subStep);
    // In add mode, once a building is created, step 1 substep 1 (Name & Location) is locked.
    const hasUuid = this.getBuildingId()
      || this.formData['building-information/building-name-location']?.building_uuid;
    if (!this.editMode && hasUuid && targetStep === 1 && targetSubStep === 1) {
      return;
    }
    this.currentStep = targetStep;
    this.currentSubStep = targetSubStep;
    this.renderStepNavigation();
    this.updateCurrentStepInfo();
    this.loadCurrentStep();
    this.updateProgress();
    this.updateUrl({ pushState: true });
  }

  async _checkEnergyMismatch() {
    const buildingUuid = this.getBuildingId();
    if (!buildingUuid) return null;
    try {
      const [summaryResp, carrierResp] = await Promise.all([
        fetch(`/building/energy-summary/?building_uuid=${buildingUuid}`),
        fetch(`/building/${buildingUuid}/total-kwh/`)
      ]);
      const summaryData = await summaryResp.json();
      const carrierData = await carrierResp.json();
      const systemsTotal = parseFloat(summaryData?.summary?.total_kwh) || 0;
      const carriersTotal = parseFloat(carrierData?.total_kwh) || 0;
      if (systemsTotal === 0 && carriersTotal === 0) return null;
      const diff = Math.abs(systemsTotal - carriersTotal);
      const tolerance = Math.max(2000, systemsTotal * 0.05);
      if (diff > tolerance) {
        return { systemsTotal, carriersTotal, diff };
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  async saveAndContinue(skipSave = false) {
    // Energy mismatch check before saving Operational Data Entry
    const stepKey = this.getCurrentStepKey();
    if (stepKey === 'operational-data-entry/operational-data-entry') {
      const mismatch = await this._checkEnergyMismatch();
      if (mismatch) {
        const sysKwh = Math.round(mismatch.systemsTotal).toLocaleString();
        const carKwh = Math.round(mismatch.carriersTotal).toLocaleString();
        let errorEl = document.getElementById('energy-mismatch-error');
        if (!errorEl) {
          errorEl = document.createElement('div');
          errorEl.id = 'energy-mismatch-error';
          errorEl.className = 'flex items-start gap-2 p-3 rounded-lg bg-[var(--state--error--lighter)] text-sm text-[var(--state--error--base)] mt-3';
          const content = document.getElementById('energy_carrier_template_container');
          if (content) content.parentNode.insertBefore(errorEl, content.nextSibling);
        }
        errorEl.innerHTML = `<span data-icon="alert-fill" data-size="16" data-color="var(--state--error--base)"></span>
          <span>${gettext("The total energy from your building systems")} (${sysKwh} kWh) ${gettext("does not match the total from your energy carriers")} (${carKwh} kWh). ${gettext("Please reconcile both before continuing.")}</span>`;
        if (typeof window.Icons !== 'undefined') window.Icons.render(errorEl);
        errorEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        return;
      } else {
        const errorEl = document.getElementById('energy-mismatch-error');
        if (errorEl) errorEl.remove();
      }
    }

    // Save current form data and wait for completion
    if(!skipSave){
      const saveResult = await this.saveFormData();

      // Check if save failed
      if (saveResult && !saveResult.success) {
        // Show error message
        Toast.error(`Failed to save: ${saveResult.error || 'Unknown error'}`);
        return; // Don't proceed to next step
      }

      if (saveResult && saveResult.success) {
        const isFirstStep = this.currentStep === 1 && this.currentSubStep === 1;
        if (!this.editMode && isFirstStep) {
          Toast.success(gettext('Building created successfully!'));
        } else {
          Toast.success(gettext('Building updated successfully!'));
        }
      }
    }
    const step = this.stepConfig[this.currentStep];

    if (this.currentSubStep < step.subSteps.length) {
      // Move to next substep
      this.currentSubStep++;
    } else if (this.currentStep < this.totalSteps) {
      // Move to next step
      this.currentStep++;
      this.currentSubStep = 1;
    } else {
      // Completed all steps
      this.completeSetup();
      return;
    }

    this.renderStepNavigation();
    this.updateCurrentStepInfo();
    this.loadCurrentStep();
    this.updateProgress();
    this.updateUrl({ pushState: true });
  }

  async goBack() {
    // Skip confirmation dialog if triggered by browser back/forward
    if (!this.isPopStateNavigation) {
      const response = await confirmDialog.warning("Are you sure you want to go back? Unsaved changes will be lost.");
      if (!response) {
        return;
      }
    }

    if (this.currentSubStep > 1) {
      // Go to previous substep
      this.currentSubStep--;
    } else if (this.currentStep > 1) {
      // Go to previous step's last substep
      this.currentStep--;
      this.currentSubStep = this.stepConfig[this.currentStep].subSteps.length;
    } else {
      // Already at the beginning
      return;
    }

    this.renderStepNavigation();
    this.updateCurrentStepInfo();
    this.loadCurrentStep();
    this.updateProgress();

    // Only update URL if not from popstate (popstate already has correct URL)
    if (!this.isPopStateNavigation) {
      this.updateUrl({ pushState: true });
    }
  }

  async skip() {
    // Save current form data (even if incomplete)
    const results = await confirmDialog.warning("Are you sure you want to skip this step? Unsaved changes will be lost.");
    if (!results) {
      return;
    }
    await this.saveAndContinue(true);
  }

  async completeSetup() {
    const buildingId = this.getBuildingId();
    if (buildingId) {
      try {
        const resp = await fetch(`/building/step/systems-status?building_uuid=${buildingId}`);
        const data = await resp.json();
        if (data.success) {
          const incomplete = data.systems.filter(s => !s.has_data && !s.not_applicable);
          if (incomplete.length > 0) {
            window._pendingSystemsComplete = incomplete;
            window._stepManagerInstance = this;
            const list = document.getElementById('systems-check-list');
            if (list) {
              list.innerHTML = incomplete.map(s => `
                <li class="flex items-center gap-2">
                  <input type="checkbox" id="sys-check-${s.key}" class="checkbox checkbox-sm"
                    onchange="document.getElementById('systems-check-confirm-btn').disabled = !Array.from(document.querySelectorAll('#systems-check-list input[type=checkbox]')).every(c=>c.checked)" />
                  <label for="sys-check-${s.key}" class="text-sm cursor-pointer">${s.label}</label>
                </li>`).join('');
              document.getElementById('systems-check-confirm-btn').disabled = true;
            }
            const modal = document.getElementById('systems-check-modal');
            if (modal) modal.showModal();
            return;
          }
        }
      } catch(e) {
        console.error('Systems status check failed:', e);
      }
    }
    await this._doCompleteSetup();
  }

  async _doCompleteSetup() {
    // Save final data
    await this.saveFormData();

    // Show loading state
    const contentArea = document.getElementById("dynamic-content");
    if (contentArea) {
      contentArea.innerHTML = `
        <div class="flex items-center justify-center h-64 w-fit mx-auto">
          <div class="loading loading-spinner loading-lg text-primary"></div>
          <p class="ml-4">Completing building setup...</p>
        </div>
      `;
    }

    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
      
      const response = await fetch(`/building/complete?building_uuid=${this.getBuildingId()}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || '',
        },
        body: JSON.stringify({
          building_uuid: this.getBuildingId(),
          all_data: this.formData
        })
      });

      const result = await response.json();

      if (response.ok && result.success) {
        // Show completion message
          Toast.success("Building setup completed successfully!");
          
          setTimeout(() => {
            window.location.href = result.redirect_url;
          }, 1000);

        // Clear localStorage
        localStorage.removeItem("building-form-data");
      } else {
        Toast.error(`Failed to complete setup: ${result.error || 'Unknown error'}`);
        throw new Error(result.error || 'Failed to complete building setup');
      }
    } catch (error) {
      console.error('Error completing setup:', error);
      Toast.error(`Error completing setup: ${error.message || 'Unknown error'}`);
      return;
    }

    // Hide navigation buttons
    const goBackBtn = document.getElementById("go-back");
    const skipBtn = document.getElementById("skip");
    const saveBtn = document.getElementById("save-and-continue");

    if (goBackBtn) goBackBtn.style.display = "none";
    if (skipBtn) skipBtn.style.display = "none";
    if (saveBtn) saveBtn.style.display = "none";

    // Update progress to 100%
    const progressText = document.getElementById("progress-text");
    const progressBar = document.getElementById("progress-bar");

    if (progressText) progressText.textContent = gettext("100% completed");
    if (progressBar) progressBar.value = 100;
  }

  async resetForm() {
    // Clear saved data from localStorage
    localStorage.removeItem("building-form-data");
    this.formData = {};
    this.formValidationStatus = {};

    // Clear server-side session data
    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
      await fetch('/building/step/save', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || '',
        },
        body: JSON.stringify({
          step_key: '__clear_all__',
          data: {}
        })
      });
    } catch (error) {
      console.error('Error clearing server data:', error);
    }

    // Reset to first step
    this.currentStep = 1;
    this.currentSubStep = 1;

    // Clear URL params and reset to base URL
    const url = new URL(window.location.href);
    url.searchParams.delete('step');
    url.searchParams.delete('substep');
    url.searchParams.delete('building_uuid');
    window.history.replaceState({}, '', url);

    // Reinitialize (skip URL parsing since we just reset)
    this.renderStepNavigation();
    this.updateCurrentStepInfo();
    this.loadCurrentStep();
    this.updateProgress();

    // Show navigation buttons again
    const goBackBtn = document.getElementById("go-back");
    const skipBtn = document.getElementById("skip");
    const saveBtn = document.getElementById("save-and-continue");

    if (goBackBtn) goBackBtn.style.display = "";
    if (skipBtn) skipBtn.style.display = "";
    if (saveBtn) saveBtn.style.display = "";
  }

  // Utility method to get all form data
  getAllFormData() {
    return this.formData;
  }

  getCurrentStepKey() {
    const currentStep = this.stepConfig[this.currentStep];
    const currentSubStep = currentStep.subSteps[this.currentSubStep - 1];
    
    return `${currentStep.id}/${currentSubStep.id}`;
  }

  // Utility method to get current step info
  getCurrentStepInfo() {
    const step = this.stepConfig[this.currentStep];
    const subStep = step.subSteps[this.currentSubStep - 1];

    return {
      step: this.currentStep,
      subStep: this.currentSubStep,
      stepName: step.name,
      subStepName: subStep.name,
      component: subStep.component,
      requiredFields: subStep.requiredFields,
      title: subStep.title,
      description: subStep.description,
    };
  }

}

// Attach class to window for global access
window.StepManager = StepManager;

// Initialize the step manager when the page loads
document.addEventListener("DOMContentLoaded", () => {
  window.stepManager = new StepManager();
});

// Export for use in other scripts
if (typeof module !== "undefined" && module.exports) {
  module.exports = StepManager;
}
