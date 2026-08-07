import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import DnaNetworkScene from "./DnaNetworkScene";
import HelixMark from "../HelixMark";

const TARGET_COMPANIES = ["Isomorphic Labs", "Arc Institute", "FutureHouse", "Owkin", "Recursion", "Generate Biomedicines"];

const PEOPLE_CARDS = [
  { name: "Anton Osokin", role: "Principal Research Scientist", priority: "high" },
  { name: "Piotr Mirowski", role: "Senior Staff Research Scientist", priority: "high" },
  { name: "Miguel García-Ortegón", role: "ML Research Scientist", priority: "medium" },
  { name: "Tan Nguyen", role: "Staff ML Scientist", priority: "low" },
];

// Beat timeline, in ms. Each beat's `duration` is how long it's shown before
// advancing automatically.
const BEATS = [
  { id: "biology", label: "Biology", duration: 2200 },
  { id: "dna", label: "DNA · Cells · Proteins", duration: 3000 },
  { id: "network", label: "Artificial Intelligence", duration: 3200 },
  { id: "companies", label: "Scanning AI × Biology Companies", duration: 2400 },
  { id: "people", label: "Discovering Researchers & Engineers", duration: 2400 },
  { id: "recommend", label: "Ranking Who to Follow", duration: 2200 },
  { id: "reveal", label: "", duration: 1200 },
];

export default function CinematicIntro({ onComplete }) {
  const [beatIndex, setBeatIndex] = useState(0);
  const phaseRef = useRef(0);
  const rafRef = useRef();

  const beat = BEATS[beatIndex];

  // Advance through the timeline.
  useEffect(() => {
    if (beatIndex >= BEATS.length - 1) {
      const t = setTimeout(onComplete, beat.duration);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setBeatIndex((i) => i + 1), beat.duration);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [beatIndex]);

  // Drive the 3D network-transition intensity smoothly across the
  // "network" beat (index 2) without re-rendering React every frame.
  useEffect(() => {
    const start = performance.now();
    const target = beatIndex >= 2 ? 1 : 0;
    const startValue = phaseRef.current;

    function tick(now) {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / 1800);
      phaseRef.current = startValue + (target - startValue) * easeOutCubic(t);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [beatIndex]);

  const showScene = beatIndex <= 5;
  const sceneOpacity = beatIndex === 0 ? 0.5 : beatIndex >= 6 ? 0 : 1;

  return (
    <motion.div
      className="fixed inset-0 z-[100] bg-[#05070a] overflow-hidden"
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5 }}
    >
      <button
        onClick={onComplete}
        className="absolute top-5 right-5 z-20 inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-[12px] text-white/70 hover:text-white hover:bg-white/10 backdrop-blur transition-colors"
      >
        Skip <X size={13} />
      </button>

      {showScene && (
        <motion.div
          className="absolute inset-0"
          animate={{ opacity: sceneOpacity }}
          transition={{ duration: 0.8 }}
        >
          <DnaNetworkScene phase={phaseRef} className="w-full h-full" />
        </motion.div>
      )}

      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none px-6">
        <AnimatePresence mode="wait">
          {beat.id === "biology" && (
            <motion.div key="biology" {...fadeProps} className="flex flex-col items-center gap-3">
              <div className="flex gap-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <motion.span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-accent"
                    animate={{ opacity: [0.2, 1, 0.2] }}
                    transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.15 }}
                  />
                ))}
              </div>
              <BeatLabel>Biology</BeatLabel>
            </motion.div>
          )}

          {beat.id === "dna" && (
            <motion.div key="dna" {...fadeProps}>
              <BeatLabel>{beat.label}</BeatLabel>
            </motion.div>
          )}

          {beat.id === "network" && (
            <motion.div key="network" {...fadeProps}>
              <BeatLabel>{beat.label}</BeatLabel>
            </motion.div>
          )}

          {beat.id === "companies" && (
            <motion.div key="companies" {...fadeProps} className="flex flex-col items-center gap-6 pointer-events-none">
              <BeatLabel small>{beat.label}</BeatLabel>
              <div className="flex flex-wrap justify-center gap-3 max-w-lg">
                {TARGET_COMPANIES.map((c, i) => (
                  <motion.span
                    key={c}
                    initial={{ opacity: 0, y: 8, scale: 0.9 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ delay: i * 0.12, duration: 0.4 }}
                    className="rounded-full border border-accent/30 bg-accent/10 px-3.5 py-1.5 text-[12.5px] text-accent font-medium"
                  >
                    {c}
                  </motion.span>
                ))}
              </div>
            </motion.div>
          )}

          {beat.id === "people" && (
            <motion.div key="people" {...fadeProps} className="flex flex-col items-center gap-6">
              <BeatLabel small>{beat.label}</BeatLabel>
              <div className="flex flex-wrap justify-center gap-3 max-w-md">
                {PEOPLE_CARDS.map((p, i) => (
                  <motion.div
                    key={p.name}
                    initial={{ opacity: 0, y: 14 }}
                    animate={{
                      opacity: p.priority === "low" ? 0.35 : 1,
                      y: 0,
                      scale: p.priority === "high" ? 1.04 : 1,
                    }}
                    transition={{ delay: i * 0.15, duration: 0.45 }}
                    className={`rounded-lg border px-3.5 py-2.5 text-left w-40 ${
                      p.priority === "high" ? "border-accent/50 bg-accent/10 shadow-[0_0_24px_-4px_rgba(34,211,182,0.4)]" : "border-white/10 bg-white/5"
                    }`}
                  >
                    <div className="text-[12px] font-medium text-white">{p.name}</div>
                    <div className="text-[10.5px] text-white/50 truncate">{p.role}</div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}

          {beat.id === "recommend" && (
            <motion.div key="recommend" {...fadeProps} className="flex flex-col items-center gap-3">
              <motion.div
                animate={{ scale: [1, 1.06, 1] }}
                transition={{ duration: 1.4, repeat: Infinity }}
                className="text-accent text-[22px] tracking-wide"
              >
                ★★★★★
              </motion.div>
              <BeatLabel small>Recommended Today</BeatLabel>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {beatIndex === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 1, duration: 0.8 }}
          className="absolute bottom-10 left-1/2 -translate-x-1/2 flex items-center gap-2"
        >
          <HelixMark size={22} />
          <span className="font-display font-bold text-[14px] text-white/80 tracking-tight">Helix</span>
        </motion.div>
      )}
    </motion.div>
  );
}

const fadeProps = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -10 },
  transition: { duration: 0.5 },
};

function BeatLabel({ children, small }) {
  return (
    <h1 className={`font-display font-semibold text-white text-center ${small ? "text-[18px]" : "text-[28px] md:text-[34px]"}`}>
      {children}
    </h1>
  );
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}
