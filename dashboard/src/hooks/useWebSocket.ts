import { useCallback, useEffect, useRef, useState } from "react";
import type {
  ConnectionStatus,
  SnapshotData,
  WebSocketMessage,
} from "../types/metrics";

const MAX_SNAPSHOTS = 300;
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;

interface UseWebSocketResult {
  snapshots: SnapshotData[];
  latestSnapshot: SnapshotData | null;
  connectionStatus: ConnectionStatus;
}

function getWsUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/metrics`;
}

function isSnapshotMessage(data: unknown): data is WebSocketMessage {
  if (typeof data !== "object" || data === null) return false;
  const msg = data as Record<string, unknown>;
  return msg["type"] === "snapshot" && typeof msg["data"] === "object";
}

export function useWebSocket(): UseWebSocketResult {
  const [snapshots, setSnapshots] = useState<SnapshotData[]>([]);
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const ws = new WebSocket(getWsUrl());
    wsRef.current = ws;
    setConnectionStatus("connecting");

    ws.onopen = () => {
      if (!mountedRef.current) return;
      reconnectAttemptRef.current = 0;
      setConnectionStatus("connected");
    };

    ws.onmessage = (event: MessageEvent<string>) => {
      if (!mountedRef.current) return;
      try {
        const parsed: unknown = JSON.parse(event.data);
        if (isSnapshotMessage(parsed)) {
          const snapshot = parsed.data;
          setSnapshots((prev) => {
            const next = [...prev, snapshot];
            return next.length > MAX_SNAPSHOTS ? next.slice(-MAX_SNAPSHOTS) : next;
          });
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setConnectionStatus("disconnected");
      scheduleReconnect();
    };

    ws.onerror = () => {
      // onclose will fire after onerror, so reconnect is handled there
    };
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    const attempt = reconnectAttemptRef.current;
    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, attempt),
      RECONNECT_MAX_MS,
    );
    reconnectAttemptRef.current = attempt + 1;
    reconnectTimerRef.current = setTimeout(() => {
      if (mountedRef.current) {
        connect();
      }
    }, delay);
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  const latestSnapshot =
    snapshots.length > 0 ? snapshots[snapshots.length - 1] ?? null : null;

  return { snapshots, latestSnapshot, connectionStatus };
}
