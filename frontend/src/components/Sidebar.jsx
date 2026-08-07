import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  LayoutDashboard, Users, Building2, BarChart3, FileText, Sparkles, Star, Clock, Zap,
  ChevronsUpDown, LogOut, Settings as SettingsIcon,
} from "lucide-react";
import HelixMark from "./HelixMark";
import { useAuth } from "../hooks/AuthContext";

const NAV_GROUPS = [
  {
    label: "Overview",
    items: [{ to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, end: true }],
  },
  {
    label: "Discover",
    items: [
      { to: "/discoveries", label: "New Discoveries", icon: Users },
      { to: "/recommendations", label: "Recommendations", icon: Sparkles },
      { to: "/companies", label: "Companies", icon: Building2 },
    ],
  },
  {
    label: "Engage",
    items: [
      { to: "/watchlist", label: "Watchlist", icon: Star },
      { to: "/timeline", label: "Timeline", icon: Clock },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { to: "/insights", label: "AI Insights", icon: Zap },
      { to: "/analytics", label: "Analytics", icon: BarChart3 },
      { to: "/reports", label: "Reports", icon: FileText },
    ],
  },
];

export default function Sidebar({ open, onNavigate }) {
  return (
    <aside
      className={`
        fixed lg:static inset-y-0 left-0 z-40 w-64 shrink-0
        border-r border-border bg-surface/85 backdrop-blur-xl
        flex flex-col
        transition-transform duration-200
        ${open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
      `}
    >
      <div className="flex items-center gap-3 px-5 h-16 border-b border-border shrink-0">
        <div className="relative">
          <div className="absolute inset-0 rounded-full bg-accent/30 blur-md" />
          <HelixMark size={32} className="relative" />
        </div>
        <div className="leading-tight">
          <div className="font-display font-bold text-[16px] tracking-tight text-ink">Helix</div>
          <div className="text-[10px] uppercase tracking-[0.1em] text-faint">Biotech Intelligence</div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-4 px-3 flex flex-col gap-5">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <div className="px-3 mb-1.5 text-[10.5px] font-semibold uppercase tracking-[0.08em] text-faint">
              {group.label}
            </div>
            <div className="flex flex-col gap-0.5">
              {group.items.map(({ to, label, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    `group flex items-center gap-3 rounded-md px-3 py-2 text-[13.5px] font-medium transition-all ${
                      isActive
                        ? "bg-accent-soft text-accent shadow-[inset_0_0_0_1px_rgba(0,212,255,0.25)]"
                        : "text-dim hover:text-ink hover:bg-surface-2"
                    }`
                  }
                >
                  <Icon size={17} strokeWidth={2} />
                  {label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-border shrink-0 p-3">
        <AccountMenu onNavigate={onNavigate} />
      </div>
    </aside>
  );
}

/** Avatar, account actions and sign-out — the standard bottom-left position
 * users expect in a product like this. */
function AccountMenu({ onNavigate }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  if (!user) return null;

  const initials = (user.name || user.email)
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");

  async function handleSignOut() {
    setOpen(false);
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <DropdownMenu.Root open={open} onOpenChange={setOpen}>
      <DropdownMenu.Trigger asChild>
        <button
          className="w-full flex items-center gap-2.5 rounded-md px-2 py-2 text-left transition-colors hover:bg-surface-2 focus-visible:outline-2 focus-visible:outline-accent focus-visible:outline-offset-2"
          aria-label="Account menu"
        >
          {user.avatar_url ? (
            <img
              src={user.avatar_url}
              alt=""
              className="w-8 h-8 rounded-full object-cover shrink-0 border border-border"
            />
          ) : (
            <span className="w-8 h-8 rounded-full shrink-0 bg-accent-soft border border-accent/25 text-accent text-[11.5px] font-semibold inline-flex items-center justify-center">
              {initials}
            </span>
          )}
          <span className="min-w-0 flex-1">
            <span className="block text-[12.5px] font-medium text-ink truncate">{user.name}</span>
            <span className="block text-[11px] text-faint truncate">{user.email}</span>
          </span>
          <ChevronsUpDown size={14} className="text-faint shrink-0" />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          side="top"
          align="start"
          sideOffset={6}
          className="z-50 min-w-[220px] rounded-lg border border-border bg-surface-2 p-1 shadow-2xl"
        >
          {!user.email_verified && (
            <div className="px-2.5 py-2 mb-1 rounded-md bg-warning-soft text-[11.5px] text-warning">
              Email not confirmed yet
            </div>
          )}

          <DropdownMenu.Item asChild>
            <NavLink
              to="/settings"
              onClick={onNavigate}
              className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-dim hover:text-ink hover:bg-surface-3 outline-none cursor-pointer data-[highlighted]:bg-surface-3 data-[highlighted]:text-ink"
            >
              <SettingsIcon size={15} /> Settings
            </NavLink>
          </DropdownMenu.Item>

          <DropdownMenu.Separator className="h-px bg-border my-1" />

          <DropdownMenu.Item
            onSelect={handleSignOut}
            className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] text-dim hover:text-danger hover:bg-danger-soft outline-none cursor-pointer data-[highlighted]:bg-danger-soft data-[highlighted]:text-danger"
          >
            <LogOut size={15} /> Sign out
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
