import { useEffect, useRef, useState } from "react";
import { useMotionValue, animate } from "framer-motion";

/** Counts up from its previous value to `value` whenever it changes — used
 * for the dashboard stat cards so live updates (e.g. after a run finishes)
 * feel alive instead of just snapping to a new number.
 *
 * Note: a MotionValue can't be passed as JSX children and expect live
 * updates — that binding only works for style/props on a <motion.*>
 * element. For arbitrary text content, subscribe via animate()'s onUpdate
 * callback and drive real React state instead. */
export default function AnimatedCounter({ value, className }) {
  const motionValue = useMotionValue(0);
  const [display, setDisplay] = useState(0);
  const hasMounted = useRef(false);

  useEffect(() => {
    const controls = animate(motionValue, value ?? 0, {
      duration: hasMounted.current ? 0.6 : 0.9,
      ease: "easeOut",
      onUpdate: (v) => setDisplay(Math.round(v)),
    });
    hasMounted.current = true;
    return controls.stop;
  }, [value, motionValue]);

  return <span className={className}>{display.toLocaleString("en-US")}</span>;
}
