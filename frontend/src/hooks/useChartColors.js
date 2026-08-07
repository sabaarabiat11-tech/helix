import { useEffect, useState } from "react";

const VARS = [
  "--color-accent",
  "--color-accent-2",
  "--color-accent-strong",
  "--color-highlight",
  "--color-border",
  "--color-text",
  "--color-text-dim",
  "--color-text-faint",
  "--color-surface",
  "--color-surface-2",
  "--color-success",
  "--color-warning",
  "--color-danger",
];

function readVars() {
  const styles = getComputedStyle(document.documentElement);
  const out = {};
  for (const v of VARS) {
    out[v.replace("--color-", "")] = styles.getPropertyValue(v).trim();
  }
  return out;
}

/**
 * Chart series palette, ordered for categorical use.
 *
 * Recharts needs literal colour strings, not CSS variables, so the values are
 * read from computed styles and must be re-read whenever the theme changes.
 * This watches the `data-theme` attribute directly rather than subscribing to
 * a theme hook, because the theme can now be changed from several places — the
 * topbar toggle, the settings page, or the server preference applied at
 * sign-in — and the DOM attribute is the one signal common to all of them.
 */
export function useChartColors() {
  const [colors, setColors] = useState(readVars);

  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      // A frame's delay lets the new custom-property values settle before
      // computed styles are read back.
      requestAnimationFrame(() => setColors(readVars()));
    });
    observer.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return {
    ...colors,
    series: [colors.accent, colors["accent-2"], colors.highlight, colors.success, colors.warning, colors.danger],
  };
}
