import { Star } from "lucide-react";
import { useWatchlist } from "../hooks/WatchlistContext";
import { cn } from "../lib/cn";

export default function FollowButton({ personId, size = 16, className }) {
  const { followedIds, toggle } = useWatchlist();
  const following = followedIds.has(personId);

  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        toggle(personId);
      }}
      className={cn(
        "inline-flex items-center justify-center rounded-md p-1.5 transition-colors",
        following ? "text-accent hover:text-accent-strong" : "text-faint hover:text-ink hover:bg-surface-2",
        className
      )}
      aria-pressed={following}
      aria-label={following ? "Remove from watchlist" : "Add to watchlist"}
      title={following ? "Following" : "Follow"}
    >
      <Star size={size} className={following ? "fill-accent" : "fill-transparent"} strokeWidth={1.75} />
    </button>
  );
}
