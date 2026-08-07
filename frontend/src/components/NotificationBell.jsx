import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Bell, CheckCheck, Sparkles, Building2, Activity, FileText } from "lucide-react";
import { useNotifications } from "../hooks/NotificationsContext";
import { formatRelativeTime } from "../lib/format";
import Button from "./ui/Button";
import EmptyState from "./ui/EmptyState";

const ICON_BY_TYPE = {
  discovery: Sparkles,
  company: Building2,
  pipeline: Activity,
  report: FileText,
};

export default function NotificationBell() {
  const { notifications, unreadCount, markRead, markAllRead } = useNotifications();

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className="relative p-2 rounded-md text-dim hover:text-ink hover:bg-surface-2"
          aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
        >
          <Bell size={17} />
          {unreadCount > 0 && (
            <span className="absolute top-1 right-1 min-w-[15px] h-[15px] px-[3px] rounded-full bg-accent text-[9px] font-bold text-[#04121f] flex items-center justify-center">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={8}
          className="z-50 w-80 max-h-[70vh] overflow-y-auto rounded-lg border border-border bg-surface shadow-2xl"
          style={{ animation: "helix-pop 120ms ease-out" }}
        >
          <div className="flex items-center justify-between px-4 py-3 border-b border-border sticky top-0 bg-surface">
            <span className="font-display font-semibold text-[13px] text-ink">Notifications</span>
            {unreadCount > 0 && (
              <Button variant="ghost" size="sm" onClick={markAllRead} className="!px-2 !py-1 text-[11px]">
                <CheckCheck size={13} /> Mark all read
              </Button>
            )}
          </div>

          {notifications.length === 0 ? (
            <EmptyState
              icon={Bell}
              title="No notifications yet"
              description="You'll see updates here after your next discovery run."
            />
          ) : (
            <ul>
              {notifications.map((n) => {
                const Icon = ICON_BY_TYPE[n.type] || Bell;
                return (
                  <li
                    key={n.id}
                    onClick={() => !n.read && markRead(n.id)}
                    className={`flex gap-3 px-4 py-3 border-b border-border last:border-0 cursor-pointer hover:bg-surface-2/50 ${
                      !n.read ? "bg-accent-soft/30" : ""
                    }`}
                  >
                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-surface-2 text-dim shrink-0">
                      <Icon size={14} />
                    </span>
                    <div className="min-w-0">
                      <div className="text-[12.5px] font-medium text-ink">{n.title}</div>
                      <div className="text-[11.5px] text-faint">{n.message}</div>
                      <div className="text-[10.5px] text-faint mt-1 font-mono">{formatRelativeTime(n.created_at)}</div>
                    </div>
                    {!n.read && <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0 mt-1.5" />}
                  </li>
                );
              })}
            </ul>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
