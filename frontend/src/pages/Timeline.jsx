import { useEffect, useState } from "react";
import { ExternalLink, Clock } from "lucide-react";
import { api } from "../api/client";
import { useRun } from "../hooks/RunContext";
import PageShell from "../components/PageShell";
import SourceBadge from "../components/SourceBadge";
import FollowButton from "../components/FollowButton";
import EmptyState from "../components/ui/EmptyState";
import { SkeletonText } from "../components/ui/Skeleton";
import Reveal from "../components/ui/Reveal";

export default function Timeline() {
  const [buckets, setBuckets] = useState(null);
  const [error, setError] = useState("");
  const { refreshKey } = useRun();

  useEffect(() => {
    let cancelled = false;
    api
      .timeline()
      .then((d) => !cancelled && setBuckets(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <PageShell title="Activity Timeline" subtitle="Every discovery, grouped by when it happened">
      {error && (
        <div className="mb-4 rounded-md border border-danger/30 bg-danger-soft text-danger text-[13px] px-4 py-3">
          {error}
        </div>
      )}

      {!buckets ? (
        <SkeletonText lines={8} />
      ) : buckets.length === 0 ? (
        <EmptyState icon={Clock} title="No activity yet" description="Run the pipeline to start building a timeline." />
      ) : (
        <div className="flex flex-col gap-8">
          {buckets.map((bucket) => (
            <section key={bucket.bucket}>
              <div className="flex items-center gap-2.5 mb-3 sticky top-16 bg-bg/95 backdrop-blur py-1.5 z-10">
                <h2 className="font-display font-bold text-[15px] text-ink">{bucket.bucket}</h2>
                <span className="text-[11.5px] font-mono text-faint">{bucket.count}</span>
              </div>
              <div className="relative pl-5 border-l border-border flex flex-col gap-3">
                {bucket.events.map((e, i) => (
                  <Reveal
                    key={e.id}
                  y={6} duration={0.25} delay={Math.min(i * 0.015, 0.3)}
                    className="relative"
                >
                    <span className="absolute -left-[26px] top-1.5 w-2 h-2 rounded-full bg-accent ring-4 ring-bg" />
                    <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface px-4 py-2.5 hover:border-accent/40 transition-colors">
                      <div className="min-w-0">
                        <span className="text-[13px] font-medium text-ink">{e.name}</span>
                        <span className="text-[12.5px] text-dim"> joined the list from </span>
                        <span className="text-[12.5px] text-ink font-medium">{e.company}</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <SourceBadge source={e.source} />
                        <FollowButton personId={e.id} size={14} />
                        <a href={e.linkedin_url} target="_blank" rel="noreferrer" className="text-faint hover:text-accent">
                          <ExternalLink size={13} />
                        </a>
                      </div>
                    </div>
                  </Reveal>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </PageShell>
  );
}
