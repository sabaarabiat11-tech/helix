/**
 * Shown while a lazily-loaded route chunk downloads.
 *
 * Deliberately plain CSS with no dependencies — a fallback that imported the
 * animation library would have to wait for that library to load, which is
 * exactly the delay it exists to cover. On a fast connection this is never
 * seen; the fade-in delay keeps it from flashing when the chunk arrives
 * immediately.
 */
export default function RouteFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-bg" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-4 opacity-0 animate-[helix-fade_0.25s_ease-out_0.15s_forwards]">
        <div className="relative w-9 h-9">
          <span className="absolute inset-0 rounded-full border-2 border-border" />
          <span className="absolute inset-0 rounded-full border-2 border-transparent border-t-accent animate-spin" />
        </div>
        <span className="text-[12.5px] text-faint">Loading…</span>
      </div>
    </div>
  );
}
