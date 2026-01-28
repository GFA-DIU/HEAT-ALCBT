// @ts-check
class StepManager {
   
  editMode = false;

  constructor() {
    this.currentStep = 1;
    this.currentSubStep = 1;
    this.totalSteps = 4;
    this.editMode = window.location.pathname.includes('/building/edit');

    if(this.editMode){
      document.getElementById('page-title').textContent = 'Edit Building Information';
      document.getElementById('page-description').textContent = 'Update the building information as needed.';
    }


    this.stepConfig = {
      1: {
        name: "Building Information",
        id: "building-information",
        subSteps: [
          {
            id: "building-name-location",
            name: "Building Name & Location",
            component: "building-information/building-name-location.html",
            requiredFields: ["building_name", "address", "country"],
            title: "Building Name & Location",
            description:
              "Add details concerning building name and locations of building.",
          },
          {
            id: "building-details",
            name: "Building Details",
            component: "building-information/building-details.html",
            requiredFields: ["building_type", "assessment_period", "total_floor_area"],
            title: "Building Details",
            description: "Add detailed information about your building.",
          },
        ],
      },
      2: {
        name: "Operational Details",
        id: "operational-details",
        subSteps: [
          {
            id: "operational-schedule-temperature",
            name: "Operational Schedule & Temperature",
            component:
              "operational-details/operational-schedule-temperature.html",
            requiredFields: ["operating_hours", "default_temperature"],
            title: "Operational Schedule & Temperature",
            description:
              "Complete field below to add operations information about your building.",
          },
          {
            id: "cooling-system",
            name: "Cooling System",
            component: "operational-details/cooling-system.html",
            requiredFields: ["cooling_system_type"],
            title: "Cooling System",
            description:
              "Enter details of the building's cooling system, including type and capacity.",
          },
          {
            id: "ventilation-system",
            name: "Ventilation System",
            component: "operational-details/ventilation-system.html",
            requiredFields: ["ventilation_type"],
            title: "Ventilation System",
            description:
              "Provide details on the building,s ventilation type, capacity, and coverage to assess airflow and indoor air quality.",
          },
          {
            id: "lighting-system",
            name: "Lighting System",
            component: "operational-details/lighting-system.html",
            requiredFields: ["lighting_type"],
            title: "Lighting System",
            description:
              "Provide details on lighting types, power use, and controls to assess efficiency.",
          },
          {
            id: "lift-escalator-system",
            name: "Lift & Escalator System",
            component: "operational-details/lift-escalator-system.html",
            requiredFields: [],
            title: "Lift & Escalator System",
            description:
              "Provide details on lift & escalator systems in your building if any.",
          },
          {
            formId: "hot-water-system",
            name: "Hot Water System",
            component: "operational-details/hot-water-system.html",
            requiredFields: ["hot_water_type"],
            title: "Hot Water System",
            description:
              "Defines the building’s method of producing and distributing hot water, including equipment type, energy source, and usage patterns.",
          },
        ],
      },
      3: {
        name: "Operational Data Entry",
        id: "operational-data-entry",
        subSteps: [
          {
            id: "operational-data-entry",
            name: "Data Entry",
            component: "operational-data-entry/operational-data-entry.html",
            requiredFields: ["energy_consumption"],
            title: "Operational Energy carrier",
            description:
              "Tell us what fuels or energy sources your building runs on.",
          },
        ],
      },
      4: {
        name: "Building Structural Components",
        id: "building-structural-components",
        subSteps: [
          {
            id: "building-structural-components",
            name: "Structural Components",
            component:
              "building-structural-components/building-structural-components.html",
            requiredFields: ["foundation_type", "structure_type"],
            title: "Building Structural Components",
            description:
              "Enter information about the building’s walls, floors, roofs, and other structural parts.",
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
            : "";

          return `
          <div class="stepper-sub-item" onclick="stepManager.goToSubStep(${stepNum}, ${subStepNum})">  
            ${icon}
            <span class="stepper-sub-item-text ${
              isSubActive ? "text-[var(--text--strong-950)]" : ""
            } ${
            isSubCompleted ? "text-[var(--text--strong-950)] line-through" : ""
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
                ? `
              <input
                type="checkbox"
                class="checkbox checkbox-primary checkbox-sm rounded-full pointer-events-none"
                checked/>
            `
                : `
              <div class="stepper-item-icon"></div>
            `
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
  
    // Show loading state
    contentArea.innerHTML = `
      <div class="flex items-center justify-center h-64">
        <div class="loading loading-spinner loading-lg text-primary"></div>
      </div>
    `;

    try {
      // Use the new Django step view endpoint
      // Get building UUID if it exists in form data
      const buildingUuid = this.formData['building-information/building-name-location']?.building_uuid || '';
      const url = buildingUuid
        ? `/building/step?step=${subStep.component}&building_uuid=${buildingUuid}`
        : `/building/step?step=${subStep.component}`;

      // Update browser URL to include UUID if available
      if (buildingUuid && !window.location.search.includes('building_uuid')) {
        const newUrl = new URL(window.location);
        newUrl.searchParams.set('building_uuid', buildingUuid);
        window.history.pushState({}, '', newUrl);
      }

      const response = await fetch(url);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const html = await response.text();
      contentArea.innerHTML = html;

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
        // Remove the new script after execution to avoid duplicates
        setTimeout(() => newScript.remove(), 100);
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
    const totalSubSteps = Object.values(this.stepConfig).reduce(
      (total, step) => total + step.subSteps.length,
      0
    );
    let completedSubSteps = 0;

    // Calculate completed substeps
    for (let i = 1; i < this.currentStep; i++) {
      completedSubSteps += this.stepConfig[i].subSteps.length;
    }
    completedSubSteps += this.currentSubStep - 1;

    const percentage = Math.round((completedSubSteps / totalSubSteps) * 100);

    const progressText = document.getElementById("progress-text");
    const progressBar = document.getElementById("progress-bar");

    if (progressText) {
      progressText.textContent = `${percentage}% completed`;
    }

    if (progressBar) {
      progressBar.value = percentage;
    }
  }

  updateButtonStates() {
    console.log("Updating button states...");
    const step = this.stepConfig[this.currentStep];
    const subStep = step.subSteps[this.currentSubStep - 1];
    const saveBtn = document.getElementById("save-and-continue");
    const goBackBtn = document.getElementById("go-back");

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
      const isFirstStep = this.currentStep === 1 && this.currentSubStep === 1;
      goBackBtn.disabled = isFirstStep;
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
      const forms = document.getElementById('selected_op_products')?.querySelectorAll("form");
      if (!forms || forms.length === 0) {
        Toast.error("No operational products found. Please add at least one.");
        throw new Error("No operational products found.");
      }
      /**
       * @type {{ [k: string]: FormDataEntryValue; }[]}
       */
      const combinedData = [];
      
      forms.forEach((form) => {
        const formData = new FormData(form);
        let validator = new window.FormValidator(form);
        let isValid = validator.validate();
        if (!isValid) {
          Toast.error("Please correct the errors in the form before proceeding.");
          throw new Error("Form validation failed.");
        }
        combinedData.push(Object.fromEntries(formData.entries()));
      });
      
      return { 
        building_uuid: this.getBuildingId(),
        operation_products: combinedData 
      };

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

    console.log("Saving step data:", stepData);
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
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;

      // Get building_uuid from URL params or from formData
      const urlParams = new URLSearchParams(window.location.search);
      const urlUuid = urlParams.get('building_uuid');
      const formUuid = this.formData['building-information/building-name-location']?.building_uuid;

      // Add building_uuid to stepData if it exists
      const dataWithUuid = {
        ...stepData,
        building_uuid: urlUuid || formUuid || stepData.building_uuid || ''
      };

      const response = await fetch('/building/step/save', {
        method: this.editMode ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || '',
        },
        body: JSON.stringify({
          building_uuid: this.getBuildingId(),
          step_key: stepKey,
          data: dataWithUuid
        })
      });

      const result = await response.json();

      if (!response.ok) {
        console.error('Failed to save step data to server:', result);
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
          >${this.currentSubStep} out of
          <span class="font-normal text-[var(--text--sub-600)]"
            >${this.stepConfig[this.currentStep].subSteps.length} steps</span
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
    this.currentStep = parseInt(step);
    this.currentSubStep = 1;
    this.renderStepNavigation();
    this.updateCurrentStepInfo();
    this.loadCurrentStep();
    this.updateProgress();
  }

  goToSubStep(step, subStep) {
    this.currentStep = parseInt(step);
    this.currentSubStep = parseInt(subStep);
    this.renderStepNavigation();
    this.updateCurrentStepInfo();
    this.loadCurrentStep();
    this.updateProgress();
  }

  async saveAndContinue(skipSave = false) {
    // Save current form data and wait for completion
    if(!skipSave){
      const saveResult = await this.saveFormData();

      // Check if save failed
      if (saveResult && !saveResult.success) {
        // Show error message
        Toast.error(`Failed to save: ${saveResult.error || 'Unknown error'}`);
        return; // Don't proceed to next step
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
  }

  async goBack() {
    const response = await confirmDialog.warning("Are you sure you want to go back? Unsaved changes will be lost.");
    if (!response) {
      return;
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
    // Save final data
    await this.saveFormData();

    // Show loading state
    const contentArea = document.getElementById("dynamic-content");
    if (contentArea) {
      contentArea.innerHTML = `
        <div class="flex items-center justify-center h-64">
          <div class="loading loading-spinner loading-lg text-primary"></div>
          <p class="ml-4">Completing building setup...</p>
        </div>
      `;
    }

    try {
      const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
      
      const response = await fetch('/building/complete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken || '',
        },
        body: JSON.stringify({
          all_data: this.formData
        })
      });

      const result = await response.json();

      if (response.ok && result.success) {
        // Show completion message
        if (contentArea) {
          contentArea.innerHTML = `
            <div class="flex flex-col items-center justify-center h-64 text-center">
              <div class="alert alert-success max-w-md">
                <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <h3 class="font-bold">Building Setup Completed!</h3>
                  <div class="text-xs">${result.message || 'All information has been saved successfully.'}</div>
                </div>
              </div>
              <div class="mt-6 space-x-2">
                <button class="btn btn-primary" onclick="window.location.href='${result.redirect_url || '/dashboard/'}'">
                  Go to Dashboard
                </button>
                <button class="btn btn-outline" onclick="stepManager.resetForm()">
                  Add Another Building
                </button>
              </div>
            </div>
          `;
        }

        // Clear localStorage
        localStorage.removeItem("building-form-data");
      } else {
        throw new Error(result.error || 'Failed to complete building setup');
      }
    } catch (error) {
      console.error('Error completing setup:', error);
      if (contentArea) {
        contentArea.innerHTML = `
          <div class="flex flex-col items-center justify-center h-64 text-center">
            <div class="alert alert-error max-w-md">
              <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <h3 class="font-bold">Error Completing Setup</h3>
                <div class="text-xs">${error.message}</div>
              </div>
            </div>
            <button onclick="stepManager.completeSetup()" class="btn btn-primary mt-4">
              Retry
            </button>
          </div>
        `;
      }
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

    if (progressText) progressText.textContent = "100% completed";
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

    // Reinitialize
    this.init();

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

    console.log(subStep.title);
    console.log(subStep.description);

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
