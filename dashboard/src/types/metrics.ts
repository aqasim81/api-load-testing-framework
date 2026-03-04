/** Latency percentiles and aggregate values in milliseconds. */
export interface LatencyMetrics {
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  p99: number;
  p999: number;
  min: number;
  max: number;
  avg: number;
}

/** Error summary for a snapshot interval. */
export interface ErrorMetrics {
  total: number;
  rate: number;
  by_status: Record<string, number>;
}

/** Per-endpoint metrics within a snapshot. */
export interface EndpointSnapshot {
  name: string;
  rps: number;
  request_count: number;
  error_count: number;
  error_rate: number;
  p50: number;
  p75: number;
  p90: number;
  p95: number;
  p99: number;
  min: number;
  max: number;
  avg: number;
}

/** Point-in-time aggregated metrics from the server. */
export interface SnapshotData {
  timestamp: number;
  elapsed_seconds: number;
  active_users: number;
  rps: number;
  total_requests: number;
  latency: LatencyMetrics;
  errors: ErrorMetrics;
  endpoints: EndpointSnapshot[];
}

/** WebSocket message envelope. */
export interface WebSocketMessage {
  type: "snapshot";
  data: SnapshotData;
}

/** WebSocket connection state. */
export type ConnectionStatus = "connecting" | "connected" | "disconnected";
