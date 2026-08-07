import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight, Building2, ExternalLink, Flame, SlidersHorizontal, Sparkles, TrendingUp, UserPlus,
} from "lucide-react";
import { api } from "../api/client";
import { useRun } from "../hooks/RunContext";
import PageShell from "../components/PageShell";
import PageHero from "../components/PageHero";
import FollowButton from "../components/FollowButton";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import Stars from "../components/ui/Stars";
import EmptyState from "../components/ui/EmptyState";
import { SkeletonCard } from "../components/ui/Skeleton";
import LazyDnaScene from "../components/cinematic/LazyDnaScene";
import { cn } from "../lib/cn";
import Reveal from "../components/ui/Reveal";

const TABS = [
  { id: "top_today", label: "Top today", icon: Sparkles, blurb: "The five strongest matches from the latest discoveries." },
  { id: "top_this_week", label: "This week", icon: TrendingUp, blurb: "The ten highest-ranked people across the past week." },
  { id: "to_follow", label: "To follow", icon: UserPlus, blurb: "Strong matches you haven't added to your watchlist yet." },
];

function PersonCard({ person, rank }) {
  // Personalized reasons are appended first by the ranking service, so the
  // leading badges are the ones that answer "why me?".
  const boosted = person.personal_adjustment > 0;

  return (
    <Card hover className="p-5 flex flex-col gap-3 h-full">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {rank != null && <span className="text-[11px] font-mono text-faint">#{rank}</span>}
            <h3 className="font-display font-semibold text-[14.5px] text-ink truncate">{person.name}</h3>
          </div>
          <p className="text-[12.5px] text-dim truncate mt-0.5">
            {person.title}{person.company ? ` · ${person.company}` : ""}
          </p>
        </div>
        <FollowButton personId={person.id} />
      </div>

      <div className="flex items-center gap-3 flex-wrap">
        <Stars count={person.stars} />
        <span className="font-mono text-[13px] font-semibold text-accent">{person.score}</span>
        <span className="text-[11px] text-faint">/ 100</span>
        {boosted && (
          <span
            className="inline-flex items-center gap-1 text-[11px] font-medium text-success"
            title={`Base score ${person.base_score}, boosted by your preferences`}
          >
            <Flame size={11} /> +{person.personal_adjustment} for you
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {person.why.slice(0, 4).map((reason, index) => (
          <Badge key={index} tone={index === 0 && boosted ? "success" : "neutral"} size="sm" dot={false}>
            {reason}
          </Badge>
        ))}
      </div>

      <a
        href={person.linkedin_url}
        target="_blank"
        rel="noreferrer"
        className="mt-auto inline-flex items-center gap-1 text-[12.5px] text-accent hover:text-accent-strong font-medium"
      >
        View LinkedIn <ExternalLink size={12} />
      </a>
    </Card>
  );
}

function CompanyList({ title, description, icon: Icon, items, unit }) {
  if (!items?.length) return null;
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2.5 mb-1">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-accent-soft text-accent">
          <Icon size={15} />
        </span>
        <h2 className="font-display font-semibold text-[14px] text-ink">{title}</h2>
      </div>
      <p className="text-[12px] text-faint mb-3.5">{description}</p>
      <ul className="flex flex-col gap-1.5">
        {items.map((company) => (
          <li key={company.name}>
            <Link
              to={`/companies/${encodeURIComponent(company.name)}`}
              className="flex items-center justify-between gap-3 rounded-md px-3 py-2 hover:bg-surface-2 transition-colors group"
            >
              <span className="text-[13px] text-ink truncate group-hover:text-accent transition-colors">
                {company.name}
              </span>
              <span className="font-mono text-[12px] text-dim shrink-0">
                {company.count} {unit}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function AppliedPreferences({ applied }) {
  const chips = [
    ...applied.focus_areas.map((v) => ({ label: v, kind: "Focus" })),
    ...applied.preferred_companies.map((v) => ({ label: v, kind: "Company" })),
    ...applied.preferred_locations.map((v) => ({ label: v, kind: "Location" })),
  ];
  if (applied.seniority_preference !== "any") {
    chips.push({ label: applied.seniority_preference, kind: "Seniority" });
  }
  if (applied.min_score > 0) {
    chips.push({ label: `Score ≥ ${applied.min_score}`, kind: "Filter" });
  }

  return (
    <Card className="p-4 mb-4">
      <div className="flex items-start gap-3 flex-wrap">
        <span className="inline-flex items-center gap-2 text-[12px] font-medium text-dim shrink-0">
          <SlidersHorizontal size={13} className="text-accent" />
          Ranked for you
        </span>

        {chips.length ? (
          <div className="flex flex-wrap gap-1.5 flex-1">
            {chips.map((chip) => (
              <Badge key={`${chip.kind}-${chip.label}`} tone="accent" size="sm" dot={false}>
                {chip.label}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-[12px] text-faint flex-1">
            You haven't set any preferences yet, so this is the general ranking.
          </p>
        )}

        <Link
          to="/settings"
          className="inline-flex items-center gap-1 text-[12px] text-accent hover:text-accent-strong font-medium shrink-0"
        >
          Tune <ArrowRight size={12} />
        </Link>
      </div>
    </Card>
  );
}

export default function Recommendations() {
  const [bundle, setBundle] = useState(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("top_today");
  const { refreshKey } = useRun();

  useEffect(() => {
    let cancelled = false;
    api
      .recommendationBundle()
      .then((data) => !cancelled && setBundle(data))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const activeTab = TABS.find((t) => t.id === tab);
  const people = bundle?.[tab] ?? [];

  return (
    <PageShell
      title="Recommendations"
      subtitle="Ranked for you — every score explains itself"
      hasHero
    >
      <PageHero
        eyebrow="Your Copilot"
        title="Who to reach out to next"
        subtitle="Helix scores the whole network against what you care about, then tells you exactly why each person surfaced."
        icon={Sparkles}
        scene={<LazyDnaScene className="w-full h-full" phase={0.55} />}
      />

      {error && (
        <div className="mb-4 rounded-md border border-danger/30 bg-danger-soft text-danger text-[13px] px-4 py-3">
          {error}
        </div>
      )}

      {error ? null : !bundle ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : (
        <>
          <AppliedPreferences applied={bundle.preferences_applied} />

          <div className="flex items-center gap-1.5 mb-4 flex-wrap" role="tablist">
            {TABS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                className={cn(
                  "inline-flex items-center gap-2 px-3.5 py-2 rounded-md text-[13px] font-medium border transition-colors",
                  tab === id
                    ? "border-accent bg-accent-soft text-accent"
                    : "border-border text-dim hover:text-ink hover:border-accent/30"
                )}
              >
                <Icon size={14} />
                {label}
                <span className="font-mono text-[11px] opacity-70">{bundle[id]?.length ?? 0}</span>
              </button>
            ))}
          </div>

          <p className="text-[12.5px] text-faint mb-4">
            {activeTab.blurb}
            {tab === "top_today" && bundle.top_today_is_fallback && (
              <span className="text-warning">
                {" "}Nothing was discovered today, so these are the strongest overall.
              </span>
            )}
          </p>

          {people.length === 0 ? (
            <EmptyState
              icon={Sparkles}
              title="Nothing here yet"
              description={
                bundle.preferences_applied.min_score > 0
                  ? `No one clears your minimum score of ${bundle.preferences_applied.min_score}. Lower it in Settings to see more.`
                  : "Run the discovery pipeline to populate recommendations."
              }
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {people.map((person, index) => (
                <Reveal
                  key={person.id}
                  y={10} duration={0.3} delay={Math.min(index, 8) * 0.04}
                >
                  <PersonCard person={person} rank={index + 1} />
                </Reveal>
              ))}
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">
            <CompanyList
              title="Trending companies"
              description="Most discoveries in the past week."
              icon={TrendingUp}
              items={bundle.trending_companies}
              unit="new"
            />
            <CompanyList
              title="Most active organizations"
              description="Largest presence in the network overall."
              icon={Building2}
              items={bundle.most_active_organizations}
              unit="people"
            />
          </div>
        </>
      )}
    </PageShell>
  );
}
