import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api/client";

const NotificationsContext = createContext(null);
const POLL_INTERVAL_MS = 30_000;

export function NotificationsProvider({ children }) {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const refresh = useCallback(async () => {
    try {
      const data = await api.notifications();
      setNotifications(data.notifications);
      setUnreadCount(data.unread_count);
    } catch {
      /* silent — notification polling shouldn't surface errors to the whole app */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  const markRead = useCallback(
    async (id) => {
      await api.markNotificationRead(id);
      await refresh();
    },
    [refresh]
  );

  const markAllRead = useCallback(async () => {
    await api.markAllNotificationsRead();
    await refresh();
  }, [refresh]);

  return (
    <NotificationsContext.Provider value={{ notifications, unreadCount, refresh, markRead, markAllRead }}>
      {children}
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error("useNotifications must be used within NotificationsProvider");
  return ctx;
}
