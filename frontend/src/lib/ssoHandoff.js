/** Outbound peer handoff via redirect (not fetch).
 *
 *  Replaces the silent `fanOutSsoBridge()` cross-origin fetch fan-out.
 *  Fetch fan-out hits the third-party-cookie wall in every modern
 *  browser; navigation-based handoff sidesteps it because the
 *  resulting Set-Cookie is first-party on the peer.
 *
 *  Usage:
 *      const onClick = (e) => {
 *        e.preventDefault();
 *        if (user) openInPeer("https://forgeslicer.com", "/workspace");
 *        else window.open("https://forgeslicer.com", "_blank");
 *      };
 */
import { API } from "./api";

export async function openInPeer(peerOrigin, returnPath = "/") {
  try {
    const mintRes = await fetch(`${API}/auth/sso-bridge/mint`, {
      credentials: "include",
    });
    if (!mintRes.ok) {
      // Not signed in here either — open the peer cold; they can sign
      // in there directly.
      window.open(peerOrigin + returnPath, "_blank");
      return;
    }
    const { token } = await mintRes.json();
    if (!token) {
      window.open(peerOrigin + returnPath, "_blank");
      return;
    }
    const url = new URL(peerOrigin + "/auth/sso-accept");
    url.searchParams.set("token", token);
    url.searchParams.set("return", returnPath);
    window.open(url.toString(), "_blank", "noopener");
  } catch {
    // Network blip or peer offline — degrade to a cold open.
    window.open(peerOrigin + returnPath, "_blank");
  }
}
