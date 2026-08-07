import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText, ArrowLeft } from "lucide-react";
import { api } from "../api/client";
import { useRun } from "../hooks/RunContext";
import PageShell from "../components/PageShell";
import ScanLoader from "../components/ScanLoader";
import { formatDateTime } from "../lib/format";

export default function Reports() {
  const [reports, setReports] = useState(null);
  const [selected, setSelected] = useState(null);
  const [content, setContent] = useState(null);
  const [error, setError] = useState("");
  const { refreshKey } = useRun();

  useEffect(() => {
    api.reports().then(setReports).catch((e) => setError(e.message));
  }, [refreshKey]);

  useEffect(() => {
    if (!selected) return;
    setContent(null);
    api.report(selected).then((r) => setContent(r.content)).catch((e) => setError(e.message));
  }, [selected]);

  if (selected) {
    return (
      <PageShell
        title={selected}
        subtitle="Weekly discovery report"
        right={
          <button
            onClick={() => setSelected(null)}
            className="inline-flex items-center gap-1.5 text-[13px] text-dim hover:text-ink"
          >
            <ArrowLeft size={14} /> All reports
          </button>
        }
      >
        <div className="rounded-lg border border-border bg-surface p-6 md:p-8">
          {!content ? (
            <div className="flex items-center gap-2 justify-center text-dim py-12">
              <ScanLoader size={20} /> Loading report…
            </div>
          ) : (
            <article className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </article>
          )}
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell title="Reports" subtitle="Every weekly_report_*.md the pipeline has written">
      {error && (
        <div className="mb-4 rounded-md border border-danger/30 bg-danger-soft text-danger text-[13px] px-4 py-3">
          {error}
        </div>
      )}

      {error ? null : !reports ? (
        <div className="flex items-center gap-2 justify-center text-dim py-12">
          <ScanLoader size={20} /> Loading…
        </div>
      ) : reports.length === 0 ? (
        <div className="rounded-lg border border-border bg-surface p-10 text-center text-faint text-[13.5px]">
          No reports yet — run the pipeline to generate one.
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {reports.map((r) => (
            <button
              key={r.filename}
              onClick={() => setSelected(r.filename)}
              className="text-left rounded-lg border border-border bg-surface p-4 hover:border-accent/50 hover:bg-surface-2/40 transition-colors"
            >
              <div className="flex items-center gap-2.5 mb-2">
                <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-accent-soft text-accent shrink-0">
                  <FileText size={15} />
                </span>
                <div className="min-w-0">
                  <div className="text-[13px] font-semibold text-ink truncate">{r.filename}</div>
                  <div className="text-[11.5px] text-faint">{(r.size_bytes / 1024).toFixed(1)} KB</div>
                </div>
              </div>
              <div className="text-[11.5px] text-faint font-mono">{formatDateTime(new Date(r.modified * 1000).toISOString())}</div>
            </button>
          ))}
        </div>
      )}
    </PageShell>
  );
}
