/** /auth/sso-accept — first-party token exchange page.
 *
 *  A peer app (ForgeSlicer today) navigates the user here with
 *  `?token=<JWT>&return=/studio`. We POST the token same-origin to our
 *  own `/api/auth/sso-bridge` so the resulting `Set-Cookie` is
 *  FIRST-PARTY (browsers don't partition first-party cookies; works on
 *  Firefox/Safari/Brave/Chrome regardless of ETP / ITP / 3p settings).
 *
 *  After exchange we strip the `?token=` from the URL bar (so the JWT
 *  doesn't sit in history or leak via Referer), refresh the auth
 *  context, and navigate to the safe `return` path.
 */
import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, AlertCircle } from "lucide-react";
import { API } from "../lib/api";
import { useAuth } from "../lib/auth";

// Only allow same-site relative paths to prevent open-redirect via ?return=
const VALID_RETURN = /^\/[A-Za-z0-9\-_/]*$/;

export default function SsoAccept() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { refresh } = useAuth();
  const [error, setError] = useState("");

  useEffect(() => {
    const token = params.get("token") || "";
    const ret = params.get("return") || "/";
    const safeReturn = VALID_RETURN.test(ret) ? ret : "/";

    if (!token) {
      queueMicrotask(() => setError("Missing SSO token."));
      return;
    }

    (async () => {
      try {
        const r = await fetch(`${API}/auth/sso-bridge`, {
          method: "POST",
          credentials: "include",
          headers: { "X-Forge-Suite-Token": token },
        });
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          throw new Error(body.detail || `Sign-in failed (${r.status}).`);
        }
        // Wipe the JWT from the address bar BEFORE refresh() so any
        // re-render can't accidentally re-trigger the exchange under
        // React StrictMode double-invoke.
        window.history.replaceState({}, "", safeReturn);
        try {
          await refresh?.();
        } catch {
          /* refresh failures still allow navigation — user can retry */
        }
        navigate(safeReturn, { replace: true });
      } catch (err) {
        setError(err.message || "Could not sign you in.");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center px-4"
      data-testid="sso-accept-page"
    >
      <div className="max-w-md w-full bg-zinc-900 border border-zinc-800 p-8 text-center">
        {!error && (
          <>
            <Loader2
              size={28}
              className="animate-spin text-amber-400 mx-auto mb-4"
              data-testid="sso-accept-loading"
            />
            <h1 className="text-lg font-semibold">Signing you in…</h1>
            <p className="text-xs text-zinc-500 mt-2 font-mono">
              Bridging your Forge Suite session.
            </p>
          </>
        )}
        {error && (
          <>
            <AlertCircle
              size={28}
              className="text-rose-400 mx-auto mb-4"
              data-testid="sso-accept-error"
            />
            <h1 className="text-lg font-semibold">Sign-in failed</h1>
            <p className="text-xs text-zinc-500 mt-2 font-mono">{error}</p>
            <button
              onClick={() => navigate("/", { replace: true })}
              data-testid="sso-accept-retry"
              className="mt-5 h-10 px-4 bg-zinc-100 text-zinc-950 text-sm font-bold uppercase tracking-[0.18em] font-mono"
            >
              Continue to LithoForge
            </button>
          </>
        )}
      </div>
    </div>
  );
}
