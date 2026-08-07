/**
 * API origin.
 *
 * Empty in development, so requests stay same-origin and Vite's proxy
 * forwards `/api` to the local backend. In production the frontend (Vercel)
 * and the API (Railway) are different origins, so `VITE_API_URL` supplies the
 * absolute backend URL at build time.
 *
 * Note this makes production requests genuinely cross-site, which is why the
 * backend must issue its refresh cookie with `SameSite=None; Secure` — see
 * `Settings.cookie_samesite` in backend/config.py, which derives that
 * automatically by comparing PUBLIC_URL and API_URL.
 */
const API_ORIGIN = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");
const BASE = `${API_ORIGIN}/api`;

export { API_ORIGIN };

/**
 * Access-token handling.
 *
 * The access token lives in a module variable, never in localStorage. That is
 * deliberate: anything readable from `localStorage` is readable by injected
 * script, so a single XSS would leak a durable credential. Here the token dies
 * with the tab, and the durable half of the session is the httpOnly refresh
 * cookie, which page JavaScript cannot read at all.
 *
 * The cost is that a page reload starts with no token — handled by AuthContext
 * calling `refresh()` on mount, which the cookie makes succeed silently.
 */
let accessToken = null;
let onUnauthorized = null;

export function setAccessToken(token) {
  accessToken = token || null;
}

export function getAccessToken() {
  return accessToken;
}

/** Registered by AuthContext so a dead session can clear app state once. */
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseError(res) {
  let detail = res.statusText || `Request failed (${res.status})`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") {
      detail = body.detail;
    } else if (Array.isArray(body.detail) && body.detail.length) {
      // FastAPI validation errors: surface the first field message rather than
      // a raw pydantic dump.
      const first = body.detail[0];
      const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : "";
      detail = field ? `${field}: ${first.msg}` : first.msg;
    }
  } catch {
    /* response had no JSON body */
  }
  return new ApiError(detail, res.status);
}

/**
 * A single in-flight refresh shared by every caller. Without this, five
 * concurrent requests hitting an expired token would fire five refreshes — and
 * because refresh tokens rotate, four of them would present an
 * already-rotated token and trip the reuse detector, logging the user out.
 */
let refreshInFlight = null;

