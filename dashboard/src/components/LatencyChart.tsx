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
import {
  AXIS_FONT_SIZE,
  AXIS_STROKE,
  CHART_COLORS,
  GRID_STROKE,
  TOOLTIP_STYLE,
} from "../utils/chartTheme";
import { formatElapsed, formatElapsedLabel } from "../utils/format";

interface Props {
  snapshots: SnapshotData[];
}

interface ChartPoint {
  elapsed_seconds: number;
  p50: number;
  p95: number;
  p99: number;
}

export default function LatencyChart({ snapshots }: Props) {
  const data: ChartPoint[] = useMemo(
    () =>
      snapshots.map((s) => ({
        elapsed_seconds: s.elapsed_seconds,
        p50: s.latency.p50,
        p95: s.latency.p95,
        p99: s.latency.p99,
      })),
    [snapshots],
  );

  return (
    <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Latency Percentiles (ms)
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
          <XAxis
            dataKey="elapsed_seconds"
            tickFormatter={formatElapsed}
            stroke={AXIS_STROKE}
            fontSize={AXIS_FONT_SIZE}
          />
          <YAxis stroke={AXIS_STROKE} fontSize={AXIS_FONT_SIZE} />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelFormatter={formatElapsedLabel}
            formatter={(value: number) => [`${value.toFixed(1)}ms`]}
          />
          <Area
            type="monotone"
            dataKey="p99"
            name="p99"
            stroke={CHART_COLORS.red}
            fill={CHART_COLORS.red}
            fillOpacity={0.15}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="p95"
            name="p95"
            stroke={CHART_COLORS.orange}
            fill={CHART_COLORS.orange}
            fillOpacity={0.2}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="p50"
            name="p50"
            stroke={CHART_COLORS.green}
            fill={CHART_COLORS.green}
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
