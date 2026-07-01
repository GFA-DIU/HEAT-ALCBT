class GeoLocationPicker {
  constructor() {
    this.map = null;
    this.marker = null;
    this.currentLocation = { lat: 5.603717, lng: -0.186964 }; // Default: Accra, Ghana
    this.selectedAddress = "";
    this.country = "";
    this.city = "";
    this.state = "";
    // Ordered lists of candidate names so we can try several keys when
    // matching against the region / city dropdowns (Nominatim is inconsistent:
    // city-states like Bangkok expose the region only under `city`).
    this.stateCandidates = [];
    this.cityCandidates = [];
  }

  _extractCandidates(addr) {
    addr = addr || {};
    // Region/state candidates, most-specific first
    this.stateCandidates = [
      addr.state,
      addr.region,
      addr.province,
      addr.state_district,
      addr.county,
      // City-states (Bangkok, Singapore, etc.) expose the region as `city`
      addr.city,
    ].filter(Boolean);
    // City candidates
    this.cityCandidates = [
      addr.city,
      addr.town,
      addr.village,
      addr.municipality,
      addr.suburb,
      addr.city_district,
    ].filter(Boolean);
    this.state = this.stateCandidates[0] || "";
    this.city = this.cityCandidates[0] || "";
    this.country = addr.country || "";
  }

  init() {
    const modal = document.getElementById("geo_location_modal");
    if (!modal) return;

    // Initialize map when modal is opened
    modal.addEventListener("open", () => {
      this.initializeMap();
    });
  }

  initializeMap() {
    if (this.map) {
      this.map.invalidateSize();
      return;
    }

    // Initialize Leaflet map
    this.map = L.map("map", {
      center: [this.currentLocation.lat, this.currentLocation.lng],
      zoom: 13,
      zoomControl: true,
    });

    // Add OpenStreetMap tiles
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap contributors",
      maxZoom: 19,
    }).addTo(this.map);

    // Update location on map move
    this.map.on("moveend", () => {
      const center = this.map.getCenter();
      this.currentLocation = { lat: center.lat, lng: center.lng };
      this.reverseGeocode(center.lat, center.lng);
    });

    // Initialize search
    this.initializeSearch();

    // Try to get user's current location
    this.getUserLocation();
  }

  initializeSearch() {
    const searchInput = document.getElementById("location-search");
    if (!searchInput) return;

    let searchTimeout;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(searchTimeout);
      const query = e.target.value.trim();

      if (query.length < 3) return;

      searchTimeout = setTimeout(() => {
        this.searchLocation(query);
      }, 500);
    });
  }

  async searchLocation(query) {
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&accept-language=en&q=${encodeURIComponent(
          query
        )}&limit=1`
      );
      const results = await response.json();

      if (results.length > 0) {
        const { lat, lon, display_name, address } = results[0];
        this.map.setView([parseFloat(lat), parseFloat(lon)], 15);
        this.selectedAddress = display_name;
        this._extractCandidates(address);
      }
    } catch (error) {
      console.error("Search failed:", error);
    }
  }

  async reverseGeocode(lat, lng) {
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&addressdetails=1&accept-language=en&lat=${lat}&lon=${lng}`
      );
      const data = await response.json();
      this.selectedAddress = data.display_name || "";
      this._extractCandidates(data.address);
    } catch (error) {
      console.error("Reverse geocoding failed:", error);
    }
  }

  getUserLocation() {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          this.map.setView([latitude, longitude], 15);
          this.currentLocation = { lat: latitude, lng: longitude };
        },
        (error) => {
          console.error("Could not get user location:", error);
        }
      );
    }
  }

  getSelectedLocation() {
    return {
      latitude: this.currentLocation.lat,
      longitude: this.currentLocation.lng,
      address: this.selectedAddress,
      country: this.country,
      city: this.city,
      state: this.state,
      stateCandidates: this.stateCandidates.slice(),
      cityCandidates: this.cityCandidates.slice(),
    };
  }
}

// Global functions for modal control
function openGeoLocationModal() {
  const modal = document.getElementById("geo_location_modal");
  if (modal) {
    modal.showModal();
    // Initialize or refresh map after modal opens
    setTimeout(() => {
      if (window.geoLocationPicker) {
        window.geoLocationPicker.initializeMap();
      }
    }, 100);
  }
}

