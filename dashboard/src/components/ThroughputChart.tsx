import {
  CartesianGrid,
  Line,
  LineChart,
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

export default function ThroughputChart({ snapshots }: Props) {
  return (
    <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Throughput (RPS)
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={snapshots}>
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
          />
          <Line
            type="monotone"
            dataKey="rps"
            name="RPS"
            stroke={CHART_COLORS.green}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
