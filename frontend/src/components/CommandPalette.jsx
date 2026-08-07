import { useCallback, useEffect, useState } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import {
  Play, FileText, Users, Star, LayoutDashboard, Building2, BarChart3, Sparkles, Clock, Search,
} from "lucide-react";
import { api } from "../api/client";
import { useRun } from "../hooks/RunContext";

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const navigate = useNavigate();
  const { startRun } = useRun();

  useEffect(() => {
    function onKeyDown(e) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setResults(null);
      return;
    }
    const t = setTimeout(() => {
      api.search(query).then(setResults).catch(() => setResults(null));
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  const go = useCallback(
    (path) => {
      navigate(path);
      setOpen(false);
      setQuery("");
    },
    [navigate]
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center pt-[12vh] px-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setOpen(false)} />
      <Command
        className="relative w-full max-w-lg rounded-lg border border-border bg-surface shadow-2xl overflow-hidden"
        style={{ animation: "helix-pop 120ms ease-out" }}
        shouldFilter={false}
      >
        <div className="flex items-center gap-2.5 px-4 border-b border-border">
          <Search size={15} className="text-faint shrink-0" />
          <Command.Input
            value={query}
            onValueChange={setQuery}
            placeholder="Search people, companies, or run a command…"
            className="flex-1 bg-transparent py-3.5 text-[13.5px] text-ink placeholder:text-faint focus:outline-none"
            autoFocus
          />
          <kbd className="text-[10px] text-faint border border-border rounded px-1.5 py-0.5">esc</kbd>
        </div>

        <Command.List className="max-h-[60vh] overflow-y-auto p-2">
          <Command.Empty className="py-8 text-center text-[12.5px] text-faint">No results found.</Command.Empty>

          {!query.trim() && (
            <Command.Group heading="Quick actions" className="text-[11px] font-medium text-faint uppercase tracking-wide px-2 py-1.5">
              <PaletteItem icon={Play} label="Run Discovery" onSelect={() => { setOpen(false); startRun(); }} />
              <PaletteItem icon={LayoutDashboard} label="Go to Dashboard" onSelect={() => go("/")} />
              <PaletteItem icon={Users} label="Go to New Discoveries" onSelect={() => go("/discoveries")} />
              <PaletteItem icon={Star} label="Go to Watchlist" onSelect={() => go("/watchlist")} />
              <PaletteItem icon={Sparkles} label="Go to Recommendations" onSelect={() => go("/recommendations")} />
              <PaletteItem icon={Building2} label="Go to Companies" onSelect={() => go("/companies")} />
              <PaletteItem icon={BarChart3} label="Go to Analytics" onSelect={() => go("/analytics")} />
              <PaletteItem icon={Clock} label="Go to Timeline" onSelect={() => go("/timeline")} />
              <PaletteItem icon={FileText} label="Open Reports" onSelect={() => go("/reports")} />
            </Command.Group>
          )}

          {results && results.people.length > 0 && (
            <Command.Group heading="People" className="text-[11px] font-medium text-faint uppercase tracking-wide px-2 py-1.5 mt-1">
              {results.people.map((p) => (
                <PaletteItem
                  key={p.id}
                  icon={Users}
                  label={`${p.name} — ${p.company}`}
                  onSelect={() => go(`/discoveries?search=${encodeURIComponent(p.name)}`)}
                />
              ))}
            </Command.Group>
          )}

          {results && results.companies.length > 0 && (
            <Command.Group heading="Companies" className="text-[11px] font-medium text-faint uppercase tracking-wide px-2 py-1.5 mt-1">
              {results.companies.map((c) => (
                <PaletteItem
                  key={c.company}
                  icon={Building2}
                  label={`${c.company} (${c.n})`}
                  onSelect={() => go(`/companies/${encodeURIComponent(c.company)}`)}
                />
              ))}
            </Command.Group>
          )}
        </Command.List>
      </Command>
    </div>
  );
}

function PaletteItem({ icon: Icon, label, onSelect }) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex items-center gap-2.5 px-2.5 py-2 rounded-md text-[13px] text-ink cursor-pointer data-[selected=true]:bg-accent-soft data-[selected=true]:text-accent"
    >
      <Icon size={15} />
      {label}
    </Command.Item>
  );
}
