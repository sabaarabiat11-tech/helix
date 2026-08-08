import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { AnimatePresence } from "framer-motion";
import Sidebar from "./Sidebar";
import LogDrawer from "./LogDrawer";
import CommandPalette from "./CommandPalette";
import CinematicIntro from "./cinematic/CinematicIntro";
import { useRun } from "../hooks/RunContext";

const INTRO_SEEN_KEY = "helix-intro-seen";

function shouldPlayIntro() {
  if (typeof window === "undefined") return false;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
  return !sessionStorage.getItem(INTRO_SEEN_KEY);
}

export default function Layout() {
  const [navOpen, setNavOpen] = useState(false);
  const { running, logLines, outcome, drawerOpen, setDrawerOpen } = useRun();
  const [showIntro, setShowIntro] = useState(shouldPlayIntro);

  useEffect(() => {
    if (!showIntro) sessionStorage.setItem(INTRO_SEEN_KEY, "1");
  }, [showIntro]);

  return (
    <div className="min-h-screen bg-bg text-ink">
      <AnimatePresence>
        {showIntro && <CinematicIntro key="intro" onComplete={() => setShowIntro(false)} />}
      </AnimatePresence>

      <Sidebar open={navOpen} onNavigate={() => setNavOpen(false)} />

      {navOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setNavOpen(false)}
        />
      )}

      <div className="lg:pl-64">
        <Outlet context={{ onMenuClick: () => setNavOpen(true) }} />
      </div>

      <LogDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        running={running}
        lines={logLines}
        outcome={outcome}
      />

      <CommandPalette />
    </div>
  );
}
