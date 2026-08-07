import { useState } from "react";

/**
 * Whether entrance animations should run for a component mounting right now.
 *
 * Why this exists
 * ---------------
 * Entrance animations were written as `initial={{ opacity: 0 }}` +
 * `animate={{ opacity: 1 }}`. That makes the element's *resting* state
 * invisible and relies on an animation frame to reveal it — so if the
 * animation never starts, the content is permanently invisible even though it
 * is fully present in the DOM.
 *
 * That is not hypothetical. Browsers stop servicing `requestAnimationFrame`
 * (which drives Framer Motion) whenever the document is not being painted:
 *
 *   - a page opened in a background tab (middle-click, "open in new tab")
 *   - a window restoring several tabs at startup
 *   - a tab restored from the back/forward cache
 *   - some mobile browsers deferring the first frame until interaction
 *
 * In every one of those cases the page mounts, the animation is scheduled and
 * never runs, and the user sees a blank screen until they scroll — scrolling
 * is simply the cheapest thing that forces the compositor to wake up.
 *
 * Measured directly: with `document.visibilityState === "hidden"`,
 * `setTimeout` still fires but `requestAnimationFrame` does not, and CSS
 * animations *and* transitions are frozen too. So switching animation
 * technique doesn't help — the resting state has to be visible.
 *
 * The decision is made once, synchronously, during the first render. It is
 * never re-enabled later: by the time the document becomes visible the
 * content is already on screen, and starting a fade then would make things
 * appear to flicker after the fact.
 */
export function useEntrance() {
  const [enabled] = useState(() => {
    if (typeof document === "undefined" || typeof window === "undefined") return false;

    // No frames are being produced, so an animation would never complete.
    if (document.visibilityState === "hidden") return false;

    // Honouring this is also what stops the animation from being a barrier
    // for anyone who has asked the OS to reduce motion.
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return false;

    return true;
  });

  return enabled;
}

/** Milliseconds after which content is force-shown regardless of animation
 * state. Comfortably longer than any entrance in the app (~350ms), so it is a
 * no-op in the normal case and only acts as a backstop when frames stall for
 * a reason we could not detect up front. */
export const ENTRANCE_SAFETY_MS = 1500;
