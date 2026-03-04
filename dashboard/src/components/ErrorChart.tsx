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

const STATUS_COLORS: Record<string, string> = {
  "400": CHART_COLORS.orange,
  "401": "#f97316",
  "403": "#f97316",
  "404": CHART_COLORS.purple,
  "429": CHART_COLORS.cyan,
  "500": CHART_COLORS.red,
  "502": "#dc2626",
  "503": "#b91c1c",
};

const DEFAULT_COLOR = CHART_COLORS.gray;

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
          <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
          <XAxis
            dataKey="elapsed_seconds"
            tickFormatter={formatElapsed}
            stroke={AXIS_STROKE}
            fontSize={AXIS_FONT_SIZE}
          />
          <YAxis stroke={AXIS_STROKE} fontSize={AXIS_FONT_SIZE} allowDecimals={false} />
          <Tooltip
            contentStyle={TOOLTIP_STYLE}
            labelFormatter={formatElapsedLabel}
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
              stroke={CHART_COLORS.red}
              fill={CHART_COLORS.red}
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
