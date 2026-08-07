import { cn } from "../../lib/cn";

export default function Skeleton({ className }) {
  return <div className={cn("animate-pulse rounded-md bg-surface-3", className)} />;
}

export function SkeletonText({ lines = 3, className }) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={cn("h-3", i === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="rounded-lg border border-border bg-surface p-5 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-8 w-8 rounded-md" />
      </div>
      <Skeleton className="h-9 w-20" />
      <Skeleton className="h-3 w-28" />
    </div>
  );
}

export function SkeletonRow({ columns = 5 }) {
  return (
    <tr className="border-b border-border last:border-0">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-3.5 w-full max-w-[140px]" />
        </td>
      ))}
    </tr>
  );
}
