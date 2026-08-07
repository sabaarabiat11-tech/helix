import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { ENTRANCE_SAFETY_MS, useEntrance } from "../../hooks/useEntrance";

/**
 * The single entrance animation used across the app.
 *
 * Its one hard guarantee: **content is never left invisible.** Two independent
 * safeguards enforce that, because a page that renders blank is a far worse
 * failure than a page that renders without a fade.
 *
 *  1. `useEntrance()` skips the animation entirely when no frames are being
 *     produced (hidden tab) or the user prefers reduced motion. Framer Motion's
 *     `initial={false}` renders straight at the final state.
 *
 *  2. A timer forces the final state after `ENTRANCE_SAFETY_MS` regardless.
 *     Timers keep firing when animation frames don't, so this catches the
 *     cases condition 1 cannot detect — a throttled first frame under heavy
 *     load, for instance. The entrance takes ~350ms, so in normal operation
 *     this fires long after the animation finished and changes nothing.
 *
 * `whenInView` opts into a scroll-triggered reveal. That uses
 * IntersectionObserver, which keeps working when rAF does not — but the same
 * two safeguards still apply, so a stalled observer cannot hide anything
 * either.
 */
export default function Reveal({
  children,
  delay = 0,
  y = 10,
  duration = 0.35,
  whenInView = false,
  className,
  ...rest
}) {
  const animate = useEntrance();
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const [forceShown, setForceShown] = useState(false);

  useEffect(() => {
    if (!animate) return undefined;
    const timer = setTimeout(() => setForceShown(true), ENTRANCE_SAFETY_MS);
    return () => clearTimeout(timer);
  }, [animate]);

  const shown = !animate || forceShown || (whenInView ? inView : true);

  return (
    <motion.div
      ref={ref}
      // `false` means "no entrance" — render at the animate values immediately.
      initial={animate ? { opacity: 0, y } : false}
      animate={shown ? { opacity: 1, y: 0 } : undefined}
      transition={{ duration, delay, ease: [0.22, 1, 0.36, 1] }}
      // An inline style outranks Framer Motion's animated values, so this is
      // what makes the backstop authoritative rather than advisory.
      style={forceShown ? { opacity: 1, transform: "none" } : undefined}
      className={className}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
