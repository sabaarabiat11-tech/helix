import { Lottie } from "../lib/lottie";
import helixMark from "../assets/lottie/helix-mark.json";

/** The brand mark: plays the reveal once, then holds on the settled lockup. */
export default function HelixMark({ size = 32, className = "" }) {
  return (
    <div style={{ width: size, height: size }} className={className}>
      <Lottie animationData={helixMark} loop={false} autoplay className="w-full h-full" />
    </div>
  );
}
