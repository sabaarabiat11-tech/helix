import { useEffect, useRef } from "react";
import { X, Terminal } from "lucide-react";
import ScanLoader from "./ScanLoader";

export default function LogDrawer({ open, onClose, running, lines }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [lines]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={running ? undefined : onClose} />
      <div className="relative w-full max-w-xl h-full bg-surface border-l border-border flex flex-col shadow-2xl">
        <div className="flex items-center justify-between px-5 h-16 border-b border-border shrink-0">
          <div className="flex items-center gap-2.5">
            {running ? <ScanLoader size={22} /> : <Terminal size={18} className="text-dim" />}
            <div>
              <div className="font-display font-semibold text-[14px] text-ink">
                {running ? "Discovery run in progress" : "Run finished"}
              </div>
              <div className="text-[11.5px] text-faint">python start.py</div>
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
