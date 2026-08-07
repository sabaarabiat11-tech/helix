import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useInView } from "framer-motion";
import {
  ArrowRight, Bell, Building2, Check, ChevronDown, Dna, ExternalLink,
  Code2, Filter, Mail, Menu, Search, Sparkles, Star, X,
} from "lucide-react";
import { cn } from "../lib/cn";

/**
 * Public landing page.
 *
 * The thesis: Helix's distinctive artifact is not "AI" in the abstract, it's a
 * *scored recommendation that shows its reasoning*. So the hero isn't a
 * gradient and a slogan — it's the actual thing the product outputs, with the
 * reasons assembling themselves one by one. Everything else on the page stays
 * quiet so that one component carries the weight.
 *
 * The score badge recurs as the page's structural through-line: hero, the
 * scoring step, and the plan cards. Numbers and dates are set in the mono face
 * throughout, so the page reads as an instrument rather than a brochure.
 */

// ---------------------------------------------------------------------------

const SAMPLE = {
  name: "Dr. Amara Osei",
  title: "Principal Research Scientist",
  company: "Isomorphic Labs",
  score: 94,
  reasons: [
    "Isomorphic Labs is a top-tier AI×Biology lab",
    "Matches your focus on protein structure prediction",
    "Senior/leadership-level role",
    "Discovered today",
  ],
};

