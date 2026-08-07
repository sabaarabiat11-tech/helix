import { Star } from "lucide-react";
import { cn } from "../../lib/cn";

export default function Stars({ count, max = 5, size = 13, className }) {
  return (
    <div className={cn("inline-flex items-center gap-0.5", className)} aria-label={`${count} out of ${max} stars`}>
      {Array.from({ length: max }).map((_, i) => (
        <Star
          key={i}
          size={size}
          strokeWidth={1.75}
          className={i < count ? "fill-accent text-accent" : "fill-transparent text-surface-3"}
        />
      ))}
    </div>
  );
}
