/** Shared formatting utilities for the dashboard. */

/** Format elapsed seconds as a human-readable string (e.g., "2m 15s"). */
export function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

/** Tooltip label formatter for Recharts time axes. */
export function formatElapsedLabel(v: number): string {
  return `${formatElapsed(v)} elapsed`;
}
