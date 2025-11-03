const API_URL = "https://restcountries.com/v3.1/all?fields=name,cca2";

// Create a map of country code (lowercase) to country data for fast lookup
const COUNTRIES_MAP = new Map();
let isLoading = true;
let hasError = false;

// Fetch countries data from API
async function fetchCountriesData() {
  if (hasCountries()) {
    isLoading = false;
    hasError = false;
    return;
  }
  try {
    const response = await fetch(API_URL);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();

    // Populate the map
    data.forEach((country) => {
      COUNTRIES_MAP.set(country.cca2.toLowerCase(), country);

    });

    isLoading = false;
    hasError = false;

    console.log(`✓ Countries registry loaded: ${data.length} countries`);
  } catch (error) {
    console.error("Failed to fetch countries data:", error);
    isLoading = false;
    hasError = true;
  }
}

// Start fetching data immediately
const dataPromise = fetchCountriesData();

/**
 * Get country name (common name)
 * @param {string} countryCode - Alpha-2 country code (case insensitive)
 * @returns {string|null} - Common country name or null if not found
 */
export function getName(countryCode) {
  if (!countryCode) return null;
  const country = COUNTRIES_MAP.get(countryCode.toLowerCase());
  return country ? country.name.common : null;
}

/**
 * Get official country name
 * @param {string} countryCode - Alpha-2 country code (case insensitive)
 * @returns {string|null} - Official country name or null if not found
 */
export function getOfficialName(countryCode) {
  if (!countryCode) return null;
  const country = COUNTRIES_MAP.get(countryCode.toLowerCase());
  return country ? country.name.official : null;
}


export function getCountryCodeByName(countryName) {
  if (!countryName) return null;
  return Array.from(COUNTRIES_MAP.entries()).find(([cca2, country]) => {
    return (country.name.common.toLowerCase() === countryName.toLowerCase() || country.name.official.toLowerCase() === countryName.toLowerCase());
  }
  )[0];
}
/**
 * Check if a country code exists
 * @param {string} countryCode - Alpha-2 country code (case insensitive)
 * @returns {Object|false} - Country object if found, false otherwise
 */
export function hasCountry(countryCode) {
  if (!countryCode) return false;
  return COUNTRIES_MAP.get(countryCode.toLowerCase()) ?? false;
}

/**
 * Get all available country codes
 * @returns {string[]} - Array of lowercase country codes
 */
export function getAvailableCountryCodes() {
  return Array.from(COUNTRIES_MAP.keys());
}

/**
 * Get all countries data
 * @returns {Array} - Array of country objects
 */
export function getAllCountries() {
  return COUNTRIES_MAP.values();
}

/**
 * Check if countries data has been loaded successfully
 * @returns {boolean} - true if countries data is available, false if empty/error
 */
export function hasCountries() {
  return COUNTRIES_MAP.size > 0;
}

/**
 * Check if countries data is currently loading
 * @returns {boolean} - true if still loading
 */
export function isLoadingCountries() {
  return isLoading;
}

/**
 * Check if there was an error loading countries data
 * @returns {boolean} - true if there was an error
 */
export function hasLoadingError() {
  return hasError;
}

/**
 * Wait for countries data to be loaded
 * @returns {Promise<void>}
 */
export async function waitForCountries() {
  await dataPromise;
}

/**
 * Initialize country flags by replacing elements with data-country attribute
 * This function should be called after DOM is loaded
 *
 * Attributes:
 * - data-country: Country code (required)
 * - data-flag: Boolean, if true shows flag, if false shows name (default: true)
 * - data-name: 'common' or 'official' for name format (default: 'common')
 * - data-width: Width in pixels for flag image (default: 16)
 * - data-class: Additional CSS classes to apply
 *
 * Note: Flag images are always replaced, even if country data fails to load
 */
export async function initCountryFlags() {
  // Wait for data to load (or fail)
  await dataPromise;

  // Find all elements with data-country attribute
  const elements = document.querySelectorAll("[data-country]");

  elements.forEach((element) => {
    const countryCode = element.getAttribute("data-country");

    if (!countryCode) {
      console.warn("Element has data-country attribute but no value:", element);
      return;
    }

    const lowerCode = countryCode.length > 2 ? getCountryCodeByName(countryCode) : countryCode.toLowerCase();

    // Get attributes
    const showFlag = element.getAttribute("data-flag") !== "false"; // default true
    const nameType = element.getAttribute("data-name") || "common"; // 'common' or 'official'
    const width = parseInt(element.getAttribute("data-width")) || 16; // default 16px
    const customClasses = element.getAttribute("data-class") || "";

    // Get country name if data is available, otherwise use code
    let countryName;
    if (hasCountries()) {
      if (nameType === "official") {
        countryName = getOfficialName(lowerCode) || countryCode;
      } else {
        countryName = getName(lowerCode) || countryCode;
      }
    } else {
      countryName = countryCode;
    }

    if (showFlag) {
      // Create flag image
      const flagUrl = `https://cdn.jsdelivr.net/gh/HatScripts/circle-flags/flags/${lowerCode}.svg`;
      const img = document.createElement("img");
      img.src = flagUrl;
      img.alt = `${countryName} Flag icon`;
      img.style.width = `${width}px`;
      img.className = customClasses;

      // Copy any other attributes except data-* and class
      Array.from(element.attributes).forEach((attr) => {
        if (
          !attr.name.startsWith("data-") &&
          attr.name !== "class" &&
          attr.name !== "style"
        ) {
          img.setAttribute(attr.name, attr.value);
        }
      });

      // Replace the element with the img
      element.replaceWith(img);
    } else {
      // Create text element with country name
      const p = document.createElement("p");
      p.textContent = countryName;
      p.className = customClasses;

      // Copy any other attributes except data-* and class
      Array.from(element.attributes).forEach((attr) => {
        if (!attr.name.startsWith("data-") && attr.name !== "class") {
          p.setAttribute(attr.name, attr.value);
        }
      });

      // Replace the element with the p
      element.replaceWith(p);
    }
  });

  if (!hasCountries()) {
    console.warn(
      "⚠ Countries data not available. Flags displayed but helper functions may return null."
    );
  }
}

// Create a global instance for easy access
if (typeof window !== "undefined") {
  window.CountriesRegistry = {
    initCountryFlags,
    getName,
    getOfficialName,
    hasCountry,
    hasCountries,
    isLoadingCountries,
    hasLoadingError,
    getAvailableCountryCodes,
    getAllCountries,
    waitForCountries,
  };
}

// Auto-initialize when DOM is ready if this is running in a browser
if (typeof window !== "undefined" && typeof document !== "undefined") {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCountryFlags);
  } else {
    // DOM is already loaded
    initCountryFlags();
  }
}
