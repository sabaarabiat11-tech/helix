import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { useRunPipeline } from "./useRunPipeline";

const RunContext = createContext(null);

/** How often to check whether the corpus changed underneath us. The pipeline
 * runs on a schedule measured in hours, so a minute is already far finer
 * granularity than the data actually changes at. */
const POLL_INTERVAL_MS = 60_000;

export function RunProvider({ children }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const bumpRefresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  const { running, logLines, error, start } = useRunPipeline(bumpRefresh);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const startRun = useCallback(() => {
    setDrawerOpen(true);
    start();
  }, [start]);

  /**
   * Keep the dashboard current without a manual reload.
   *
   * Two things keep this from being wasteful. It only polls while the tab is
   * actually visible — a backgrounded dashboard shouldn't generate traffic
   * forever — and it only bumps `refreshKey` when the data genuinely changed,
   * so an unchanged corpus costs one small request and re-renders nothing.
   *
   * A run already in progress is skipped: the WebSocket stream drives the
   * refresh at completion, and polling on top would just duplicate it.
   */
  const signatureRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    async function check() {
      if (cancelled || running || document.visibilityState !== "visible") return;
      try {
        const stats = await api.stats();
        const signature = `${stats.total_people}:${stats.last_run_time ?? ""}`;
        if (signatureRef.current === null) {
          signatureRef.current = signature;
        } else if (signatureRef.current !== signature) {
          signatureRef.current = signature;
          bumpRefresh();
        }
      } catch {
        // A failed poll is not worth surfacing — the next one will retry, and
        // whichever page the user is on shows its own error if it matters.
      }
    }

    const timer = setInterval(check, POLL_INTERVAL_MS);
    // Coming back to the tab is exactly when stale data is most likely and
    // most visible, so check immediately rather than waiting out the interval.
    const onVisible = () => {
      if (document.visibilityState === "visible") check();
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      cancelled = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [running, bumpRefresh]);

  return (
    <RunContext.Provider
      value={{ running, logLines, error, startRun, drawerOpen, setDrawerOpen, refreshKey }}
    >
      {children}
    </RunContext.Provider>
  );
}

export function useRun() {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun must be used within RunProvider");
  return ctx;
}
