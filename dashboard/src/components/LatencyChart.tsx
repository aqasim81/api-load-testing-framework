import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SnapshotData } from "../types/metrics";

interface Props {
  snapshots: SnapshotData[];
}

interface ChartPoint {
  elapsed_seconds: number;
  p50: number;
  p95: number;
  p99: number;
}

function formatElapsed(seconds: number): string {
  return `${Math.round(seconds)}s`;
}

export default function LatencyChart({ snapshots }: Props) {
  const data: ChartPoint[] = snapshots.map((s) => ({
    elapsed_seconds: s.elapsed_seconds,
    p50: s.latency.p50,
    p95: s.latency.p95,
    p99: s.latency.p99,
  }));

  return (
    <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Latency Percentiles (ms)
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="elapsed_seconds"
            tickFormatter={formatElapsed}
            stroke="#6b7280"
            fontSize={12}
          />
          <YAxis stroke="#6b7280" fontSize={12} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "0.5rem",
              color: "#f3f4f6",
            }}
            labelFormatter={(v: number) => `${formatElapsed(v)} elapsed`}
            formatter={(value: number) => [`${value.toFixed(1)}ms`]}
          />
          <Area
            type="monotone"
            dataKey="p99"
            name="p99"
            stroke="#ef4444"
            fill="#ef4444"
            fillOpacity={0.15}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="p95"
            name="p95"
            stroke="#f59e0b"
            fill="#f59e0b"
            fillOpacity={0.2}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="p50"
            name="p50"
            stroke="#22c55e"
            fill="#22c55e"
            fillOpacity={0.25}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
