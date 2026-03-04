import { useMemo } from "react";
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

const STATUS_COLORS: Record<string, string> = {
  "400": "#f59e0b",
  "401": "#f97316",
  "403": "#f97316",
  "404": "#a855f7",
  "429": "#06b6d4",
  "500": "#ef4444",
  "502": "#dc2626",
  "503": "#b91c1c",
};

const DEFAULT_COLOR = "#6b7280";

function formatElapsed(seconds: number): string {
  return `${Math.round(seconds)}s`;
}

export default function ErrorChart({ snapshots }: Props) {
  // Collect all unique status codes across snapshots
  const statusCodes = useMemo(() => {
    const codes = new Set<string>();
    for (const snap of snapshots) {
      for (const code of Object.keys(snap.errors.by_status)) {
        codes.add(code);
      }
    }
    return Array.from(codes).sort();
  }, [snapshots]);

  // Build chart data with one key per status code
  const data = useMemo(() => {
    return snapshots.map((snap) => {
      const point: Record<string, number> = {
        elapsed_seconds: snap.elapsed_seconds,
        total: snap.errors.total,
      };
      for (const code of statusCodes) {
        point[code] = snap.errors.by_status[code] ?? 0;
      }
      return point;
    });
  }, [snapshots, statusCodes]);

  const hasStatusBreakdown = statusCodes.length > 0;

  return (
    <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Errors
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
          {hasStatusBreakdown ? (
            statusCodes.map((code) => (
              <Area
                key={code}
                type="monotone"
                dataKey={code}
                name={`HTTP ${code}`}
                stackId="errors"
                stroke={STATUS_COLORS[code] ?? DEFAULT_COLOR}
                fill={STATUS_COLORS[code] ?? DEFAULT_COLOR}
                fillOpacity={0.3}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            ))
          ) : (
            <Area
              type="monotone"
              dataKey="total"
              name="Errors"
              stroke="#ef4444"
              fill="#ef4444"
              fillOpacity={0.2}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
