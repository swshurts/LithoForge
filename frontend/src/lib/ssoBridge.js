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
          // `no-cors` because peers run on a different origin and we
          // don't care about reading the body — we just want the peer
          // to set ITS cookie on ITS domain via the Set-Cookie header.
          //
          // CRITICAL: in no-cors mode the browser STRIPS all custom
          // headers (including X-Forge-Suite-Token). We therefore send
          // the JWT in the request BODY with Content-Type: text/plain
          // — a CORS-safelisted content type that survives no-cors.
          // Peers accept the token from either header or body.
          mode: "no-cors",
          credentials: "include",
          headers: { "Content-Type": "text/plain" },
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
