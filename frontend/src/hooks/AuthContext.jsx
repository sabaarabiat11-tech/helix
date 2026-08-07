import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  refreshAccessToken,
  setAccessToken,
  setUnauthorizedHandler,
} from "../api/client";
import { applyTheme, readAppliedTheme } from "../lib/theme";

const AuthContext = createContext(null);

/** Refresh a little before the token actually expires, so an in-flight request
 * never races the expiry. */
const REFRESH_MARGIN_SECONDS = 60;

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [preferences, setPreferences] = useState(null);
  const [linkedProviders, setLinkedProviders] = useState([]);
  const [hasPassword, setHasPassword] = useState(true);
  // `initializing` covers the first silent refresh on page load. Routes must
  // wait for it, otherwise a reload briefly bounces a signed-in user to /login.
  const [initializing, setInitializing] = useState(true);

  const refreshTimer = useRef(null);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setPreferences(null);
    setLinkedProviders([]);
    if (refreshTimer.current) {
      clearTimeout(refreshTimer.current);
      refreshTimer.current = null;
    }
  }, []);

  const applyAccountPayload = useCallback((payload) => {
    if (!payload) return;
    if (payload.user) setUser(payload.user);
    if (payload.preferences) {
      setPreferences(payload.preferences);
      // The server is the source of truth for theme across devices — this is
      // what makes the same account look the same on phone and desktop.
      if (payload.preferences.theme) applyTheme(payload.preferences.theme);
    }
    if (payload.linked_providers) setLinkedProviders(payload.linked_providers);
    if (typeof payload.has_password === "boolean") setHasPassword(payload.has_password);
  }, []);

  const scheduleRefresh = useCallback((expiresIn) => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    const delay = Math.max(30, (expiresIn || 1800) - REFRESH_MARGIN_SECONDS) * 1000;
    refreshTimer.current = setTimeout(async () => {
      try {
        const result = await refreshAccessToken();
        scheduleRefresh(result.expires_in);
      } catch {
        clearSession();
      }
    }, delay);
  }, [clearSession]);

  const loadAccount = useCallback(async () => {
    const payload = await api.me();
    applyAccountPayload(payload);
    return payload;
  }, [applyAccountPayload]);

  /** Adopt a session returned by signup/login. */
  const adoptSession = useCallback(async (session) => {
    setAccessToken(session.access_token);
    setUser(session.user);
    scheduleRefresh(session.expires_in);
    await loadAccount();
  }, [loadAccount, scheduleRefresh]);

  // --- Bootstrap: try to resume a session from the httpOnly cookie ---
  useEffect(() => {
    let cancelled = false;

    setUnauthorizedHandler(() => {
      if (!cancelled) clearSession();
    });

    (async () => {
      try {
        const session = await refreshAccessToken();
        if (cancelled) return;
        setUser(session.user);
        scheduleRefresh(session.expires_in);
        await loadAccount();
      } catch {
        // No valid cookie — an ordinary signed-out visit, not an error.
        if (!cancelled) clearSession();
      } finally {
        if (!cancelled) setInitializing(false);
      }
    })();

    return () => {
      cancelled = true;
      setUnauthorizedHandler(null);
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, [clearSession, loadAccount, scheduleRefresh]);

  // --- Actions ---
  const login = useCallback(async (email, password) => {
    const session = await api.login({ email, password });
    await adoptSession(session);
    return session.user;
  }, [adoptSession]);

  const signup = useCallback(async (email, password, name) => {
    const session = await api.signup({ email, password, name });
    await adoptSession(session);
    return session.user;
  }, [adoptSession]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      // Clear locally even if the network call failed — the user asked to be
      // signed out and the UI must reflect that immediately.
      clearSession();
    }
  }, [clearSession]);

  const updatePreferences = useCallback(async (fields) => {
    const updated = await api.updatePreferences(fields);
    setPreferences(updated);
    if (updated.theme) applyTheme(updated.theme);
    return updated;
  }, []);

  const updateProfile = useCallback(async (fields) => {
    const { user: updated } = await api.updateProfile(fields);
    setUser(updated);
    return updated;
  }, []);

  /**
   * Theme is persisted per account when signed in, and locally otherwise, so a
   * signed-out visitor's choice still sticks in that browser.
   */
  const setTheme = useCallback(async (theme) => {
    applyTheme(theme);
    setPreferences((prev) => (prev ? { ...prev, theme } : prev));
    if (user) {
      try {
        await api.updatePreferences({ theme });
      } catch {
        /* the local change already applied; a failed sync is not worth an error toast */
      }
    }
  }, [user]);

  const value = useMemo(() => ({
    user,
    preferences,
    linkedProviders,
    hasPassword,
    initializing,
    isAuthenticated: Boolean(user),
    theme: preferences?.theme || readAppliedTheme(),
    login,
    signup,
    logout,
    setTheme,
    updateProfile,
    updatePreferences,
    reloadAccount: loadAccount,
    adoptSession,
  }), [
    user, preferences, linkedProviders, hasPassword, initializing,
    login, signup, logout, setTheme, updateProfile, updatePreferences, loadAccount, adoptSession,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
