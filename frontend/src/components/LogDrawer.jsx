import { useEffect, useRef } from "react";
import { X, Terminal, AlertTriangle, CheckCircle2, CircleOff } from "lucide-react";
import ScanLoader from "./ScanLoader";

// Mirrors backend/services/pipeline_log.py's STATUS_MESSAGES — kept as a
// small, explicit map (not a passthrough of the raw status string) so the
// unconditional "Run finished" this replaces can't silently come back if a
// new status value is ever added without updating what it says here too.
const OUTCOME_TEXT = {
  completed: "Run finished",
  completed_zero_results: "Run finished — no new people found",
  completed_zero_results_searxng_unavailable: "Discovery failed: SearXNG is unavailable",
  failed: "Discovery run failed",
  incomplete: "Run ended unexpectedly",
};

function outcomeTone(status) {
  if (status === "completed") return "success";
  if (status === "completed_zero_results") return "neutral";
  return "danger"; // completed_zero_results_searxng_unavailable, failed, incomplete
}

function OutcomeIcon({ tone }) {
  if (tone === "success") return <CheckCircle2 size={18} className="text-success" />;
  if (tone === "neutral") return <CircleOff size={18} className="text-faint" />;
  return <AlertTriangle size={18} className="text-danger" />;
}

export default function LogDrawer({ open, onClose, running, lines, outcome }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [lines]);

  if (!open) return null;

  // Only ever the status this run's own captured output actually produced —
  // see backend/services/pipeline_log.py. No "Run finished" fallback: an
  // outcome that hasn't arrived yet is shown as "finishing up", not silently
  // reported as success.
  const status = outcome?.status;
  const tone = !running && status ? outcomeTone(status) : null;
  const title = running
    ? "Discovery run in progress"
    : status
      ? OUTCOME_TEXT[status] || status
      : "Finishing up…";

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={running ? undefined : onClose} />
      <div className="relative w-full max-w-xl h-full bg-surface border-l border-border flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-5 h-16 border-b border-border shrink-0">
          <div className="flex items-center gap-2.5">
            {running ? <ScanLoader size={22} /> : tone ? <OutcomeIcon tone={tone} /> : <Terminal size={18} className="text-dim" />}
            <div>
              <div className="font-display font-semibold text-[14px] text-ink">
                {title}
              </div>
              <div className="text-[11.5px] text-faint">
                {!running && status === "completed" && outcome.new_people != null
                  ? `${outcome.new_people} new ${outcome.new_people === 1 ? "person" : "people"} added`
                  : "python run.py"}
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={running}
            className="p-1.5 rounded-md text-faint hover:text-ink hover:bg-surface-2 disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Close log panel"
          >
            <X size={18} />
          </button>
        </div>

        {!running && status === "completed_zero_results_searxng_unavailable" && (
          <div className="mx-5 mt-4 flex items-start gap-2.5 rounded-md border border-danger/30 bg-danger-soft px-3.5 py-3 text-[12.5px] text-danger">
            <AlertTriangle size={15} className="shrink-0 mt-[1px]" />
            <span>
              The discovery search backend (SearXNG) couldn't be reached, so this run found
              nothing. Other sources may still have contributed. Check the search backend
              configuration and try again.
            </span>
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-5 py-4 font-mono text-[12px] leading-relaxed text-dim bg-surface-2/40">
          {lines.length === 0 && (
            <p className="text-faint italic">Waiting for output…</p>
          )}
          {lines.map((line, i) => (
            <div key={i} className="whitespace-pre-wrap break-all">
              {line}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
        {!running && (
          <div className="px-5 py-3 border-t border-border shrink-0 text-[12px] text-faint">
            Dashboard data refreshes automatically.
          </div>
        )}
      </div>
    </div>
  );
}