function closeGeoLocationModal() {
  const modal = document.getElementById("geo_location_modal");
  if (modal) {
    modal.close();
  }
}


function getOptionNameAndValue(option) {

  return {
    name: option.getAttribute('data-name'),
    value: option.getAttribute('value')
  };
}

// Find a <select> option whose visible text matches one of the candidate names.
// Tries exact (case-insensitive) match first, then a contains/startsWith fallback.
function findOptionByNames(selectEl, candidates) {
  if (!selectEl || !candidates || !candidates.length) return null;
  const options = Array.from(selectEl.options).filter((o) => o.value);
  const norm = (s) => (s || "").toString().trim().toLowerCase();
  // Exact match pass
  for (const name of candidates) {
    const target = norm(name);
    if (!target) continue;
    const exact = options.find((o) => norm(o.text) === target);
    if (exact) return exact;
  }
  // Loose match pass (handles "Bangkok Metropolis" vs "Bangkok", etc.)
  for (const name of candidates) {
    const target = norm(name);
    if (!target) continue;
    const loose = options.find(
      (o) => norm(o.text).includes(target) || target.includes(norm(o.text))
    );
    if (loose) return loose;
  }
  return null;
}

// Fire a native change event so the form-validator clears the "required" error.
function notifyChange(el) {
  if (el) el.dispatchEvent(new Event("change", { bubbles: true }));
}

