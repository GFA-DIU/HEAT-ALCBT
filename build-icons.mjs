import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const excludedFromCurrentColor = ["google"];

// Configuration
const config = {
  iconsDir: path.join(__dirname, "./static/assets/icons"),
  outputFile: path.join(__dirname, "./static/js/icons.js"),
  // Optional: Generate TypeScript definitions
  // generateTypes: true,
  // typesFile: path.join(__dirname, "../src/types/icons.d.ts"),
};

/**
 * Clean and optimize SVG content
 */
function cleanSVG(svgContent, fileName) {
  let cleaned = svgContent
    // Remove XML declaration
    .replace(/^\s*<\?xml[^>]*>\s*/, "")
    // Remove comments
    .replace(/<!--[\s\S]*?-->/g, "")
    // Remove DOCTYPE
    .replace(/<!DOCTYPE[^>]*>/g, "")
    // Normalize whitespace
    .replace(/\s+/g, " ")
    // Remove extra spaces around tags
    .replace(/>\s+</g, "><")
    .trim();

  // Validate SVG
  if (!cleaned.startsWith("<svg")) {
    console.warn(`⚠️  Warning: ${fileName} doesn't start with <svg> tag`);
  }

  return cleaned;
}

/**
 * Generate icon name from filename
 */
function getIconName(filename) {
  return path
    .basename(filename, ".svg")
    .replace(/[^a-zA-Z0-9]/g, "-") // Replace special chars with hyphens
    .replace(/-+/g, "-") // Replace multiple hyphens with single
    .replace(/^-|-$/g, ""); // Remove leading/trailing hyphens
}

/**
 * Generate TypeScript type definitions
 */
// function generateTypeDefinitions(iconNames) {
//   const iconNamesString = iconNames.map((name) => `  | '${name}'`).join("\n");

//   return `// Auto-generated file - do not edit manually
// // Generated on: ${new Date().toISOString()}

// export type IconName =
// ${iconNamesString};

// export interface IconProps {
//   size?: number;
//   color?: string;
//   className?: string;
// }

// export interface IconComponent {
//   create(iconName: IconName, options?: IconProps): SVGElement;
//   render(iconName: IconName, container: HTMLElement, options?: IconProps): SVGElement;
//   getHTML(iconName: IconName, options?: IconProps): string;
// }

// declare global {
//   interface Window {
//     IconComponent: IconComponent;
//     createIcon: (name: IconName, options?: IconProps) => SVGElement;
//     renderIcon: (name: IconName, container: HTMLElement, options?: IconProps) => SVGElement;
//   }
// }
// `;
// }

/**
 * Main build function
 */
async function buildIcons() {
  console.log("🔨 Building icon registry...");

  try {
    // Check if icons directory exists
    if (!fs.existsSync(config.iconsDir)) {
      throw new Error(`Icons directory not found: ${config.iconsDir}`);
    }

    // Get all SVG files
    const files = fs
      .readdirSync(config.iconsDir)
      .filter((file) => file.endsWith(".svg"))
      .sort(); // Sort for consistent output

    if (files.length === 0) {
      throw new Error("No SVG files found in icons directory");
    }

    console.log(`📁 Found ${files.length} SVG files`);

    // Process each SVG file
    const iconsRegistry = {};
    const iconNames = [];
    let processedCount = 0;
    let errorCount = 0;

    for (const file of files) {
      try {
        const filePath = path.join(config.iconsDir, file);
        const iconName = getIconName(file);
        const svgContent = fs.readFileSync(filePath, "utf-8");
        const cleanedContent = cleanSVG(svgContent, file);

        iconsRegistry[iconName] = cleanedContent;
        iconNames.push(iconName);
        processedCount++;

        console.log(`  ✅ ${file} → ${iconName}`);
      } catch (error) {
        console.error(`  ❌ Error processing ${file}:`, error.message);
        errorCount++;
      }
    }

    // Generate the JavaScript registry file
    const jsOutput = generateJSRegistry(iconsRegistry);

    // Ensure output directory exists
    const outputDir = path.dirname(config.outputFile);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    // Write the registry file
    fs.writeFileSync(config.outputFile, jsOutput);
    console.log(`📝 Generated: ${config.outputFile}`);

    // Generate TypeScript definitions if enabled
    // if (config.generateTypes && iconNames.length > 0) {
    //   const typesOutput = generateTypeDefinitions(iconNames);
    //   const typesDir = path.dirname(config.typesFile);

    //   if (!fs.existsSync(typesDir)) {
    //     fs.mkdirSync(typesDir, { recursive: true });
    //   }

    //   fs.writeFileSync(config.typesFile, typesOutput);
    //   console.log(`📝 Generated: ${config.typesFile}`);
    // }

    // Summary
    console.log(`\n🎉 Build complete!`);
    console.log(`   ✅ Processed: ${processedCount} icons`);
    if (errorCount > 0) {
      console.log(`   ❌ Errors: ${errorCount} icons`);
    }
    console.log(
      `   📦 Registry size: ${(
        Buffer.byteLength(jsOutput, "utf8") / 1024
      ).toFixed(2)} KB`
    );
  } catch (error) {
    console.error("❌ Build failed:", error.message);
    process.exit(1);
  }
}

/**
 * Generate the JavaScript registry file content
 */
function generateJSRegistry(iconsRegistry) {
  const iconEntries = Object.entries(iconsRegistry)
    .map(([name, content]) => {
      // Escape backticks and other special characters in the SVG content
      const escapedContent = content
        .replace(/\\/g, "\\\\")
        .replace(/`/g, "\\`")
        .replace(/\${/g, "\\${");

      return `  '${name}': \`${escapedContent}\``;
    })
    .join(",\n");

  return `// Auto-generated file - do not edit manually
// Generated on: ${new Date().toISOString()}
// Total icons: ${Object.keys(iconsRegistry).length}

export const ICONS_REGISTRY = {
${iconEntries}
};

// Export icon names for validation
export const ICON_NAMES = [
${Object.keys(iconsRegistry)
  .map((name) => `  '${name}'`)
  .join(",\n")}
];

export const EXCLUDED_FROM_CURRENT_COLOR = [
${excludedFromCurrentColor.map((name) => `  '${name}'`).join(",\n")}
];

// Helper function to check if an icon exists
export function hasIcon(name) {
  return name in ICONS_REGISTRY;
}

// Get all available icon names
export function getAvailableIcons() {
  return Object.keys(ICONS_REGISTRY);
}
`;
}

buildIcons();

export { buildIcons };