async function refreshAccessToken() {
  if (!refreshInFlight) {
    refreshInFlight = fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) throw await parseError(res);
        const body = await res.json();
        setAccessToken(body.access_token);
        return body;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

export { refreshAccessToken };

async function request(path, options = {}, { retryOnAuthFailure = true } = {}) {
  const { body, headers: extraHeaders, ...rest } = options;

  const headers = { ...extraHeaders };
  if (body !== undefined && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const res = await fetch(`${BASE}${path}`, {
    ...rest,
    body,
    headers,
    credentials: "include",
  });

  if (res.status === 401 && retryOnAuthFailure) {
    // The access token expired mid-session. Refresh once and replay the
    // request; the user never sees it.
    try {
      await refreshAccessToken();
    } catch {
      setAccessToken(null);
      onUnauthorized?.();
      throw new ApiError("Your session has expired. Please sign in again.", 401);
    }
    return request(path, options, { retryOnAuthFailure: false });
  }

  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return null;
  return res.json();
}

function qs(params) {
  const clean = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  );
  const s = new URLSearchParams(clean).toString();
  return s ? `?${s}` : "";
}

const json = (data) => JSON.stringify(data);

export const api = {
  // --- Auth (no token required) ---
  authConfig: () => request("/auth/config", {}, { retryOnAuthFailure: false }),
  signup: (payload) =>
    request("/auth/signup", { method: "POST", body: json(payload) }, { retryOnAuthFailure: false }),
  login: (payload) =>
    request("/auth/login", { method: "POST", body: json(payload) }, { retryOnAuthFailure: false }),
  logout: () => request("/auth/logout", { method: "POST" }, { retryOnAuthFailure: false }),
  logoutAll: () => request("/auth/logout-all", { method: "POST" }),
  me: () => request("/auth/me"),
  forgotPassword: (email) =>
    request("/auth/forgot-password", { method: "POST", body: json({ email }) }, { retryOnAuthFailure: false }),
  resetPassword: (token, password) =>
    request("/auth/reset-password", { method: "POST", body: json({ token, password }) }, { retryOnAuthFailure: false }),
  verifyEmail: (token) =>
    request("/auth/verify-email", { method: "POST", body: json({ token }) }, { retryOnAuthFailure: false }),
  resendVerification: () => request("/auth/resend-verification", { method: "POST" }),
  changePassword: (currentPassword, newPassword) =>
    request("/auth/change-password", {
      method: "POST",
      body: json({ current_password: currentPassword, new_password: newPassword }),
    }),
  // Absolute on purpose: this is a full-page navigation to the backend, not a
  // fetch, so a relative path would resolve against the frontend host.
  oauthStartUrl: (provider, next = "/dashboard") =>
    `${BASE}/auth/oauth/${provider}/start?next=${encodeURIComponent(next)}`,

  // --- Account ---
  updateProfile: (fields) => request("/users/me", { method: "PATCH", body: json(fields) }),
  preferences: () => request("/users/me/preferences"),
  updatePreferences: (fields) =>
    request("/users/me/preferences", { method: "PATCH", body: json(fields) }),
  sendTestDigest: () => request("/users/me/send-test-digest", { method: "POST" }),
  recommendationHistory: (limit = 100) => request(`/users/me/recommendation-history?limit=${limit}`),
  unlinkOAuth: (provider) => request(`/users/me/oauth/${provider}`, { method: "DELETE" }),
  deleteAccount: () => request("/users/me", { method: "DELETE" }),

  // --- Discovery data ---
  stats: () => request("/stats"),
  status: () => request("/status"),
  discoveries: (params = {}) => request(`/discoveries${qs(params)}`),
  sources: () => request("/discoveries/sources"),
  companies: (params = {}) => request(`/companies${qs(params)}`),
  companyDetail: (name) => request(`/companies/${encodeURIComponent(name)}`),
  analytics: () => request("/analytics"),
  reports: () => request("/reports"),
  report: (filename) => request(`/reports/${encodeURIComponent(filename)}`),
  timeline: () => request("/timeline"),
  search: (q) => request(`/search${qs({ q })}`),

  // --- Intelligence ---
  recommendations: (limit = 10, excludeFollowed = false) =>
    request(`/recommendations${qs({ limit, exclude_followed: excludeFollowed || undefined })}`),
  recommendationBundle: () => request("/recommendations/bundle"),
  insights: () => request("/insights"),

  // --- Watchlist ---
  watchlist: () => request("/watchlist"),
  follow: (personId) => request(`/watchlist/${personId}`, { method: "POST" }),
  unfollow: (personId) => request(`/watchlist/${personId}`, { method: "DELETE" }),
  updateWatchlistEntry: (personId, fields) =>
    request(`/watchlist/${personId}`, { method: "PATCH", body: json(fields) }),

  // --- Notifications ---
  notifications: (unreadOnly = false) =>
    request(`/notifications${qs({ unread_only: unreadOnly || undefined })}`),
  markNotificationRead: (id) => request(`/notifications/${id}/read`, { method: "POST" }),
  markAllNotificationsRead: () => request("/notifications/read-all", { method: "POST" }),

  // --- Pipeline ---
  runState: () => request("/run/state"),
  triggerRun: () => request("/run", { method: "POST" }),

  exportCsvUrl: () => `${BASE}/export/csv`,
};

/**
 * Downloads go through fetch rather than a plain link because the export
 * endpoint needs an Authorization header, which an <a href> cannot send.
 */
export async function downloadExport() {
  if (!accessToken) await refreshAccessToken();
  const res = await fetch(`${BASE}/export/csv`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    credentials: "include",
  });
  if (!res.ok) throw await parseError(res);

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download =
    res.headers.get("content-disposition")?.match(/filename="?([^"]+)"?/)?.[1] || "helix-export.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function openRunLogSocket() {
  // WebSocket handshakes can't carry an Authorization header, so the backend
  // accepts the same short-lived access token as a query parameter.
  const token = encodeURIComponent(accessToken || "");

  // Derive the ws:// origin from the API origin when one is configured
  // (production), falling back to the current page origin in development
  // where Vite proxies the socket.
  const base = API_ORIGIN || window.location.origin;
  const wsOrigin = base.replace(/^http/, "ws");

  return new WebSocket(`${wsOrigin}/api/run/stream?token=${token}`);
}

export { ApiError };
