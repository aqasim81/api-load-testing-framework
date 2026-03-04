/** Shared chart styling constants — single source of truth for colors and styles. */

/** Chart color palette (matches CSS theme variables in index.css). */
export const CHART_COLORS = {
  green: "#22c55e",
  blue: "#3b82f6",
  red: "#ef4444",
  orange: "#f59e0b",
  purple: "#a855f7",
  cyan: "#06b6d4",
  gray: "#6b7280",
} as const;

/** Recharts Tooltip content style for dark theme. */
export const TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: "#1f2937",
  border: "1px solid #374151",
  borderRadius: "0.5rem",
  color: "#f3f4f6",
};

/** Standard axis stroke color. */
export const AXIS_STROKE = "#6b7280";

/** Standard axis font size. */
export const AXIS_FONT_SIZE = 12;

/** Standard CartesianGrid stroke color. */
export const GRID_STROKE = "#374151";
