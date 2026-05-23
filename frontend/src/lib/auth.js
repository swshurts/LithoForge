// Auth context + helpers wrapping Emergent-managed Google Auth.
//
// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
//
// This app is NOT auth-gated — auth is opt-in to sync presets across
// devices. The provider exposes `user` (or `null` for anonymous) plus
// `login()` / `logout()` helpers.

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { api } from "./api";

const AuthCtx = createContext({
  user: null,
  loading: true,
  login: () => {},
  logout: async () => {},
  refresh: async () => {},
});

export const useAuth = () => useContext(AuthCtx);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me", { withCredentials: true });
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // If we're returning from the OAuth callback, AuthCallback will run
    // /auth/session first; skip /me here so the cookie is set before we
    // poll the server.
    if (window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }
    refresh();
  }, [refresh]);

  const login = useCallback(() => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/";
    window.location.href =
      `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout", null, { withCredentials: true });
    } catch {
      /* ignore — local state always wins for UX */
    }
    setUser(null);
  }, []);

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
};

/** Handles the OAuth return fragment. Mount above the app so it runs
 *  before any /auth/me checks. */
export const AuthCallbackHandler = ({ onComplete }) => {
  const [processing, setProcessing] = useState(
    () =>
      typeof window !== "undefined" &&
      window.location.hash?.includes("session_id=")
  );
  const hasRun = useRef(false);

  useEffect(() => {
    if (!processing) return;
    if (hasRun.current) return;
    hasRun.current = true;
    const params = new URLSearchParams(window.location.hash.slice(1));
    const sessionId = params.get("session_id");
    if (!sessionId) {
      setProcessing(false);
      return;
    }
    (async () => {
      try {
        await api.post(
          "/auth/session",
          { session_id: sessionId },
          { withCredentials: true }
        );
      } catch {
        /* fall through — user will see anonymous state */
      } finally {
        // Strip the fragment so the URL stays clean and reloads work.
        const cleanUrl = window.location.pathname + window.location.search;
        window.history.replaceState({}, document.title, cleanUrl);
        setProcessing(false);
        if (onComplete) onComplete();
      }
    })();
  }, [processing, onComplete]);

  if (!processing) return null;
  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-zinc-950 text-zinc-100"
      data-testid="auth-callback-loader"
    >
      <div className="font-mono text-[11px] uppercase tracking-[0.25em] text-zinc-300 animate-pulse">
        Signing you in…
      </div>
    </div>
  );
};
