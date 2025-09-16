import {
  ICONS_REGISTRY,
  EXCLUDED_FROM_CURRENT_COLOR,
} from "/src/constants/icons-registry.js";

class IconComponent {
  constructor() {
    this.registry = new Map(Object.entries(ICONS_REGISTRY));
    this.defaultProps = {
      size: 20,
      color: "currentColor",
      className: "",
    };
  }

  initialize() {
    const icons = document.querySelectorAll("[data-icon]");
    icons.forEach((el) => {
      const iconName = el.dataset.icon;
      const size = parseInt(el.dataset.size) || 20;
      const color = el.dataset.color || "currentColor";

      window.IconComponent.render(iconName, el, { size, color });
    });
  }

  /**
   * Register an additional icon (for runtime additions)
   */
  register(name, svgContent) {
    this.registry.set(name, svgContent);
  }

  /**
   * Create an icon element
   */
  create(iconName, options = {}) {
    const props = { ...this.defaultProps, ...options };
    const svgContent = this.registry.get(iconName);

    if (!svgContent) {
      console.warn(
        `Icon "${iconName}" not found in registry. Available icons:`,
        this.getAvailableIcons()
      );
      return this.createPlaceholder(props);
    }

    return this.createSVGElement(svgContent, props, iconName);
  }

  /**
   * Create SVG element with proper attributes
   */
  createSVGElement(svgContent, props, iconName) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(svgContent, "image/svg+xml");
    const svg = doc.documentElement;

    // Set size
    svg.setAttribute("width", props.size);
    svg.setAttribute("height", props.size);

    // Add classes
    if (props.className) {
      svg.setAttribute("class", props.className);
    }

    // Handle color - replace fill/stroke with currentColor if color is specified
    if (
      props.color !== "inherit" &&
      !EXCLUDED_FROM_CURRENT_COLOR.includes(iconName)
    ) {
      this.applyColor(svg, props.color);
    }

    return svg;
  }

  /**
   * Apply color to SVG elements
   */
  applyColor(svg, color) {
    // Find all elements with fill or stroke attributes
    const elementsWithFill = svg.querySelectorAll('[fill]:not([fill="none"])');
    const elementsWithStroke = svg.querySelectorAll(
      '[stroke]:not([stroke="none"])'
    );

    elementsWithFill.forEach((el) => {
      el.setAttribute("fill", color);
    });

    elementsWithStroke.forEach((el) => {
      el.setAttribute("stroke", color);
    });
  }

  /**
   * Create a placeholder for missing icons
   */
  createPlaceholder(props) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", props.size);
    svg.setAttribute("height", props.size);
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.innerHTML = `
      <rect x="2" y="2" width="20" height="20" stroke="${props.color}" stroke-width="2" stroke-dasharray="4 4"/>
      <text x="12" y="13" text-anchor="middle" font-size="8" fill="${props.color}">?</text>
    `;
    return svg;
  }

  /**
   * Render icon directly into a container
   */
  render(iconName, container, options = {}) {
    const icon = this.create(iconName, options);
    if (container) {
      container.innerHTML = "";
      container.appendChild(icon);
    }
    return icon;
  }

  /**
   * Get icon as HTML string
   */
  getHTML(iconName, options = {}) {
    const icon = this.create(iconName, options);
    return icon.outerHTML;
  }

  /**
   * Utility method to get all registered icon names
   */
  getAvailableIcons() {
    return Array.from(this.registry.keys());
  }

  /**
   * Check if an icon exists
   */
  hasIcon(iconName) {
    return this.registry.has(iconName);
  }
}

// Create a global instance
window.IconComponent = new IconComponent();

// Helper functions for easy access
window.createIcon = (name, options) =>
  window.IconComponent.create(name, options);
window.renderIcon = (name, container, options) =>
  window.IconComponent.render(name, container, options);

// Auto-initialize icons with data attributes
document.addEventListener("DOMContentLoaded", function () {
  window.IconComponent.initialize();
});
