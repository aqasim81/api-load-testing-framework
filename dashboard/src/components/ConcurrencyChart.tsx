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

export default function ConcurrencyChart({ snapshots }: Props) {
  return (
    <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Active Users
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={snapshots}>
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
          <Area
            type="monotone"
            dataKey="active_users"
            name="Active Users"
            stroke={CHART_COLORS.blue}
            fill={CHART_COLORS.blue}
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
