import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api/client";

const WatchlistContext = createContext(null);

export function WatchlistProvider({ children }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await api.watchlist();
      setEntries(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const followedIds = new Set(entries.map((e) => e.person_id));

  const follow = useCallback(
    async (personId) => {
      await api.follow(personId);
      await refresh();
    },
    [refresh]
  );

  const unfollow = useCallback(
    async (personId) => {
      await api.unfollow(personId);
      await refresh();
    },
    [refresh]
  );

  const toggle = useCallback(
    async (personId) => {
      if (followedIds.has(personId)) await unfollow(personId);
      else await follow(personId);
    },
    [followedIds, follow, unfollow]
  );

  const updateEntry = useCallback(
    async (personId, fields) => {
      await api.updateWatchlistEntry(personId, fields);
      await refresh();
    },
    [refresh]
  );

  return (
    <WatchlistContext.Provider
      value={{ entries, followedIds, loading, follow, unfollow, toggle, updateEntry, refresh }}
    >
      {children}
    </WatchlistContext.Provider>
  );
}

export function useWatchlist() {
  const ctx = useContext(WatchlistContext);
  if (!ctx) throw new Error("useWatchlist must be used within WatchlistProvider");
  return ctx;
}
