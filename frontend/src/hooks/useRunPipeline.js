import { useCallback, useEffect, useRef, useState } from "react";
import { api, openRunLogSocket } from "../api/client";

export function useRunPipeline(onComplete) {
  const [running, setRunning] = useState(false);
  const [logLines, setLogLines] = useState([]);
  const [error, setError] = useState("");
  const socketRef = useRef(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  const attachSocket = useCallback(() => {
    // Guard against React StrictMode's dev-only double-invocation of mount
    // effects, which would otherwise open two sockets and duplicate every
    // replayed/streamed log line.
    if (socketRef.current) return;

    const ws = openRunLogSocket();
    socketRef.current = ws;

    ws.onmessage = (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        payload = null;
      }
      if (payload && payload.event === "closed") {
        setRunning(false);
        ws.close();
        onCompleteRef.current?.();
        return;
      }
      setLogLines((prev) => [...prev, event.data]);
    };

    ws.onerror = () => setError("Log stream connection error.");
    ws.onclose = () => {
      if (socketRef.current === ws) socketRef.current = null;
    };
  }, []);

  const detachSocket = useCallback(() => {
    const ws = socketRef.current;
    if (!ws) return;
    // Detach handlers synchronously before closing so that any frames
    // already in flight for this socket don't get processed after we've
    // decided to drop it (matters for the StrictMode double-mount case
    // below, where the "cleanup" socket must not leak duplicate lines into
    // the real one).
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    ws.close();
    socketRef.current = null;
  }, []);

  // On mount, check whether a run is already in progress (e.g. page was
  // refreshed mid-run) and reattach the live log stream if so.
  useEffect(() => {
    api
      .runState()
      .then((state) => {
        if (state.running) {
          setRunning(true);
          attachSocket();
        }
      })
      .catch(() => {});
    return detachSocket;
  }, [attachSocket, detachSocket]);

  const start = useCallback(async () => {
    setError("");
    setLogLines([]);
    try {
      await api.triggerRun();
      setRunning(true);
      attachSocket();
    } catch (e) {
      setError(e.message || "Failed to start the discovery run.");
    }
  }, [attachSocket]);

  return { running, logLines, error, start };
}
