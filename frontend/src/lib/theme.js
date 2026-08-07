// Single source of truth for theme constants. The bootstrap script in
// index.html (which MUST stay a plain inline script, not an ES module, so
// it can run before first paint) duplicates this key/default by necessity —
// if you change either value here, update index.html to match.
export const THEME_STORAGE_KEY = "helix-theme";
export const DEFAULT_THEME = "dark";

export function readAppliedTheme() {
  // The bootstrap script already set this on <html> before React mounted —
  // read it back rather than recomputing, so there is exactly one place
  // (index.html's bootstrap script) that ever *decides* the initial theme.
  const attr = document.documentElement.getAttribute("data-theme");
  return attr === "light" || attr === "dark" ? attr : DEFAULT_THEME;
}

export function persistTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    /* localStorage unavailable (private browsing, etc.) — theme still applies for this session */
  }
}

/**
 * Apply a theme coming from the server (the signed-in user's saved
 * preference). Also written to localStorage so the bootstrap script in
 * index.html paints the right theme on the *next* load, before any network
 * call has had a chance to run — that's what prevents a flash of the wrong
 * theme on reload.
 */
export function applyTheme(theme) {
  if (theme !== "light" && theme !== "dark") return;
  persistTheme(theme);
}
