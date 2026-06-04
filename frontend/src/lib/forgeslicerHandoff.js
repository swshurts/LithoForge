/**
 * "Send to ForgeSlicer" handoff.
 *
 * Opens the ForgeSlicer handoff endpoint in a new tab and ships the
 * current job's STL bytes via `postMessage` once ForgeSlicer signals
 * `forgeslicer:handoff:ready`. The contract — set by ForgeSlicer:
 *
 *   ForgeSlicer → LithoForge:  { type: "forgeslicer:handoff:ready" }
 *   LithoForge → ForgeSlicer:  { type: "forgeslicer:handoff:stl",
 *                                 filename, data: ArrayBuffer,
 *                                 sourceLabel, sourceUrl }
 *
 * This module also handles:
 *  - Popup blockers (caller catches the thrown `PopupBlocked` and toasts)
 *  - The user not signing in (STL fetch returns 401 → throws AuthRequired)
 *  - A handshake timeout (ForgeSlicer never sends `ready`) — abandons
 *    cleanly after 60 s so we don't leak the `message` listener.
 *
 * Origin guard: we ONLY accept `ready` from `FORGESLICER_ORIGIN` and we
 * ONLY post to that same origin. The ArrayBuffer is transferred (zero-
 * copy) so neither side keeps a duplicate of the STL.
 */

const FORGESLICER_ORIGIN = "https://forgeslicer.com";
const FORGESLICER_HANDOFF_URL = `${FORGESLICER_ORIGIN}/handoff`;
const HANDSHAKE_TIMEOUT_MS = 60_000;

export class PopupBlocked extends Error {}
export class AuthRequired extends Error {}
export class HandoffTimeout extends Error {}

/**
 * Kick off the handoff for the given STL URL.
 *
 * @param {object} args
 * @param {string} args.stlUrl    — Absolute URL the auth'd browser can
 *                                  GET to retrieve the STL (e.g.
 *                                  /api/export/{jobId}/stl).
 * @param {string} args.filename  — Suggested filename for ForgeSlicer.
 * @param {string} args.sourceUrl — Deep-link back to this LithoForge job.
 * @returns {Promise<void>}       resolves once we've posted the STL.
 *                                rejects on popup-block / auth / timeout.
 */
export const sendToForgeSlicer = async ({ stlUrl, filename, sourceUrl }) => {
  // 1. Open the popup synchronously from the user gesture. Anything async
  //    BEFORE window.open() will trip Chrome / Safari popup blockers.
  const popup = window.open(FORGESLICER_HANDOFF_URL, "_blank");
  if (!popup || popup.closed || typeof popup.closed === "undefined") {
    throw new PopupBlocked(
      "ForgeSlicer popup was blocked — allow popups for this site to use the handoff.",
    );
  }

  // 2. In parallel: fetch the STL with credentials.
  let arrayBuffer;
  try {
    const res = await fetch(stlUrl, { credentials: "include" });
    if (res.status === 401) {
      popup.close();
      throw new AuthRequired("Sign in to send to ForgeSlicer.");
    }
    if (!res.ok) {
      popup.close();
      throw new Error(`STL fetch failed (${res.status})`);
    }
    arrayBuffer = await res.arrayBuffer();
  } catch (err) {
    if (!(err instanceof AuthRequired)) {
      try { popup.close(); } catch { /* noop */ }
    }
    throw err;
  }

  // 3. Wait for ForgeSlicer to signal readiness, then ship the bytes.
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (fn) => (...args) => {
      if (settled) return;
      settled = true;
      window.removeEventListener("message", onMessage);
      clearTimeout(timer);
      fn(...args);
    };

    const onMessage = (e) => {
      // Strict origin check — never trust a postMessage without it.
      if (e.origin !== FORGESLICER_ORIGIN) return;
      if (e.data?.type !== "forgeslicer:handoff:ready") return;
      try {
        popup.postMessage(
          {
            type: "forgeslicer:handoff:stl",
            filename,
            data: arrayBuffer,
            sourceLabel: "LithoForge",
            sourceUrl,
          },
          FORGESLICER_ORIGIN,
          // Transfer the ArrayBuffer for zero-copy efficiency on large
          // STLs (some can be > 10 MB).
          [arrayBuffer],
        );
        finish(resolve)();
      } catch (err) {
        finish(reject)(err);
      }
    };
    window.addEventListener("message", onMessage);

    const timer = setTimeout(() => {
      try { popup.close(); } catch { /* noop */ }
      finish(reject)(new HandoffTimeout(
        "ForgeSlicer didn't respond within 60 s — please try again.",
      ));
    }, HANDSHAKE_TIMEOUT_MS);
  });
};

export { FORGESLICER_ORIGIN };
