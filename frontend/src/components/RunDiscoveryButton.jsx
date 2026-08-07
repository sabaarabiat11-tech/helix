import { Play } from "lucide-react";
import ScanLoader from "./ScanLoader";
import { useRun } from "../hooks/RunContext";

export default function RunDiscoveryButton() {
  const { running, startRun, setDrawerOpen } = useRun();

  return (
    <button
      onClick={() => (running ? setDrawerOpen(true) : startRun())}
      className={`
        inline-flex items-center gap-2 rounded-md px-3.5 py-2 text-[13px] font-semibold
        transition-colors
        ${
          running
            ? "bg-surface-3 text-ink"
            : "bg-accent text-[#04121f] hover:bg-accent-strong"
        }
      `}
    >
      {running ? <ScanLoader size={16} /> : <Play size={14} strokeWidth={2.5} />}
      {running ? "Running…" : "Run Discovery"}
    </button>
  );
}
