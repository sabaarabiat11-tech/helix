import { cva } from "class-variance-authority";
import { cn } from "../../lib/cn";

const badge = cva("inline-flex items-center gap-1.5 rounded-full font-medium whitespace-nowrap", {
  variants: {
    tone: {
      success: "bg-success-soft text-success",
      warning: "bg-warning-soft text-warning",
      danger: "bg-danger-soft text-danger",
      accent: "bg-accent-soft text-accent",
      neutral: "bg-surface-3 text-dim",
    },
    size: {
      sm: "text-[10.5px] px-2 py-0.5",
      md: "text-[11.5px] px-2.5 py-1",
    },
  },
  defaultVariants: { tone: "neutral", size: "md" },
});

export default function Badge({ tone, size, dot = true, className, children }) {
  return (
    <span className={cn(badge({ tone, size }), className)}>
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current shrink-0" />}
      {children}
    </span>
  );
}
