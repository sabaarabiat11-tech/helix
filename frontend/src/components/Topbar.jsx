import { Menu, Moon, Sun, Search } from "lucide-react";
import RunDiscoveryButton from "./RunDiscoveryButton";
import NotificationBell from "./NotificationBell";
import { useAuth } from "../hooks/AuthContext";

export default function Topbar({ title, subtitle, onMenuClick, right, titleAsHeading = true }) {
  // Theme comes from the account, not this browser, so it follows the user
  // across devices instead of drifting per-device.
  const { theme, setTheme } = useAuth();
  const toggle = () => setTheme(theme === "dark" ? "light" : "dark");
  const TitleTag = titleAsHeading ? "h1" : "p";

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between gap-4 h-16 px-4 lg:px-6 border-b border-border bg-surface/80 backdrop-blur-xl">
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-1.5 -ml-1.5 rounded-md text-dim hover:text-ink hover:bg-surface-2"
          aria-label="Toggle navigation"
        >
          <Menu size={20} />
        </button>
        <div className="min-w-0">
          <TitleTag className="font-display font-bold text-[17px] text-ink truncate">{title}</TitleTag>
          {subtitle && <p className="text-[12px] text-faint truncate hidden sm:block">{subtitle}</p>}
        </div>
      </div>

      <div className="flex items-center gap-1.5 sm:gap-2.5 shrink-0">
        {right}
        <button
          onClick={() => document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
          className="hidden md:inline-flex items-center gap-2 rounded-md border border-border px-3 py-1.5 text-[12px] text-faint hover:text-ink hover:border-accent/40 transition-colors"
        >
          <Search size={13} /> Search
          <kbd className="ml-1 text-[10px] border border-border rounded px-1 py-0.5">⌘K</kbd>
        </button>
        <button
          onClick={toggle}
          className="p-2 rounded-md text-dim hover:text-ink hover:bg-surface-2"
          aria-label="Toggle color theme"
          title="Toggle theme"
        >
          {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
        </button>
        <NotificationBell />
        <RunDiscoveryButton />
      </div>
    </header>
  );
}
