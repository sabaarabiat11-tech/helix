import { useRef } from "react";
import DnaNetworkScene from "./DnaNetworkScene";

/** Decorative, non-story-mode use of the DNA/network scene — a fixed
 * mid-transition blend (part helix, part network) that just idles and
 * rotates, used as a signature background motif on hero sections rather
 * than the full cinematic timeline. `phase` (0..1) controls the DNA/network
 * balance — higher leans more "neural network" (used on AI Insights). */
export default function AmbientDnaScene({ className, phase = 0.45 }) {
  const phaseRef = useRef(phase);
  return <DnaNetworkScene phase={phaseRef} className={className} />;
}