/** The signature element: a score that explains itself, line by line. */
function ScoredCard() {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const [score, setScore] = useState(0);

  useEffect(() => {
    if (!inView) return;
    // Count up to the score. Uses state rather than a MotionValue because
    // motion values don't reactively re-render text children.
    const duration = 900;
    const start = performance.now();
    let frame;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      // easeOutCubic — decelerates into the final number
      setScore(Math.round(SAMPLE.score * (1 - Math.pow(1 - t, 3))));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [inView]);

  return (
    <div ref={ref} className="relative">
      <div
        aria-hidden="true"
        className="absolute -inset-6 rounded-3xl bg-[radial-gradient(60%_50%_at_50%_0%,rgba(0,212,255,0.16),transparent_70%)] blur-xl"
      />
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="relative rounded-2xl border border-border bg-surface/90 backdrop-blur-xl p-5 sm:p-6 shadow-[0_24px_60px_-24px_rgba(0,0,0,0.7)]"
      >
        <div className="flex items-center justify-between gap-3 mb-5">
          <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-accent">
            <Sparkles size={12} /> Today's top match
          </span>
          <span className="font-mono text-[11px] text-faint">helix.daily</span>
        </div>

        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h3 className="font-display font-semibold text-[17px] sm:text-[19px] text-ink truncate">
              {SAMPLE.name}
            </h3>
            <p className="text-[13px] text-dim mt-1 truncate">
              {SAMPLE.title} · {SAMPLE.company}
            </p>
          </div>

          <div className="shrink-0 text-right">
            <div className="font-mono text-[30px] sm:text-[34px] leading-none font-bold text-accent tabular-nums">
              {score}
            </div>
            <div className="font-mono text-[10.5px] text-faint mt-1">/ 100</div>
          </div>
        </div>

        <div className="h-px bg-border my-5" />

        <ul className="flex flex-col gap-2.5">
          {SAMPLE.reasons.map((reason, i) => (
            <motion.li
              key={reason}
              initial={{ opacity: 0, x: -6 }}
              animate={inView ? { opacity: 1, x: 0 } : {}}
              transition={{ duration: 0.32, delay: 0.45 + i * 0.13 }}
              className="flex items-start gap-2.5 text-[12.5px] text-dim leading-snug"
            >
              <Check size={13} className="text-success shrink-0 mt-[2px]" />
              {reason}
            </motion.li>
          ))}
        </ul>

        <motion.div
          initial={{ opacity: 0 }}
          animate={inView ? { opacity: 1 } : {}}
          transition={{ delay: 1.1 }}
          className="mt-5 flex items-center justify-between gap-3"
        >
          <span className="inline-flex items-center gap-1.5 text-[12.5px] font-medium text-accent">
            View LinkedIn <ExternalLink size={11} />
          </span>
          <span className="inline-flex items-center gap-1.5 text-[11.5px] text-faint">
            <Star size={11} /> Add to watchlist
          </span>
        </motion.div>
      </motion.div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function Section({ id, eyebrow, title, lede, children, className }) {
  return (
    <section id={id} className={cn("px-5 sm:px-8 py-20 sm:py-28", className)}>
      <div className="max-w-6xl mx-auto">
        {eyebrow && (
          <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-accent mb-3.5">
            {eyebrow}
          </div>
        )}
        {title && (
          <h2 className="font-display font-bold text-[clamp(24px,4vw,36px)] leading-[1.15] text-ink tracking-tight text-wrap-balance max-w-2xl">
            {title}
          </h2>
        )}
        {lede && <p className="text-[14.5px] text-dim mt-4 max-w-xl leading-relaxed">{lede}</p>}
        {children}
      </div>
    </section>
  );
}

function Reveal({ children, delay = 0, className }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 14 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.45, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------

const FEATURES = [
  {
    icon: Search,
    title: "Continuous discovery",
    body: "A scheduled pipeline scans research labs, biotech companies and open-source projects, and adds only people it hasn't seen before.",
  },
  {
    icon: Star,
    title: "Scores that explain themselves",
    body: "Every researcher gets a 0–100 score built from company, seniority, field relevance, source confidence and recency — with the reasoning attached.",
  },
  {
    icon: Filter,
    title: "Ranked around your work",
    body: "Set focus areas, target organizations, locations and seniority. Rankings shift immediately, and each result says which preference moved it.",
  },
  {
    icon: Building2,
    title: "Organization intelligence",
    body: "See which labs are growing fastest, who's hiring, and where a field's talent is concentrating — with per-company breakdowns.",
  },
  {
    icon: Mail,
    title: "A digest worth opening",
    body: "Daily or weekly, the strongest new matches land in your inbox with scores, reasoning and direct profile links.",
  },
  {
    icon: Bell,
    title: "Watchlist and reminders",
    body: "Follow anyone worth tracking. Add notes, set a priority and a reminder date, and they resurface when it's time to reach out.",
  },
];

const STEPS = [
  {
    title: "Discover",
    body: "The pipeline queries a self-hosted search index across target organizations and open-source contributions, then de-duplicates against everything already found.",
    detail: "Never returns the same person twice",
  },
  {
    title: "Score",
    body: "Each profile is evaluated on six weighted signals. The score is deterministic and auditable — no black box, and no model you can't inspect.",
    detail: "Six weighted signals, 0–100",
  },
  {
    title: "Deliver",
    body: "Results are ranked against your preferences and delivered to your dashboard and inbox, newest and strongest first.",
    detail: "Dashboard and email",
  },
];

const WORKFLOW = [
  { phase: "Scan", body: "New profiles enter the shared corpus on every scheduled run." },
  { phase: "Rank", body: "Your preferences re-order the corpus without changing anyone else's view." },
  { phase: "Triage", body: "Follow the ones worth tracking; note why, and set a reminder." },
  { phase: "Reach out", body: "Open the profile directly, with the reasoning already in front of you." },
];

const FAQS = [
  {
    q: "Where does the data come from?",
    a: "Public search results and public organization pages, through a self-hosted search index. Helix does not log into LinkedIn, scrape linkedin.com, or automate a browser against it. Every profile link in the database came from a real search result — none are guessed or constructed from a name.",
  },
  {
    q: "How is the score calculated?",
    a: "Six weighted signals: the discovering organization's standing (30), title seniority (20), AI×Biology relevance (20), source confidence (15), recency (10) and profile completeness (5). Your preferences then apply a capped personal adjustment on top. Every component that fires is shown as a reason on the result.",
  },
  {
    q: "Is this a language model?",
    a: "Not currently. Scoring and insights are statistical and rule-based, which is why every ranking can explain itself precisely. Both engines sit behind interfaces designed so a model-backed implementation can replace them without changing anything else.",
  },
  {
    q: "Do other users see my watchlist?",
    a: "No. The discovery corpus is shared — one pipeline run serves every account — but watchlists, notes, preferences and notifications are scoped to your account and never surface in anyone else's search.",
  },
  {
    q: "Can I export my data?",
    a: "Yes. The full dataset exports to CSV on demand, and deleting your account erases your watchlist, notes, preferences and notifications.",
  },
];

const PLANS = [
  {
    name: "Researcher",
    price: "Free",
    note: "While in early access",
    features: ["Full discovery database", "Personalized ranking", "Weekly digest", "Watchlist and notes"],
    cta: "Get started",
    highlighted: false,
  },
  {
    name: "Lab",
    price: "—",
    note: "Pricing not set yet",
    features: ["Everything in Researcher", "Daily digest", "Shared team watchlists", "Priority discovery runs"],
    cta: "Register interest",
    highlighted: true,
  },
  {
    name: "Institution",
    price: "—",
    note: "Pricing not set yet",
    features: ["Everything in Lab", "SSO and admin controls", "API access", "Custom target organizations"],
    cta: "Contact us",
    highlighted: false,
  },
];

// ---------------------------------------------------------------------------

function Nav() {
  const [open, setOpen] = useState(false);
  const links = [
    { href: "#features", label: "Features" },
    { href: "#how", label: "How it works" },
    { href: "#pricing", label: "Pricing" },
    { href: "#faq", label: "FAQ" },
  ];

  return (
    <header className="sticky top-0 z-50 border-b border-border/70 bg-bg/80 backdrop-blur-xl">
      <nav className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2.5 shrink-0">
          <span className="relative inline-flex items-center justify-center w-8 h-8 rounded-[9px] bg-surface-2 border border-border">
            <span aria-hidden="true" className="absolute inset-0 rounded-[9px] bg-accent/25 blur-md" />
            <Dna size={16} className="relative text-accent" />
          </span>
          <span className="font-display font-bold text-[15px] tracking-[0.16em] text-ink">HELIX</span>
        </Link>

        <div className="hidden md:flex items-center gap-7">
          {links.map((l) => (
            <a key={l.href} href={l.href} className="text-[13px] text-dim hover:text-ink transition-colors">
              {l.label}
            </a>
          ))}
        </div>

        <div className="hidden md:flex items-center gap-2.5">
          <Link to="/login" className="text-[13px] font-medium text-dim hover:text-ink px-3 py-2 transition-colors">
            Sign in
          </Link>
          <Link
            to="/signup"
            className="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-[13px] font-semibold text-[#04121f] hover:bg-accent-strong transition-colors shadow-[0_0_20px_-6px_rgba(0,212,255,0.7)]"
          >
            Get started <ArrowRight size={13} />
          </Link>
        </div>

        <button
          onClick={() => setOpen((v) => !v)}
          className="md:hidden p-2 -mr-2 rounded-md text-dim hover:text-ink"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
        >
          {open ? <X size={19} /> : <Menu size={19} />}
        </button>
      </nav>

      {open && (
        <div className="md:hidden border-t border-border bg-bg px-5 py-4 flex flex-col gap-1">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="py-2.5 text-[14px] text-dim hover:text-ink"
            >
              {l.label}
            </a>
          ))}
          <div className="h-px bg-border my-2" />
          <Link to="/login" className="py-2.5 text-[14px] text-dim hover:text-ink">Sign in</Link>
          <Link
            to="/signup"
            className="mt-1 inline-flex items-center justify-center gap-1.5 rounded-md bg-accent px-4 py-2.5 text-[14px] font-semibold text-[#04121f]"
          >
            Get started <ArrowRight size={14} />
          </Link>
        </div>
      )}
    </header>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden px-5 sm:px-8 pt-16 sm:pt-24 pb-20 sm:pb-28">
      <div className="helix-ambient-bg" aria-hidden="true" />
      <div className="relative max-w-6xl mx-auto grid lg:grid-cols-[1.05fr_0.95fr] gap-14 lg:gap-16 items-center">
        <div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-surface-2/60 px-3 py-1.5 text-[11.5px] text-dim mb-7"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-success" aria-hidden="true" />
            Now in early access
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.06 }}
            className="font-display font-bold text-[clamp(32px,6vw,54px)] leading-[1.06] tracking-[-0.02em] text-ink text-wrap-balance"
          >
            Find the people building{" "}
            <span className="bg-gradient-to-r from-accent via-highlight to-accent-2 bg-clip-text text-transparent">
              AI&nbsp;×&nbsp;Biology
            </span>{" "}
            before everyone else does.
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.14 }}
            className="text-[15px] sm:text-[16px] text-dim mt-6 max-w-lg leading-relaxed"
          >
            Helix continuously scans research labs, biotech companies and open-source
            projects, scores every researcher it finds, and tells you exactly why each
            one is worth your attention.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.22 }}
            className="flex flex-col sm:flex-row gap-3 mt-9"
          >
            <Link
              to="/signup"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-6 py-3 text-[14px] font-semibold text-[#04121f] hover:bg-accent-strong transition-colors shadow-[0_0_28px_-6px_rgba(0,212,255,0.75)]"
            >
              Start free <ArrowRight size={15} />
            </Link>
            <a
              href="#how"
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-surface-2/50 px-6 py-3 text-[14px] font-semibold text-ink hover:bg-surface-3 transition-colors"
            >
              See how it works
            </a>
          </motion.div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.35 }}
            className="text-[12px] text-faint mt-5"
          >
            No credit card. Public data only — Helix never scrapes LinkedIn.
          </motion.p>
        </div>

        <ScoredCard />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------

