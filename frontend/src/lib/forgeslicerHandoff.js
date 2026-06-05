/**
 * "Send to ForgeSlicer" handoff.
 *
 * Opens the ForgeSlicer handoff endpoint in a new tab and ships the
 * current job's 3MF bytes via `postMessage` once ForgeSlicer signals
 * `forgeslicer:handoff:ready`. We send the 3MF (not STL) because the
 * 3MF carries per-filament `<object>` entries tagged with filament_slot
 * + RGB hex + filament_name — ForgeSlicer can recover the full colour
 * palette directly from those objects without re-deriving them.
 *
 * Wire contract:
 *
 *   ForgeSlicer → LithoForge:  { type: "forgeslicer:handoff:ready" }
 *   LithoForge → ForgeSlicer:  { type: "forgeslicer:handoff:model",
 *                                 format: "3mf",
 *                                 filename, data: ArrayBuffer,
 *                                 sourceLabel, sourceUrl }
 *
 * (Older message type `forgeslicer:handoff:stl` is still emitted on
 * the fallback path when a caller passes the legacy `stlUrl` arg, so
 * a stale ForgeSlicer build that hasn't shipped the new listener yet
 * keeps working — see `_postPayload` below.)
 *
 * This module also handles:
 *  - Popup blockers (caller catches the thrown `PopupBlocked` and toasts)
 *  - The user not signing in (model fetch returns 401 → throws AuthRequired)
 *  - A handshake timeout (ForgeSlicer never sends `ready`) — abandons
 *    cleanly after 90 s so we don't leak the `message` listener.
 *
 * Origin guard: we ONLY accept `ready` from `FORGESLICER_ORIGIN` and we
 * ONLY post to that same origin. The ArrayBuffer is transferred (zero-
 * copy) so neither side keeps a duplicate of the model bytes.
 */

const FORGESLICER_ORIGIN = "https://forgeslicer.com";
const FORGESLICER_HANDOFF_URL = `${FORGESLICER_ORIGIN}/handoff`;

export class PopupBlocked extends Error {}
export class AuthRequired extends Error {}
export class HandoffTimeout extends Error {}

/**
 * Kick off the handoff for the given STL URL.
 *
 * Race-condition note: ForgeSlicer mounts its handoff page fast and
 * fires `{type:"forgeslicer:handoff:ready"}` within ~200 ms. The STL
 * fetch can take several seconds, especially for 10 MB+ files. So we
 * MUST attach our `message` listener immediately after window.open()
 * — before awaiting fetch — otherwise ForgeSlicer's `ready` ping
 * arrives before our listener exists, gets silently dropped, and the
 * sister page hits its own 20 s timeout showing "Handoff didn't
 * complete". The implementation below uses a small state machine:
 *
 *   [POPUP_OPENED] ──ready arrives──▶ [READY_BUFFERED] ──fetch done──▶ POST
 *           │                                 │
 *           └───────fetch done────────▶ [STL_READY] ──ready arrives──▶ POST
 *
 * Either ordering ends with a single postMessage; once that happens
 * the listener is removed and the timeout is cleared.
 *
 * @param {object} args
 * @param {string} args.stlUrl    — Absolute URL the auth'd browser can
 *                                  GET to retrieve the STL.
 * @param {string} args.filename  — Suggested filename for ForgeSlicer.
 * @param {string} args.sourceUrl — Deep-link back to this LithoForge job.
 * @returns {Promise<void>}       resolves once we've posted the STL.
 *                                rejects on popup-block / auth / timeout.
 */
export const sendToForgeSlicer = ({
  modelUrl,
  filename,
  sourceUrl,
  // Legacy alias — older callers may still pass `stlUrl`.
  stlUrl,
}) =>
  new Promise((resolve, reject) => {
    const url = modelUrl || stlUrl;
    // Detect the format from the filename / URL extension so we can
    // tag the postMessage correctly (3mf carries per-colour metadata;
    // stl is flat geometry).
    const ext = (filename || url || "").toLowerCase().split(".").pop();
    const format = ext === "3mf" ? "3mf" : "stl";
    const messageType =
      format === "3mf"
        ? "forgeslicer:handoff:model"
        : "forgeslicer:handoff:stl"; // legacy

    // 1. Open the popup synchronously from the user gesture.
    const popup = window.open(FORGESLICER_HANDOFF_URL, "_blank");
    if (!popup || popup.closed || typeof popup.closed === "undefined") {
      reject(new PopupBlocked(
        "ForgeSlicer popup was blocked — allow popups for this site to use the handoff.",
      ));
      return;
    }

    // 2. Pre-attach the listener IMMEDIATELY so we don't miss the
    //    `ready` ping that ForgeSlicer fires before our fetch resolves.
    let readyReceived = false;
    let modelBuffer = null;
    let settled = false;

    const cleanup = () => {
      settled = true;
      window.removeEventListener("message", onMessage);
      clearTimeout(timer);
    };

    const finish = (fn) => (...args) => {
      if (settled) return;
      cleanup();
      fn(...args);
    };

    const post = () => {
      if (settled) return;
      try {
        popup.postMessage(
          {
            type: messageType,
            format, // "3mf" | "stl"
            filename,
            data: modelBuffer,
            sourceLabel: "LithoForge",
            sourceUrl,
          },
          FORGESLICER_ORIGIN,
          [modelBuffer], // zero-copy transfer
        );
        finish(resolve)();
      } catch (err) {
        finish(reject)(err);
      }
    };

    const onMessage = (e) => {
      // Strict origin check — never trust a postMessage without it.
      if (e.origin !== FORGESLICER_ORIGIN) return;
      if (e.data?.type !== "forgeslicer:handoff:ready") return;
      readyReceived = true;
      if (modelBuffer) post();
    };
    window.addEventListener("message", onMessage);

    // 3. Generous 90 s timeout (handles slow 4G + 30 MB files).
    const timer = setTimeout(() => {
      try { popup.close(); } catch { /* noop */ }
      finish(reject)(new HandoffTimeout(
        "ForgeSlicer didn't respond within 90 s — please try again.",
      ));
    }, 90_000);

    // 4. Fetch the model bytes in parallel. If `ready` is already
    //    buffered when the fetch resolves, fire immediately.
    (async () => {
      try {
        const res = await fetch(url, { credentials: "include" });
        if (res.status === 401) {
          try { popup.close(); } catch { /* noop */ }
          finish(reject)(new AuthRequired("Sign in to send to ForgeSlicer."));
          return;
        }
        if (!res.ok) {
          try { popup.close(); } catch { /* noop */ }
          finish(reject)(new Error(`Model fetch failed (${res.status})`));
          return;
        }
        modelBuffer = await res.arrayBuffer();
        if (readyReceived) post();
      } catch (err) {
        try { popup.close(); } catch { /* noop */ }
        finish(reject)(err);
      }
    })();
  });

export { FORGESLICER_ORIGIN };
