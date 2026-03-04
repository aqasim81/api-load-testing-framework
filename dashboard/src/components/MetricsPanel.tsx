import type { SnapshotData } from "../types/metrics";

interface Props {
  latestSnapshot: SnapshotData | null;
  previousSnapshot: SnapshotData | null;
}

interface MetricCardProps {
  label: string;
  value: string;
  trend: number | null;
  invertTrend?: boolean;
}

function formatTrend(current: number, previous: number): number | null {
  if (previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

function MetricCard({ label, value, trend, invertTrend }: MetricCardProps) {
  let trendEl = null;
  if (trend !== null && Math.abs(trend) > 0.1) {
    const isUp = trend > 0;
    const isGood = invertTrend ? !isUp : isUp;
    const arrow = isUp ? "\u2191" : "\u2193";
    const color = isGood ? "text-green-400" : "text-red-400";
    trendEl = (
      <span className={`text-xs ${color}`}>
        {arrow} {Math.abs(trend).toFixed(1)}%
      </span>
    );
  }

  return (
    <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide">{label}</p>
      <div className="mt-1 flex items-baseline gap-2">
        <p className="text-2xl font-semibold text-gray-100">{value}</p>
        {trendEl}
      </div>
    </div>
  );
}

export default function MetricsPanel({
  latestSnapshot,
  previousSnapshot,
}: Props) {
  if (!latestSnapshot) {
    return (
      <div className="grid grid-cols-5 gap-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div
            key={i}
            className="rounded-lg bg-gray-900 border border-gray-800 p-4 h-20 animate-pulse"
          />
        ))}
      </div>
    );
  }

  const rpsTrend = previousSnapshot
    ? formatTrend(latestSnapshot.rps, previousSnapshot.rps)
    : null;
  const p95Trend = previousSnapshot
    ? formatTrend(latestSnapshot.latency.p95, previousSnapshot.latency.p95)
    : null;
  const p99Trend = previousSnapshot
    ? formatTrend(latestSnapshot.latency.p99, previousSnapshot.latency.p99)
    : null;
  const errorTrend = previousSnapshot
    ? formatTrend(latestSnapshot.errors.rate, previousSnapshot.errors.rate)
    : null;

  return (
    <div className="grid grid-cols-5 gap-3">
      <MetricCard
        label="Active Users"
        value={latestSnapshot.active_users.toLocaleString()}
        trend={null}
      />
      <MetricCard
        label="RPS"
        value={latestSnapshot.rps.toFixed(1)}
        trend={rpsTrend}
      />
      <MetricCard
        label="p95 Latency"
        value={`${latestSnapshot.latency.p95.toFixed(1)}ms`}
        trend={p95Trend}
        invertTrend
      />
      <MetricCard
        label="p99 Latency"
        value={`${latestSnapshot.latency.p99.toFixed(1)}ms`}
        trend={p99Trend}
        invertTrend
      />
      <MetricCard
        label="Error Rate"
        value={`${(latestSnapshot.errors.rate * 100).toFixed(2)}%`}
        trend={errorTrend}
        invertTrend
      />
    </div>
  );
}
