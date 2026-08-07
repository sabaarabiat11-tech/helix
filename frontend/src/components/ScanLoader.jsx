import { Lottie } from "../lib/lottie";
import scanLoader from "../assets/lottie/scan-loader.json";

/** Small looping "scanning" pulse — used while the pipeline runs or data loads. */
export default function ScanLoader({ size = 20, className = "" }) {
  return (
    <div style={{ width: size, height: size }} className={className}>
      <Lottie animationData={scanLoader} loop autoplay className="w-full h-full" />
    </div>
  );
}
