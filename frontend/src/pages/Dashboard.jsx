import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Users, Sparkles, CalendarDays, Clock, Activity, Container, ArrowRight, Star, Dna } from "lucide-react";
import { api } from "../api/client";
import { useRun } from "../hooks/RunContext";
import PageShell from "../components/PageShell";
import PageHero from "../components/PageHero";
import StatCard from "../components/StatCard";
import FollowButton from "../components/FollowButton";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import Stars from "../components/ui/Stars";
import { SkeletonCard } from "../components/ui/Skeleton";
import { formatRelativeTime } from "../lib/format";
import LazyDnaScene from "../components/cinematic/LazyDnaScene";
import Reveal from "../components/ui/Reveal";

const PIPELINE_TONE = {
  running: "accent",
  completed: "success",
  completed_zero_results: "warning",
  completed_zero_results_searxng_unavailable: "danger",
  failed: "danger",
  incomplete: "warning",
  never_run: "neutral",
};

const PIPELINE_LABEL = {
  running: "Running",
  completed: "Completed",
  completed_zero_results: "Finished — no new people",
  completed_zero_results_searxng_unavailable: "Failed — SearXNG unavailable",
  failed: "Failed",
  incomplete: "Incomplete",
  never_run: "Never run",
};

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recommended, setRecommended] = useState(null);
  const [error, setError] = useState("");
  const { refreshKey, running } = useRun();

  useEffect(() => {
    let cancelled = false;
    api.stats().then((d) => !cancelled && setStats(d)).catch((e) => !cancelled && setError(e.message));
    api.recommendations(3).then((d) => !cancelled && setRecommended(d.recommended_today)).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [refreshKey, running]);

  return (
    <PageShell title="Dashboard" subtitle="Overview of the AI × Biology discovery database" hasHero>
      <PageHero
        eyebrow="Biotech Intelligence"
        title="Living map of AI × Biology"
        subtitle="Helix continuously scans research labs, biotech companies, and professional networks to surface the people and breakthroughs that matter."
        icon={Dna}
        scene={<LazyDnaScene className="w-full h-full" />}
      />

      {error && (
        <div className="mb-4 rounded-md border border-danger/30 bg-danger-soft text-danger text-[13px] px-4 py-3">
          Could not load stats: {error}
        </div>
      )}

      {!stats ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard label="Total People" value={stats.total_people} sub="in the database" icon={Users} tone="accent" />
            <StatCard label="New Today" value={stats.new_today} sub="discovered today" icon={Sparkles} delay={0.05} />
            <StatCard label="New This Week" value={stats.new_this_week} sub="last 7 days" icon={CalendarDays} delay={0.1} />
            <StatCard
              label="Last Run"
              value={formatRelativeTime(stats.last_run_time)}
              sub={stats.last_run_new_people !== null ? `+${stats.last_run_new_people} new people` : "—"}
              icon={Clock}
              delay={0.15}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
            <Reveal y={10} duration={0.35} delay={0.15}>
              <Card className="p-5 flex items-center justify-between h-full">
                <div className="flex items-center gap-3">
                  <span className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-surface-2 text-faint">
                    <Activity size={17} />
                  </span>
                  <div>
                    <div className="text-[13px] font-semibold text-ink">Pipeline Status</div>
                    <div className="text-[12px] text-faint">Current discovery run state</div>
                  </div>
                </div>
                <Badge tone={PIPELINE_TONE[stats.pipeline_status] || "neutral"}>
                  {PIPELINE_LABEL[stats.pipeline_status] || stats.pipeline_status}
                </Badge>
              </Card>
            </Reveal>

            <Reveal y={10} duration={0.35} delay={0.2}>
              <Card className="p-5 h-full">
                <div className="flex items-center gap-3 mb-3">
                  <span className="inline-flex items-center justify-center w-9 h-9 rounded-md bg-surface-2 text-faint">
                    <Container size={17} />
                  </span>
                  <div>
                    <div className="text-[13px] font-semibold text-ink">Discovery search backend</div>
                    <div className="text-[12px] text-faint">
                      {stats.searxng.base_url || "SearXNG"}
                    </div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {/* The Docker container check only means anything where Docker
                      is actually expected (local dev). A hosted deployment has
                      no Docker daemon of its own by design — showing "not
                      found" there every time reads as a fault when it isn't
                      one, so it's shown only where the docker CLI exists at all. */}
                  {stats.docker.docker_cli_available && (
                    <Badge tone={stats.docker.container_found && stats.docker.container_status === "running" ? "success" : "warning"}>
                      Container: {stats.docker.container_found ? (stats.docker.container_status || "unknown") : "not found"}
                    </Badge>
                  )}
                  <Badge
                    tone={
                      !stats.searxng.configured ? "warning"
                      : stats.searxng.json_api_working ? "success"
                      : "danger"
                    }
                  >
                    SearXNG:{" "}
                    {!stats.searxng.configured
                      ? "not configured"
                      : stats.searxng.json_api_working
                        ? "working"
                        : "unreachable"}
                  </Badge>
                </div>
              </Card>
            </Reveal>
          </div>

          <Reveal y={10} duration={0.35} delay={0.25} className="mt-4">
            <Card className="p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2.5">
                  <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-accent-soft text-accent">
                    <Star size={15} />
                  </span>
                  <h2 className="font-display font-semibold text-[14px] text-ink">Recommended Today</h2>
                </div>
                <Link to="/recommendations" className="inline-flex items-center gap-1 text-[12.5px] text-accent hover:text-accent-strong font-medium">
                  View all <ArrowRight size={13} />
                </Link>
              </div>

              {!recommended ? (
                <p className="text-[12.5px] text-faint">Loading recommendations…</p>
              ) : recommended.length === 0 ? (
                <p className="text-[12.5px] text-faint">No recommendations yet.</p>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {recommended.map((p) => (
                    <div key={p.id} className="rounded-md border border-border p-3.5 flex flex-col gap-2">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-[13px] font-medium text-ink truncate">{p.name}</div>
                          <div className="text-[11.5px] text-faint truncate">{p.company}</div>
                        </div>
                        <FollowButton personId={p.id} size={14} />
                      </div>
                      <div className="flex items-center gap-2">
                        <Stars count={p.stars} size={11} />
                        <span className="font-mono text-[11.5px] text-accent">{p.score}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </Reveal>
        </>
      )}
    </PageShell>
  );
}
