import { cn } from "../../lib/cn";

/** Base surface used everywhere: stat cards, panels, table wrappers, insight cards.
 * All cards use the glass treatment now (Helix's signature depth), `hover`
 * adds the glow-on-hover premium micro-interaction. */
export default function Card({ className, glass = true, hover = false, children, ...props }) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-surface",
        glass && "glass-panel",
        hover &&
          "transition-all duration-200 hover:border-accent/40 hover:shadow-[0_0_0_1px_rgba(0,212,255,0.15),0_8px_30px_-8px_rgba(0,212,255,0.25)]",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, children, ...props }) {
  return (
    <div className={cn("flex items-center justify-between px-5 pt-5", className)} {...props}>
      {children}
    </div>
  );
}

export function CardBody({ className, children, ...props }) {
  return (
    <div className={cn("p-5", className)} {...props}>
      {children}
    </div>
  );
}
