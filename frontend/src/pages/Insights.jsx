import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Sparkles, TrendingUp, Building2, FlaskConical, UserPlus, ArrowUpRight, ArrowDownRight, Minus, BrainCircuit } from "lucide-react";
import { api } from "../api/client";
import { useRun } from "../hooks/RunContext";
import PageShell from "../components/PageShell";
import PageHero from "../components/PageHero";
import Card from "../components/ui/Card";
import Badge from "../components/ui/Badge";
import { SkeletonCard } from "../components/ui/Skeleton";
import { formatDateTime } from "../lib/format";
import LazyDnaScene from "../components/cinematic/LazyDnaScene";

const ICON_BY_CARD = {
  "best-today": Sparkles,
  "fastest-growing": TrendingUp,
  "increasing-hiring": Building2,
  "interesting-researchers": FlaskConical,
  "contact-first": UserPlus,
  "week-trend": TrendingUp,
};

function CardBody({ card }) {
  if (card.id === "week-trend") {
    const pct = card.items[0]?.value ?? 0;
    const Icon = pct > 0 ? ArrowUpRight : pct < 0 ? ArrowDownRight : Minus;
    const tone = pct > 0 ? "success" : pct < 0 ? "danger" : "neutral";
    return (
      <div className="flex items-center gap-2 mt-2">
        <Badge tone={tone} dot={false} className="text-[13px] px-3 py-1.5">
          <Icon size={14} /> {pct > 0 ? "+" : ""}{pct}%
        </Badge>
        <span className="text-[12px] text-faint">week-over-week</span>
      </div>
    );
  }

  if (card.items.length === 0) {
    return <p className="text-[12.5px] text-faint mt-2">Nothing to show yet.</p>;
  }

  if (card.id === "fastest-growing" || card.id === "increasing-hiring") {
    return (
      <ul className="mt-3 flex flex-col gap-2">
        {card.items.map((item, i) => (
          <li key={i} className="flex items-center justify-between text-[13px]">
            <span className="text-ink truncate pr-3">{item.company}</span>
            <span className="font-mono text-dim shrink-0">
              {item.delta !== undefined ? `+${item.delta} this week` : item.count}
            </span>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <ul className="mt-3 flex flex-col gap-2.5">
      {card.items.map((item, i) => (
        <li key={i} className="flex items-center justify-between gap-3 text-[13px]">
          <div className="min-w-0">
            <div className="text-ink font-medium truncate">{item.name}</div>
            <div className="text-faint text-[11.5px] truncate">{item.title} · {item.company}</div>
          </div>
          {item.score !== undefined && (
            <span className="font-mono text-accent text-[12.5px] shrink-0">{item.score}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function Insights() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const { refreshKey } = useRun();

  useEffect(() => {
    let cancelled = false;
    api
      .insights()
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <PageShell
      title="AI Insights"
      subtitle="Automatic daily summary — statistical analysis of your discovery data, not LLM-generated text"
      hasHero
    >
      <PageHero
        eyebrow="Intelligence Layer"
        title="Signals from the network"
        subtitle="Patterns surfaced from real discovery data — growth, momentum, and who's worth reaching out to first. Statistical today; architected so a future model can generate these instead of one rule engine."
        icon={BrainCircuit}
        scene={<LazyDnaScene className="w-full h-full" phase={0.8} />}
      />

      {error && (
        <div className="mb-4 rounded-md border border-danger/30 bg-danger-soft text-danger text-[13px] px-4 py-3">
          {error}
        </div>
      )}

      {!data ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : (
        <>
          <p className="text-[11.5px] text-faint font-mono mb-4">Generated {formatDateTime(data.generated_at)}</p>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {data.cards.map((card, i) => {
              const Icon = ICON_BY_CARD[card.id] || Sparkles;
              return (
                <motion.div
                  key={card.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: i * 0.05 }}
                >
                  <Card className="p-5 h-full">
                    <div className="flex items-center gap-2.5 mb-1">
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded-md bg-accent-soft text-accent">
                        <Icon size={16} />
                      </span>
                      <h3 className="font-display font-semibold text-[13.5px] text-ink">{card.category}</h3>
                    </div>
                    <p className="text-[12px] text-faint">{card.description}</p>
                    <CardBody card={card} />
                  </Card>
                </motion.div>
              );
            })}
          </div>
        </>
      )}
    </PageShell>
  );
}