// Haversine distance (km) between two (lat,lon) pairs.
function _haversineKm(lat1, lon1, lat2, lon2) {
  const toRad = (d) => (d * Math.PI) / 180;
  const R = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

// Find the option in `selectEl` whose data-lat/data-lon is closest to (lat,lon)
// and within `maxKm` km. Returns the option element or null.
function findOptionByDistance(selectEl, lat, lon, maxKm = 50) {
  if (!selectEl || lat == null || lon == null) return null;
  let best = null;
  let bestKm = Infinity;
  for (const opt of selectEl.options) {
    if (!opt.value) continue;
    const oLat = parseFloat(opt.getAttribute("data-lat"));
    const oLon = parseFloat(opt.getAttribute("data-lon"));
    if (Number.isNaN(oLat) || Number.isNaN(oLon)) continue;
    const km = _haversineKm(lat, lon, oLat, oLon);
    if (km < bestKm) {
      bestKm = km;
      best = opt;
    }
  }
  return best && bestKm <= maxKm ? best : null;
}

// Show or hide a non-blocking inline note under the city select indicating
// that auto-detection failed.
function _setCityAutopickNote(visible) {
  const note = document.getElementById("city-autopick-note");
  if (!note) return;
  note.style.display = visible ? "" : "none";
}

// Re-validate geo fields via FormValidator directly, without dispatching DOM events
// that would re-trigger HTMX cascades and wipe freshly-loaded dropdown values.
function _revalidateGeoFields(countryEl, regionEl, cityEl) {
  const fv = window.currentFormValidator;
  if (!fv) return;
  if (countryEl) fv.validateField(countryEl);
  if (regionEl) fv.validateField(regionEl);
  if (cityEl) fv.validateField(cityEl);
  fv.updateFormStatus();
}

async function selectCurrentLocation() {
  if (!window.geoLocationPicker) return;

  const location = window.geoLocationPicker.getSelectedLocation();
  console.log("[GeoLocation] Selected location:", location);

  // Fill the form fields
  const addressInput = document.querySelector('input[placeholder*="1885 L Street"]');
  const latInput = document.querySelector('input[placeholder*="5.603722"]');
  const lngInput = document.querySelector('input[placeholder*="-7.946232"]');

  if (addressInput && location.address) {
    addressInput.value = location.address;
    notifyChange(addressInput);
  }
  if (latInput) {
    latInput.value = location.latitude.toFixed(6);
    notifyChange(latInput);
  }
  if (lngInput) {
    lngInput.value = location.longitude.toFixed(6);
    notifyChange(lngInput);
  }

  // Close the modal immediately; the cascade runs asynchronously.
  closeGeoLocationModal();

  if (!location.country) return;

  const countrySelect = document.querySelector("select#country-select");
  if (!countrySelect) return;

  const opts = Array.from(countrySelect.querySelectorAll("option")).map(getOptionNameAndValue);
  const matchedCountry = opts.find(
    (opt) => opt.name && opt.name.toLowerCase() === location.country.toLowerCase()
  );

  if (!matchedCountry) {
    console.warn("[GeoLocation] No country match for:", location.country);
    // OSM detected a country that isn't in the ALCBT list — warn user
    if (typeof window._showGeoAddressMismatch === "function") {
      window._showGeoAddressMismatch(true);
    }
    return;
  }

  // Set the value WITHOUT dispatching change: dispatching would trigger the
  // country select's own hx-trigger and race a second region load against ours.
  countrySelect.value = matchedCountry.value;

  // Country matched — clear any previous mismatch warning
  if (typeof window._showGeoAddressMismatch === "function") {
    window._showGeoAddressMismatch(false);
  }

  try {
    // 1. Load regions for the matched country into #region-select
    await htmx.ajax("GET", "/select_lists/?country=" + matchedCountry.value, {
      target: "#region-select",
      swap: "innerHTML",
    });
    // Yield to let HTMX finish the DOM swap before we read options
    await new Promise(r => setTimeout(r, 0));

    const regionSelect = document.getElementById("region-select");
    const regionMatch = findOptionByNames(regionSelect, location.stateCandidates);
    if (!regionMatch) {
      console.warn("[GeoLocation] No region match for candidates:", location.stateCandidates);
      _revalidateGeoFields(countrySelect, regionSelect, null);
      return;
    }
    regionSelect.value = regionMatch.value;
    console.log("[GeoLocation] Matched region:", regionMatch.text);

    // 2. Load cities for the matched region into #city-select.
    // We use our own htmx.ajax call — do NOT fire notifyChange(regionSelect) here
    // because the region select's own hx-trigger="change" would race against us.
    // Pass lat/lon so the backend emits data-lat/data-lon for nearest-city fallback.
    const cityUrl =
      "/select_lists/?region=" + regionMatch.value +
      "&lat=" + encodeURIComponent(location.latitude) +
      "&lon=" + encodeURIComponent(location.longitude);
    await htmx.ajax("GET", cityUrl, {
      target: "#city-select",
      swap: "innerHTML",
    });
    // Yield to let HTMX finish the DOM swap before we read options
    await new Promise(r => setTimeout(r, 0));

    const citySelect = document.getElementById("city-select");
    // Pass 1: match by name (handles cases where Nominatim's city matches the DB row)
    let cityMatch = findOptionByNames(citySelect, location.cityCandidates);
    // Pass 2: nearest-city by lat/lon (handles suburbs/neighborhoods Nominatim returns
    // that aren't in cities_light — pick the closest large city within 50 km)
    if (!cityMatch) {
      cityMatch = findOptionByDistance(citySelect, location.latitude, location.longitude, 50);
      if (cityMatch) {
        console.log(
          "[GeoLocation] Picked nearest city by distance:", cityMatch.text
        );
      }
    }
    if (!cityMatch) {
      console.warn("[GeoLocation] No city match for candidates:", location.cityCandidates);
      _setCityAutopickNote(true);
      _revalidateGeoFields(countrySelect, regionSelect, citySelect);
      return;
    }
    citySelect.value = cityMatch.value;
    _setCityAutopickNote(false);
    console.log("[GeoLocation] Matched city:", cityMatch.text);
    _revalidateGeoFields(countrySelect, regionSelect, citySelect);
  } catch (err) {
    console.error("[GeoLocation] Cascade failed:", err);
  }
}

// Attach to window for global access (needed for onclick handlers)
window.GeoLocationPicker = GeoLocationPicker;
window.openGeoLocationModal = openGeoLocationModal;
window.closeGeoLocationModal = closeGeoLocationModal;
window.selectCurrentLocation = selectCurrentLocation;

// Initialize when page loads
document.addEventListener("DOMContentLoaded", () => {
  window.geoLocationPicker = new GeoLocationPicker();
  window.geoLocationPicker.init();
});
