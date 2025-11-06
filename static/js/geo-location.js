class GeoLocationPicker {
  constructor() {
    this.map = null;
    this.marker = null;
    this.currentLocation = { lat: 5.603717, lng: -0.186964 }; // Default: Accra, Ghana
    this.selectedAddress = "";
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
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
          query
        )}&limit=1`
      );
      const results = await response.json();

      if (results.length > 0) {
        const { lat, lon, display_name } = results[0];
        this.map.setView([parseFloat(lat), parseFloat(lon)], 15);
        this.selectedAddress = display_name;
      }
    } catch (error) {
      console.error("Search failed:", error);
    }
  }

  async reverseGeocode(lat, lng) {
    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`
      );
      const data = await response.json();
      this.selectedAddress = data.display_name || "";
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
          console.log("Could not get user location:", error);
        }
      );
    }
  }

  getSelectedLocation() {
    return {
      latitude: this.currentLocation.lat,
      longitude: this.currentLocation.lng,
      address: this.selectedAddress,
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

function selectCurrentLocation() {
  if (window.geoLocationPicker) {
    const location = window.geoLocationPicker.getSelectedLocation();

    // Fill the form fields
    const addressInput = document.querySelector(
      'input[placeholder*="1885 L Street"]'
    );
    const latInput = document.querySelector('input[placeholder*="5.603722"]');
    const lngInput = document.querySelector('input[placeholder*="-7.946232"]');

    if (addressInput && location.address) {
      addressInput.value = location.address;
    }
    if (latInput) {
      latInput.value = location.latitude.toFixed(6);
    }
    if (lngInput) {
      lngInput.value = location.longitude.toFixed(6);
    }

    closeGeoLocationModal();
  }
}

// Initialize when page loads
document.addEventListener("DOMContentLoaded", () => {
  window.geoLocationPicker = new GeoLocationPicker();
  window.geoLocationPicker.init();
});
