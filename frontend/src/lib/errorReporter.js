// Captures every uncaught JS error & promise rejection in the browser
// and ships it to /api/client-error so we can debug Safari iPad issues
// without needing screenshots from the user.

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const ENDPOINT = `${BACKEND}/api/client-error`;

let lastSig = "";
let lastTime = 0;

const send = (payload) => {
  // De-duplicate identical bursts within 2s so a slider that fires 30
  // identical errors per drag doesn't flood logs.
  const sig = `${payload.message}|${payload.source}|${payload.line}`;
  const now = Date.now();
  if (sig === lastSig && now - lastTime < 2000) return;
  lastSig = sig;
  lastTime = now;
  try {
    const body = JSON.stringify({
      ...payload,
      user_agent: navigator.userAgent,
      url: window.location.href,
    });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(
        ENDPOINT,
        new Blob([body], { type: "application/json" })
      );
    } else {
      fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive: true,
      }).catch(() => {});
    }
  } catch {
    /* swallow — never break the app trying to report errors */
  }
};

/**
 * Wraps a callback so any synchronous error inside it is reported with
 * full message + stack (Safari can't sanitize errors caught inside our
 * own code the way it does cross-origin window.onerror events).
 */
export const safeCb = (label, fn) => (...args) => {
  try {
    return fn(...args);
  } catch (e) {
    send({
      message: `[${label}] ${e?.message || e}`,
      stack: e?.stack || "",
      source: "safeCb",
      line: 0,
      column: 0,
    });
    // Re-throw so React/Radix can still handle it if they want.
    throw e;
  }
};

export const installErrorReporter = () => {
  window.addEventListener("error", (e) => {
    send({
      message: e.message || "(no message)",
      stack: e.error?.stack || "",
      source: e.filename || "",
      line: e.lineno || 0,
      column: e.colno || 0,
    });
  });
  window.addEventListener("unhandledrejection", (e) => {
    const r = e.reason;
    send({
      message: `Unhandled rejection: ${r?.message || r || "(unknown)"}`,
      stack: r?.stack || "",
      source: "",
      line: 0,
      column: 0,
    });
  });
};
