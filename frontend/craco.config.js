// craco.config.js
const path = require("path");
const { execSync } = require("child_process");
require("dotenv").config();

// Bake a sequential build identifier into the bundle so the landing
// page can surface "which iteration of the app is this?" without us
// hand-editing .env each session. Counts total commits in HEAD's
// history and offsets so that THIS build reads `iter-100` — every
// future commit increments the number monotonically. Falls back
// gracefully if git is missing or the repo is shallow.
const BUILD_ID_OFFSET = 11; // chosen so first build prints iter-100
try {
  if (!process.env.REACT_APP_BUILD_ID) {
    const count = parseInt(
      execSync("git rev-list --count HEAD", {
        cwd: __dirname,
        stdio: ["pipe", "pipe", "ignore"],
      })
        .toString()
        .trim(),
      10,
    );
    if (Number.isFinite(count)) {
      process.env.REACT_APP_BUILD_ID = `iter-${count + BUILD_ID_OFFSET}`;
    }
  }
} catch {
  /* no git, no problem — the landing badge just won't render */
}

// Check if we're in development/preview mode (not production build)
// Craco sets NODE_ENV=development for start, NODE_ENV=production for build
const isDevServer = process.env.NODE_ENV !== "production";

// Environment variable overrides
const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
};

// Conditionally load health check modules only if enabled
let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

let webpackConfig = {
  eslint: {
    configure: {
      extends: ["plugin:react-hooks/recommended"],
      rules: {
        "react-hooks/rules-of-hooks": "error",
        "react-hooks/exhaustive-deps": "warn",
        // Newer react-hooks plugin versions enable this in recommended;
        // we use `await refresh()` inside `useEffect` deliberately in
        // several auth + data-fetch hooks. Turning the rule off matches
        // CRA's own React 18 conventions.
        "react-hooks/set-state-in-effect": "off",
      },
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {

      // Add ignored patterns to reduce watched directories
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
        ],
      };

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      return webpackConfig;
    },
  },
};

webpackConfig.devServer = (devServerConfig) => {
  // Add health check endpoints if enabled
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      // Call original setup if exists
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }

      // Setup health endpoints
      setupHealthEndpoints(devServer, healthPluginInstance);

      return middlewares;
    };
  }

  return devServerConfig;
};

// Wrap with visual edits (automatically adds babel plugin, dev server, and overlay in dev mode)
if (isDevServer) {
  try {
    const { withVisualEdits } = require("@emergentbase/visual-edits/craco");
    webpackConfig = withVisualEdits(webpackConfig);
  } catch (err) {
    if (err.code === 'MODULE_NOT_FOUND' && err.message.includes('@emergentbase/visual-edits/craco')) {
      console.warn(
        "[visual-edits] @emergentbase/visual-edits not installed — visual editing disabled."
      );
    } else {
      throw err;
    }
  }
}

module.exports = webpackConfig;
