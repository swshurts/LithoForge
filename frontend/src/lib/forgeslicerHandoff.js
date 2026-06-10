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
 *
 * Diagnostics: if a `ready` ping arrives from an unexpected origin we
 * `console.warn` instead of silently dropping it — this is the only
 * way to tell, in the field, whether a stuck handoff is "ForgeSlicer
 * never pinged us" vs "our allowlist is wrong". Symmetric warnings on
 * the ForgeSlicer side make non-allowlisted LithoForge origins obvious
 * when diagnosing across the two tabs.
 */

// Allow overriding the ForgeSlicer origin / handoff URL via env vars so
// we can point at a staging ForgeSlicer build (or a local dev one)
// without rebuilding. Falls back to production.
const FORGESLICER_ORIGIN =
  process.env.REACT_APP_FORGESLICER_ORIGIN || "https://forgeslicer.com";
const FORGESLICER_HANDOFF_URL =
  process.env.REACT_APP_FORGESLICER_HANDOFF_URL ||
  `${FORGESLICER_ORIGIN}/handoff`;

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
    // The currently-deployed ForgeSlicer build (verified against
    // https://forgeslicer.com/static/js/main.0f301007.js on 2026-02-27)
    // only listens for `forgeslicer:handoff:stl` and silently drops
    // any other type. Its STL handler already validates the filename
    // extension against /\.(stl|obj|3mf|glb)$/i, so passing a `.3mf`
    // payload under the legacy `:stl` type Just Works. Once ForgeSlicer
    // ships explicit `:model` support, switch back to:
    //   format === "3mf" ? "forgeslicer:handoff:model" : "forgeslicer:handoff:stl"
    const messageType = "forgeslicer:handoff:stl";

    // Surface our own origin up front — if ForgeSlicer drops our
    // `model` message because we're not on its allowlist, this is the
    // exact string the user needs to paste into ForgeSlicer's config.
    // eslint-disable-next-line no-console
    console.info(
      `[LithoForge→ForgeSlicer] handoff starting from origin ${window.location.origin} → ${FORGESLICER_ORIGIN}`,
    );

    // 1. Open the popup synchronously from the user gesture so popup
    //    blockers don't swallow it. We open `about:blank` first, then
    //    asynchronously mint an SSO token and redirect the popup
    //    through ForgeSlicer's /auth/sso-accept page so the handoff
    //    lands ALREADY SIGNED IN. If minting fails (e.g. user isn't
    //    signed into LithoForge), we fall back to the raw handoff URL
    //    and the user signs in manually on ForgeSlicer — preserving
    //    the pre-SSO behaviour.
    const popup = window.open("about:blank", "_blank");
    if (!popup || popup.closed || typeof popup.closed === "undefined") {
      reject(new PopupBlocked(
        "ForgeSlicer popup was blocked — allow popups for this site to use the handoff.",
      ));
      return;
    }

    // Resolve the popup URL: SSO-wrapped if we can mint a token,
    // raw otherwise. Either way, do it async without blocking the
    // postMessage listener attach below — the popup may load before
    // we redirect it, that's fine (it'll just show the cold handoff
    // page until our redirect lands).
    (async () => {
      try {
        const { API: lithoApi } = await import("./api");
        const mintRes = await fetch(`${lithoApi}/auth/sso-bridge/mint`, {
          credentials: "include",
        });
        if (!mintRes.ok) {
          popup.location.replace(FORGESLICER_HANDOFF_URL);
          return;
        }
        const { token } = await mintRes.json();
        if (!token) {
          popup.location.replace(FORGESLICER_HANDOFF_URL);
          return;
        }
        // Ride through ForgeSlicer's /auth/sso-accept so the cookie
        // is first-party, then it forwards us to /handoff where the
        // existing postMessage flow continues. The handoff path is
        // a relative `return` so SsoAccept's open-redirect guard
        // (regex: /^\/[A-Za-z0-9\-_/]*$/) accepts it.
        const ssoUrl = new URL(`${FORGESLICER_ORIGIN}/auth/sso-accept`);
        ssoUrl.searchParams.set("token", token);
        ssoUrl.searchParams.set("return", "/handoff");
        popup.location.replace(ssoUrl.toString());
      } catch {
        // Any failure → degrade to the cold handoff. Worst case the
        // user sees ForgeSlicer's sign-in screen.
        try { popup.location.replace(FORGESLICER_HANDOFF_URL); } catch {
          /* popup may have been closed by the user */
        }
      }
    })();

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
        // eslint-disable-next-line no-console
        console.info(
          `[LithoForge→ForgeSlicer] posted ${format.toUpperCase()} payload (${
            modelBuffer.byteLength
          } bytes) to ${FORGESLICER_ORIGIN}`,
        );
        finish(resolve)();
      } catch (err) {
        finish(reject)(err);
      }
    };

    const onMessage = (e) => {
      // IMPORTANT — do NOT log every inbound message here. The Emergent
      // preview-logger (emergent-main.js) postMessages every console
      // call back to the same window, so an unconditional
      // `console.info(...)` in this handler creates an infinite feedback
      // loop: log → preview-logger forwards → we log it → ... until
      // Chrome OOMs the render process (which is exactly what crashed
      // the tab during the previous diagnostics round). We restrict
      // logging to messages from the ForgeSlicer origin so the loop
      // can't form.
      //
      // Strict origin check — never trust a postMessage without it.
      if (e.origin !== FORGESLICER_ORIGIN) {
        // Only warn for known forgeslicer:* types from wrong origins
        // (apex vs www, staging vs prod) — anything else is unrelated
        // app traffic (preview-logger, react-devtools, etc.) and must
        // not be logged.
        if (
          e.data &&
          typeof e.data === "object" &&
          typeof e.data.type === "string" &&
          e.data.type.startsWith("forgeslicer:")
        ) {
          // eslint-disable-next-line no-console
          console.warn(
            `[LithoForge] dropped ${e.data.type} from non-allowlisted origin ${e.origin} (expected ${FORGESLICER_ORIGIN})`,
          );
        }
        return;
      }
      // Same origin as ForgeSlicer — safe to log (ForgeSlicer doesn't
      // run our preview-logger, so no feedback loop here).
      // eslint-disable-next-line no-console
      console.info(
        `[LithoForge] inbound from ForgeSlicer data=`,
        e.data,
      );
      if (e.data?.type !== "forgeslicer:handoff:ready") {
        // eslint-disable-next-line no-console
        console.warn(
          `[LithoForge] received message from ForgeSlicer origin but type !== 'forgeslicer:handoff:ready' — got:`,
          e.data,
        );
        return;
      }
      readyReceived = true;
      if (modelBuffer) post();
    };
    window.addEventListener("message", onMessage);

    // 3. Generous 90 s timeout (handles slow 4G + 30 MB files).
    const timer = setTimeout(() => {
      try { popup.close(); } catch { /* noop */ }
      // eslint-disable-next-line no-console
      console.warn(
        `[LithoForge→ForgeSlicer] handoff timed out after 90 s. readyReceived=${readyReceived}, modelBuffered=${!!modelBuffer}. ` +
          (readyReceived
            ? `Our origin ${window.location.origin} is likely NOT on ForgeSlicer's allowlist — add it there.`
            : `ForgeSlicer never sent its 'ready' ping — check ${FORGESLICER_HANDOFF_URL} is reachable and that it posts back to ${window.location.origin}.`),
      );
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

export { FORGESLICER_ORIGIN, FORGESLICER_HANDOFF_URL };
