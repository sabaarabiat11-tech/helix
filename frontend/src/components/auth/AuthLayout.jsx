import { Link } from "react-router-dom";
import Reveal from "../ui/Reveal";
import { Dna } from "lucide-react";
import LazyDnaScene from "../cinematic/LazyDnaScene";
import { cn } from "../../lib/cn";

const PROOF_POINTS = [
  "Continuously scans labs, biotech companies and open-source projects",
  "Ranks every researcher 0–100, and shows its reasoning",
  "Digests the week into one email you'll actually read",
];

/**
 * Split layout for the signed-out surface: the form on the left, the product's
 * signature DNA/neural scene on the right. The scene is decorative and hidden
 * below `lg`, where the form should own the full width rather than compete
 * with an ornament.
 */
export default function AuthLayout({ title, subtitle, children, footer, wide = false }) {
  return (
    <div className="min-h-screen bg-bg flex">
      {/* Form side */}
      <div className="flex-1 flex flex-col px-6 py-10 sm:px-10 lg:px-16">
        <Link to="/login" className="inline-flex items-center gap-2.5 self-start group">
          <span className="relative inline-flex items-center justify-center w-8 h-8 rounded-[9px] bg-surface-2 border border-border">
            <span className="absolute inset-0 rounded-[9px] bg-accent/25 blur-md" aria-hidden="true" />
            <Dna size={16} className="relative text-accent" />
          </span>
          <span className="font-display font-bold text-[15px] tracking-[0.16em] text-ink">HELIX</span>
        </Link>

        <div className="flex-1 flex items-center">
          <Reveal
            y={12}
            duration={0.35}
            className={cn("w-full mx-auto", wide ? "max-w-lg" : "max-w-[380px]")}
          >
            <h1 className="font-display font-bold text-[27px] leading-tight text-ink tracking-tight text-wrap-balance">
              {title}
            </h1>
            {subtitle && <p className="text-[13.5px] text-dim mt-2.5 leading-relaxed">{subtitle}</p>}
            <div className="mt-7">{children}</div>
          </Reveal>
        </div>

        {footer && (
          <div className="text-[12.5px] text-faint text-center lg:text-left">{footer}</div>
        )}
      </div>

      {/* Brand side */}
      <div className="hidden lg:flex w-[46%] max-w-[620px] relative overflow-hidden border-l border-border">
        <div className="helix-ambient-bg" aria-hidden="true" />
        <div className="absolute inset-0 opacity-40" aria-hidden="true">
          <LazyDnaScene className="w-full h-full" phase={0.6} />
        </div>

        <div className="relative flex flex-col justify-end p-14 w-full">
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent mb-3.5">
            Biotech Intelligence
          </div>
          <p className="font-display font-bold text-[26px] leading-[1.25] text-ink tracking-tight text-wrap-balance max-w-sm">
            The people building AI&nbsp;×&nbsp;Biology, found before everyone else finds them.
          </p>

          <ul className="mt-8 flex flex-col gap-3">
            {PROOF_POINTS.map((point) => (
              <li key={point} className="flex items-start gap-2.5 text-[13px] text-dim leading-relaxed">
                <span
                  className="mt-[7px] w-1.5 h-1.5 rounded-full bg-accent shrink-0"
                  aria-hidden="true"
                />
                {point}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
