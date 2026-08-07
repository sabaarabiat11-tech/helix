import { Suspense, lazy } from "react";

/**
 * three.js + React Three Fiber are by far the heaviest dependency in the app
 * (~600KB before compression). The DNA scene is purely decorative — every page
 * that uses it is fully readable and usable without it — so it loads in its
 * own async chunk rather than blocking first paint.
 *
 * The fallback is `null` on purpose: this sits behind a low-opacity blend
 * layer, so an empty slot reads as "no ornament yet", while a spinner would
 * draw attention to decoration that hasn't arrived.
 */
const AmbientDnaScene = lazy(() => import("./AmbientDnaScene"));

export default function LazyDnaScene(props) {
  return (
    <Suspense fallback={null}>
      <AmbientDnaScene {...props} />
    </Suspense>
  );
}
