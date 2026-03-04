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

function formatElapsed(seconds: number): string {
  return `${Math.round(seconds)}s`;
}

export default function ConcurrencyChart({ snapshots }: Props) {
  return (
    <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Active Users
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={snapshots}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="elapsed_seconds"
            tickFormatter={formatElapsed}
            stroke="#6b7280"
            fontSize={12}
          />
          <YAxis stroke="#6b7280" fontSize={12} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "0.5rem",
              color: "#f3f4f6",
            }}
            labelFormatter={(v: number) => `${formatElapsed(v)} elapsed`}
          />
          <Area
            type="monotone"
            dataKey="active_users"
            name="Active Users"
            stroke="#3b82f6"
            fill="#3b82f6"
            fillOpacity={0.2}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
