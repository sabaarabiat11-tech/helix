import Reveal from "./ui/Reveal";
import { cn } from "../lib/cn";

/** Signature hero banner — glass panel + ambient ammated glow, optionally
 * with the DNA/network 3D scene as a background motif. Used on flagship
 * pages (Dashboard, AI Insights); other pages stay lighter-weight but still
 * inherit the same tokens/glass treatment via Card. */
export default function PageHero({ eyebrow, title, subtitle, icon: Icon, scene, right, className }) {
  return (
    <Reveal
      y={-8}
      duration={0.4}
      className={cn("relative overflow-hidden rounded-lg glass-panel mb-6", className)}
    >
      <div className="helix-ambient-bg" />
      {scene && (
        <div className="absolute inset-0 opacity-[0.35] mix-blend-screen">
          {scene}
        </div>
      )}
      <div className="relative px-6 py-8 md:px-9 md:py-10 flex items-start justify-between gap-6 flex-wrap">
        <div>
          {eyebrow && (
            <div className="flex items-center gap-2 mb-3">
              {Icon && (
                <span className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-accent-soft text-accent">
                  <Icon size={14} />
                </span>
              )}
              <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-accent">{eyebrow}</span>
            </div>
          )}
          <h1 className="font-display font-bold text-[26px] md:text-[32px] text-ink tracking-tight text-wrap-balance">
            {title}
          </h1>
          {subtitle && <p className="text-[13.5px] text-dim mt-2.5 max-w-xl">{subtitle}</p>}
        </div>
        {right}
      </div>
    </Reveal>
  );
}
