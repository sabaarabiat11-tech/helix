// lottie-react's default export sometimes arrives wrapped in an extra
// `.default` layer under Vite's esbuild dependency pre-bundling (a known
// CJS/ESM interop edge case) — unwrap defensively, however many layers deep,
// instead of assuming a fixed shape.
import * as LottieModule from "lottie-react";

function unwrap(mod) {
  let candidate = mod;
  for (let i = 0; i < 4; i++) {
    if (typeof candidate === "function") return candidate;
    if (candidate && typeof candidate === "object" && "default" in candidate) {
      candidate = candidate.default;
      continue;
    }
    break;
  }
  return candidate;
}

export const Lottie = unwrap(LottieModule);
