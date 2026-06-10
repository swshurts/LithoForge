/** Forge Suite SSO bridge — fan out from LithoForge to peer apps after
 *  any successful sign-in. Sister of ForgeSlicer's `ssoBridge.js`.
 *
 *  After a fresh login, mint a short-lived JWT and POST it to every
 *  peer in the Forge Suite. Each peer accepts the token, sets its own
 *  session cookie, and the user lands signed-in on next visit.
 *
 *  Errors are swallowed by design: if the peer is offline or the
 *  cross-origin POST fails for any reason, the local LithoForge sign-in
 *  still works perfectly.
 */
import { API } from "./api";

let inFlight = false;

export async function fanOutSsoBridge() {
  if (inFlight) return;
  inFlight = true;
  try {
    const mintRes = await fetch(`${API}/auth/sso-bridge/mint`, {
      credentials: "include",
    });
    if (!mintRes.ok) return;
    const { token, peers } = await mintRes.json();
    if (!token || !Array.isArray(peers) || peers.length === 0) return;
    await Promise.allSettled(
      peers.map((peer) =>
        fetch(`${peer}/api/auth/sso-bridge`, {
          method: "POST",
          // CORS mode — peers add this app to their CORSMiddleware
          // allowlist (via FORGE_SUITE_PEERS env). Browser does a
          // proper preflight, custom headers work, and we can read
          // the response if we want to surface bridge status in UI.
          mode: "cors",
          credentials: "include",
          // Body fallback kept defensively: any peer still running
          // an older accept handler that reads only the header
          // continues to work; peers running the new dual-path code
          // can read it from either spot.
          headers: {
            "Content-Type": "text/plain",
            "X-Forge-Suite-Token": token,
          },
          body: token,
        }),
      ),
    );
  } catch (err) {
    // Intentionally non-fatal — the local login still succeeded.
    console.warn("[forge-suite/sso] bridge fan-out failed:", err);
  } finally {
    inFlight = false;
  }
}
