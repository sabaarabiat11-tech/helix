import { createContext, useCallback, useContext, useState } from "react";
import { useRunPipeline } from "./useRunPipeline";

const RunContext = createContext(null);

export function RunProvider({ children }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const bumpRefresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  const { running, logLines, error, start } = useRunPipeline(bumpRefresh);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const startRun = useCallback(() => {
    setDrawerOpen(true);
    start();
  }, [start]);

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
