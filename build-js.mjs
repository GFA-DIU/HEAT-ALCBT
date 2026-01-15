#!/usr/bin/env node

/**
 * build-js.mjs - Bundle and minify JS files from libs/ to static/js/
 *
 * Usage:
 *   node build-js.mjs          # Production build (minified, no sourcemaps)
 *   node build-js.mjs --dev    # Development build (sourcemaps enabled)
 *   node build-js.mjs --watch  # Watch mode (implies --dev)
 *
 * Configuration:
 *   OUTPUT_DIR - Output directory (default: ./static/js)
 *   LIBS_DIR   - Source directory (default: ./libs)
 *
 * Files prefixed with _ are treated as internal imports and won't be
 * output as separate files (they get merged into their parent).
 */

import { spawn } from "child_process";
import { existsSync, mkdirSync, readdirSync } from "fs";
import { basename, dirname, join } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ============================================================================
// Configuration
// ============================================================================

const OUTPUT_DIR = process.env.JS_OUTPUT_DIR || "./static/js";
const LIBS_DIR = process.env.JS_LIBS_DIR || "./libs";

// ============================================================================
// Parse CLI arguments
// ============================================================================

const args = process.argv.slice(2);
const isDev = args.includes("--dev") || args.includes("--watch");
const isWatch = args.includes("--watch");

// ============================================================================
// Helper functions
// ============================================================================

/**
 * Get all entry files from libs directory (excluding _ prefixed files)
 */
function getEntryFiles(libsDir) {
  const absoluteLibsDir = join(__dirname, libsDir);

  if (!existsSync(absoluteLibsDir)) {
    console.error(`Error: Source directory not found: ${absoluteLibsDir}`);
    process.exit(1);
  }

  const files = readdirSync(absoluteLibsDir);

  return files
    .filter((file) => {
      // Only .js files, exclude _ prefixed (internal imports)
      return file.endsWith(".js") && !file.startsWith("_");
    })
    .map((file) => join(absoluteLibsDir, file));
}

/**
 * Ensure output directory exists
 */
function ensureOutputDir(outputDir) {
  const absoluteOutputDir = join(__dirname, outputDir);

  if (!existsSync(absoluteOutputDir)) {
    mkdirSync(absoluteOutputDir, { recursive: true });
    console.log(`Created output directory: ${absoluteOutputDir}`);
  }

  return absoluteOutputDir;
}

/**
 * Build esbuild arguments for bundling
 */
function buildEsbuildArgs(entryFiles, outputDir, options = {}) {
  const { dev = false, watch = false } = options;

  const args = [
    "esbuild",
    ...entryFiles,
    "--bundle",
    `--outdir=${outputDir}`,
    "--format=iife",
  ];

  // Always minify (production-ready output)
  args.push("--minify");

  // Sourcemaps only in development
  if (dev) {
    args.push("--sourcemap");
  }

  // Watch mode
  if (watch) {
    args.push("--watch");
  }

  // Log level for better output
  args.push("--log-level=info");

  return args;
}

/**
 * Run esbuild via npx
 */
function runEsbuild(args) {
  return new Promise((resolve, reject) => {
    console.log(`\n🔨 Running: npx ${args.join(" ")}\n`);

    const child = spawn("npx", args, {
      stdio: "inherit",
      shell: true,
      cwd: __dirname,
    });

    child.on("close", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`esbuild exited with code ${code}`));
      }
    });

    child.on("error", (err) => {
      reject(err);
    });
  });
}

// ============================================================================
// Main
// ============================================================================

async function main() {
  console.log("━".repeat(60));
  console.log("📦 HEAT-ALCBT JS Bundler");
  console.log("━".repeat(60));
  console.log(`Mode: ${isDev ? "Development" : "Production"}`);
  console.log(`Watch: ${isWatch ? "Enabled" : "Disabled"}`);
  console.log(`Source: ${LIBS_DIR}`);
  console.log(`Output: ${OUTPUT_DIR}`);
  console.log("━".repeat(60));

  // Get entry files
  const entryFiles = getEntryFiles(LIBS_DIR);

  if (entryFiles.length === 0) {
    console.error("Error: No entry files found in libs directory");
    process.exit(1);
  }

  console.log(`\n📂 Entry files (${entryFiles.length}):`);
  entryFiles.forEach((file) => {
    console.log(`   - ${basename(file)}`);
  });

  // Ensure output directory exists
  const absoluteOutputDir = ensureOutputDir(OUTPUT_DIR);

  // Build esbuild arguments
  const esbuildArgs = buildEsbuildArgs(entryFiles, absoluteOutputDir, {
    dev: isDev,
    watch: isWatch,
  });

  try {
    await runEsbuild(esbuildArgs);

    if (!isWatch) {
      console.log("\n✅ Build complete!");
      console.log(`   Output: ${absoluteOutputDir}`);
    }
  } catch (error) {
    console.error("\n❌ Build failed:", error.message);
    process.exit(1);
  }
}

main();
