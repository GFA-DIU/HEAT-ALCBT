class StepManager {
  constructor() {
    this.currentStep = 1;
    this.currentSubStep = 1;
    this.totalSteps = 4;
    this.stepConfig = {
      1: {
        name: "Building Information",
        subSteps: [
          {
            name: "Building Name & Location",
            component: "building-information/building-name-location.html",
            requiredFields: ["building-name", "address", "country"],
            title: "Building Name & Location",
            description:
              "Add details concerning building name and locations of building.",
          },
          {
            name: "Building Details",
            component: "building-information/building-details.html",
            requiredFields: ["building-type", "total-floors", "total-area"],
            title: "Building Details",
            description: "Add detailed information about your building.",
          },
        ],
      },
      2: {
        name: "Operational Details",
        subSteps: [
          {
            name: "Operational Schedule & Temperature",
            component:
              "operational-details/operational-schedule-temperature.html",
            requiredFields: ["operating-hours", "default-temperature"],
            title: "Operational Schedule & Temperature",
            description:
              "Complete field below to add operations information about your building.",
          },
          {
            name: "Cooling System",
            component: "operational-details/cooling-system.html",
            requiredFields: ["cooling-system-type"],
            title: "Cooling System",
            description:
              "Enter details of the building's cooling system, including type and capacity.",
          },
          {
            name: "Ventilation System",
            component: "operational-details/ventilation-system.html",
            requiredFields: ["ventilation-type"],
            title: "Ventilation System",
            description:
              "Provide details on the building,s ventilation type, capacity, and coverage to assess airflow and indoor air quality.",
          },
          {
            name: "Lighting System",
            component: "operational-details/lighting-system.html",
            requiredFields: ["lighting-type"],
            title: "Lighting System",
            description:
              "Provide details on lighting types, power use, and controls to assess efficiency.",
          },
          {
            name: "Lift & Escalator System",
            component: "operational-details/lift-escalator-system.html",
            requiredFields: [],
            title: "Lift & Escalator System",
            description:
              "Provide details on lift & escalator systems in your building if any.",
          },
          {
            name: "Hot Water System",
            component: "operational-details/hot-water-system.html",
            requiredFields: ["hot-water-type"],
            title: "Hot Water System",
            description:
              "Defines the building’s method of producing and distributing hot water, including equipment type, energy source, and usage patterns.",
          },
        ],
      },
      3: {
        name: "Operational Data Entry",
        subSteps: [
          {
            name: "Data Entry",
            component: "operational-data-entry/operational-data-entry.html",
            requiredFields: ["energy-consumption"],
            title: "Operational Energy carrier",
            description:
              "Tell us what fuels or energy sources your building runs on.",
          },
        ],
      },
      4: {
        name: "Building Structural Components",
        subSteps: [
          {
            name: "Structural Components",
            component:
              "building-structural-components/building-structural-components.html",
            requiredFields: ["foundation-type", "structure-type"],
            title: "Building Structural Components",
            description:
              "Provide details on the building's structural components, including type and capacity.",
          },
        ],
      },
    };

    // Store form data
    this.formData = {};

    // Store form validation status for each step
    this.formValidationStatus = {};

    this.init();
  }

  init() {
    this.renderStepNavigation();
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
      localStorage.setItem("building-form-data", JSON.stringify(this.formData));
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
        <div class="loading loading-spinner loading-lg"></div>
      </div>
    `;

    try {
      const response = await fetch(`./components/${subStep.component}`);

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

      // Initialize icons
      if (window.IconComponent) {
        window.IconComponent.initialize();
      }
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
    const step = this.stepConfig[this.currentStep];
    const subStep = step.subSteps[this.currentSubStep - 1];
    const saveBtn = document.getElementById("save-and-continue");
    const goBackBtn = document.getElementById("go-back");

    if (saveBtn) {
      const isValid = this.validateCurrentStep();
      saveBtn.disabled = !isValid;

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

  saveFormData() {
    const stepKey = `step-${this.currentStep}-${this.currentSubStep}`;
    const formElements = document.querySelectorAll("input, select, textarea");

    this.formData[stepKey] = {};

    formElements.forEach((element) => {
      if (element.name || element.dataset.field) {
        const key = element.name || element.dataset.field;
        const value =
          element.type === "checkbox" ? element.checked : element.value;
        this.formData[stepKey][key] = value;
      }
    });

    // Save to localStorage for persistence
    localStorage.setItem("building-form-data", JSON.stringify(this.formData));
  }

  restoreFormData() {
    // Load from localStorage if available
    const savedData = localStorage.getItem("building-form-data");
    if (savedData) {
      this.formData = JSON.parse(savedData);
    }

    const stepKey = `step-${this.currentStep}-${this.currentSubStep}`;
    const stepData = this.formData[stepKey];

    if (stepData) {
      Object.keys(stepData).forEach((key) => {
        const element = document.querySelector(
          `[name="${key}"], [data-field="${key}"]`
        );
        if (element) {
          if (element.type === "checkbox") {
            element.checked = stepData[key];
          } else {
            element.value = stepData[key];
          }
        }
      });
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

  saveAndContinue() {
    // Save current form data
    this.saveFormData();

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
    this.loadCurrentStep();
    this.updateProgress();
  }

  goBack() {
    // Save current form data before going back
    this.saveFormData();

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
    this.loadCurrentStep();
    this.updateProgress();
  }

  skip() {
    // Save current form data (even if incomplete)
    this.saveFormData();
    this.saveAndContinue();
  }

  completeSetup() {
    // Save final data
    this.saveFormData();

    // Show completion message
    const contentArea = document.getElementById("dynamic-content");
    if (contentArea) {
      contentArea.innerHTML = `
        <div class="flex flex-col items-center justify-center h-64 text-center">
          <div class="alert alert-success max-w-md">
            <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h3 class="font-bold">Building Setup Completed!</h3>
              <div class="text-xs">All information has been saved successfully.</div>
            </div>
          </div>
          <div class="mt-6 space-x-2">
            <button class="btn btn-primary" onclick="window.location.href='/src/pages/dashboard/dashboard.html'">
              Go to Dashboard
            </button>
            <button class="btn btn-outline" onclick="stepManager.resetForm()">
              Add Another Building
            </button>
          </div>
        </div>
      `;
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

  resetForm() {
    // Clear saved data
    localStorage.removeItem("building-form-data");
    this.formData = {};

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

  // Utility method for components to easily emit form status
  static emitFormStatus(isValid, data = null, stepKey = null) {
    const event = new CustomEvent("onFormStatus", {
      detail: {
        isValid: isValid,
        data: data,
        stepKey: stepKey,
      },
    });
    document.dispatchEvent(event);
  }
}

function goToDashboard() {
  window.location.href = "/src/pages/dashboard/dashboard.html";
}

// Initialize the step manager when the page loads
document.addEventListener("DOMContentLoaded", () => {
  window.stepManager = new StepManager();
});

// Export for use in other scripts
if (typeof module !== "undefined" && module.exports) {
  module.exports = StepManager;
}