export default function Landing() {
  const [openFaq, setOpenFaq] = useState(0);

  return (
    <div className="min-h-screen bg-bg text-ink antialiased">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-[60] focus:rounded-md focus:bg-accent focus:px-4 focus:py-2 focus:text-[13px] focus:font-semibold focus:text-[#04121f]"
      >
        Skip to content
      </a>

      <Nav />

      <main id="main">
        <Hero />

        {/* Features */}
        <Section
          id="features"
          eyebrow="What it does"
          title="A research instrument, not another contact list."
          lede="Every number on the screen can be traced back to the signal that produced it."
          className="border-t border-border/60"
        >
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-12">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={i * 0.05}>
                <div className="h-full rounded-xl border border-border bg-surface/60 p-5 transition-colors hover:border-accent/30 hover:bg-surface">
                  <span className="inline-flex items-center justify-center w-9 h-9 rounded-lg bg-accent-soft text-accent mb-4">
                    <f.icon size={17} />
                  </span>
                  <h3 className="font-display font-semibold text-[14.5px] text-ink">{f.title}</h3>
                  <p className="text-[13px] text-dim mt-2 leading-relaxed">{f.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </Section>

        {/* How it works — genuinely a sequence, so it's numbered */}
        <Section
          id="how"
          eyebrow="How it works"
          title="Three stages, running on a schedule."
          className="border-t border-border/60 bg-surface/25"
        >
          <div className="grid md:grid-cols-3 gap-5 mt-12">
            {STEPS.map((s, i) => (
              <Reveal key={s.title} delay={i * 0.08}>
                <div className="relative h-full rounded-xl border border-border bg-bg p-6">
                  <div className="flex items-baseline gap-3 mb-4">
                    <span className="font-mono text-[11px] text-accent tabular-nums">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <h3 className="font-display font-semibold text-[16px] text-ink">{s.title}</h3>
                  </div>
                  <p className="text-[13px] text-dim leading-relaxed">{s.body}</p>
                  <div className="mt-5 pt-4 border-t border-border">
                    <span className="font-mono text-[11px] text-faint">{s.detail}</span>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </Section>

        {/* Research workflow */}
        <Section
          eyebrow="Research workflow"
          title="Built around how scouting actually happens."
          lede="Not a feed to scroll. A short loop you can finish."
          className="border-t border-border/60"
        >
          <ol className="mt-12 grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {WORKFLOW.map((w, i) => (
              <Reveal key={w.phase} delay={i * 0.06}>
                <li className="relative h-full rounded-xl border border-border bg-surface/50 p-5">
                  <div
                    aria-hidden="true"
                    className="h-0.5 w-8 rounded-full bg-gradient-to-r from-accent to-accent-2 mb-4"
                  />
                  <h3 className="font-display font-semibold text-[14px] text-ink">{w.phase}</h3>
                  <p className="text-[12.5px] text-dim mt-1.5 leading-relaxed">{w.body}</p>
                </li>
              </Reveal>
            ))}
          </ol>
        </Section>

        {/* Benefits */}
        <Section
          eyebrow="Why teams use it"
          title="Stop rediscovering the same twenty people."
          className="border-t border-border/60 bg-surface/25"
        >
          <div className="grid md:grid-cols-3 gap-8 mt-12">
            {[
              {
                h: "Nothing repeats",
                p: "The pipeline de-duplicates against everything already found, so each run surfaces only genuinely new people.",
              },
              {
                h: "Every ranking is defensible",
                p: "When you put a name in front of a hiring committee, the reasoning is already written down.",
              },
              {
                h: "It keeps working without you",
                p: "Runs on a schedule and reaches you by email. There's no dashboard you're obliged to check.",
              },
            ].map((b, i) => (
              <Reveal key={b.h} delay={i * 0.07}>
                <div>
                  <h3 className="font-display font-semibold text-[16px] text-ink">{b.h}</h3>
                  <p className="text-[13.5px] text-dim mt-2.5 leading-relaxed">{b.p}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </Section>

        {/* Early access — an honest stand-in rather than invented testimonials */}
        <Section
          eyebrow="Early access"
          title="Helix is new, so there are no customer quotes here yet."
          lede="We'd rather leave this space empty than fill it with testimonials nobody said. If you use Helix and it earns one, we'd like to hear from you."
          className="border-t border-border/60"
        >
          <div className="grid sm:grid-cols-3 gap-4 mt-10">
            {[0, 1, 2].map((i) => (
              <Reveal key={i} delay={i * 0.06}>
                <div className="h-full rounded-xl border border-dashed border-border bg-surface/30 p-5 flex flex-col justify-between min-h-[150px]">
                  <p className="text-[13px] text-faint italic leading-relaxed">
                    Reserved for a real quote from an early user.
                  </p>
                  <div className="flex items-center gap-2.5 mt-5">
                    <span className="w-7 h-7 rounded-full bg-surface-3 border border-border" aria-hidden="true" />
                    <span className="font-mono text-[11px] text-faint">awaiting attribution</span>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </Section>

        {/* Pricing */}
        <Section
          id="pricing"
          eyebrow="Pricing"
          title="Free while it's in early access."
          lede="Paid tiers aren't priced yet. Nothing you use today will start charging without notice."
          className="border-t border-border/60 bg-surface/25"
        >
          <div className="grid md:grid-cols-3 gap-4 mt-12">
            {PLANS.map((plan, i) => (
              <Reveal key={plan.name} delay={i * 0.07}>
                <div
                  className={cn(
                    "relative h-full rounded-xl border p-6 flex flex-col",
                    plan.highlighted
                      ? "border-accent/45 bg-surface shadow-[0_0_40px_-20px_rgba(0,212,255,0.5)]"
                      : "border-border bg-bg"
                  )}
                >
                  {plan.highlighted && (
                    <span className="absolute -top-2.5 left-6 rounded-full bg-accent px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#04121f]">
                      Planned
                    </span>
                  )}
                  <h3 className="font-display font-semibold text-[15px] text-ink">{plan.name}</h3>
                  <div className="mt-3 flex items-baseline gap-2">
                    <span className="font-display font-bold text-[30px] text-ink tabular-nums">{plan.price}</span>
                  </div>
                  <p className="font-mono text-[11px] text-faint mt-1.5">{plan.note}</p>

                  <ul className="flex flex-col gap-2.5 mt-6 flex-1">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-start gap-2 text-[12.5px] text-dim">
                        <Check size={13} className="text-success shrink-0 mt-[2px]" />
                        {f}
                      </li>
                    ))}
                  </ul>

                  <Link
                    to="/signup"
                    className={cn(
                      "mt-7 inline-flex items-center justify-center gap-1.5 rounded-lg px-4 py-2.5 text-[13px] font-semibold transition-colors",
                      plan.highlighted
                        ? "bg-accent text-[#04121f] hover:bg-accent-strong"
                        : "border border-border text-ink hover:bg-surface-2"
                    )}
                  >
                    {plan.cta}
                  </Link>
                </div>
              </Reveal>
            ))}
          </div>
        </Section>

        {/* FAQ */}
        <Section id="faq" eyebrow="FAQ" title="Questions worth answering directly." className="border-t border-border/60">
          <div className="mt-10 max-w-3xl divide-y divide-border border-y border-border">
            {FAQS.map((item, i) => {
              const isOpen = openFaq === i;
              return (
                <div key={item.q}>
                  <button
                    onClick={() => setOpenFaq(isOpen ? -1 : i)}
                    aria-expanded={isOpen}
                    className="w-full flex items-center justify-between gap-4 py-5 text-left group"
                  >
                    <span className="font-display font-semibold text-[14.5px] text-ink group-hover:text-accent transition-colors">
                      {item.q}
                    </span>
                    <ChevronDown
                      size={16}
                      className={cn(
                        "shrink-0 text-faint transition-transform duration-200",
                        isOpen && "rotate-180 text-accent"
                      )}
                    />
                  </button>
                  {isOpen && (
                    <motion.p
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: "auto" }}
                      transition={{ duration: 0.22 }}
                      className="overflow-hidden text-[13.5px] text-dim leading-relaxed pb-5 pr-8"
                    >
                      {item.a}
                    </motion.p>
                  )}
                </div>
              );
            })}
          </div>
        </Section>

        {/* CTA */}
        <section className="relative overflow-hidden border-t border-border/60 px-5 sm:px-8 py-24 sm:py-32">
          <div className="helix-ambient-bg" aria-hidden="true" />
          <div className="relative max-w-2xl mx-auto text-center">
            <Reveal>
              <h2 className="font-display font-bold text-[clamp(26px,4.5vw,40px)] leading-[1.12] tracking-tight text-ink text-wrap-balance">
                The next person worth knowing is already in the data.
              </h2>
              <p className="text-[15px] text-dim mt-5 leading-relaxed">
                Create an account and Helix will start ranking the network around what you work on.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center mt-9">
                <Link
                  to="/signup"
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-7 py-3 text-[14px] font-semibold text-[#04121f] hover:bg-accent-strong transition-colors shadow-[0_0_28px_-6px_rgba(0,212,255,0.75)]"
                >
                  Get started free <ArrowRight size={15} />
                </Link>
                <Link
                  to="/login"
                  className="inline-flex items-center justify-center rounded-lg border border-border px-7 py-3 text-[14px] font-semibold text-ink hover:bg-surface-2 transition-colors"
                >
                  Sign in
                </Link>
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      <footer className="border-t border-border px-5 sm:px-8 py-12">
        <div className="max-w-6xl mx-auto">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-2.5">
                <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-surface-2 border border-border">
                  <Dna size={14} className="text-accent" />
                </span>
                <span className="font-display font-bold text-[13.5px] tracking-[0.16em] text-ink">HELIX</span>
              </div>
              <p className="text-[12px] text-faint mt-3 max-w-xs leading-relaxed">
                Research discovery at the intersection of artificial intelligence and
                computational biology.
              </p>
            </div>

            <nav className="flex flex-wrap gap-x-7 gap-y-2.5" aria-label="Footer">
              <a href="#features" className="text-[12.5px] text-dim hover:text-ink transition-colors">Features</a>
              <a href="#how" className="text-[12.5px] text-dim hover:text-ink transition-colors">How it works</a>
              <a href="#pricing" className="text-[12.5px] text-dim hover:text-ink transition-colors">Pricing</a>
              <a href="#faq" className="text-[12.5px] text-dim hover:text-ink transition-colors">FAQ</a>
              <a
                href="https://github.com/sabaarabiat11-tech/helix"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 text-[12.5px] text-dim hover:text-ink transition-colors"
              >
                <Code2 size={13} /> Source
              </a>
            </nav>
          </div>

          <div className="h-px bg-border my-8" />

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <p className="font-mono text-[11px] text-faint">
              Helix · AI × Biology discovery
            </p>
            <p className="text-[11.5px] text-faint max-w-md sm:text-right leading-relaxed">
              Built on public search results and public organization pages. Helix does not
              access LinkedIn accounts or scrape linkedin.com.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
