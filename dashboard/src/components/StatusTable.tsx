import { useMemo, useState } from "react";
import type { EndpointSnapshot } from "../types/metrics";

interface Props {
  endpoints: EndpointSnapshot[];
}

type SortKey = keyof EndpointSnapshot;
type SortDir = "asc" | "desc";

const COLUMNS: { key: SortKey; label: string; format: (v: number) => string }[] = [
  { key: "rps", label: "RPS", format: (v) => v.toFixed(1) },
  { key: "p50", label: "p50", format: (v) => `${v.toFixed(1)}ms` },
  { key: "p95", label: "p95", format: (v) => `${v.toFixed(1)}ms` },
  { key: "p99", label: "p99", format: (v) => `${v.toFixed(1)}ms` },
  { key: "error_count", label: "Errors", format: (v) => v.toLocaleString() },
  {
    key: "error_rate",
    label: "Error Rate",
    format: (v) => `${(v * 100).toFixed(2)}%`,
  },
];

function latencyColor(ms: number): string {
  if (ms < 100) return "text-green-400";
  if (ms < 500) return "text-yellow-400";
  return "text-red-400";
}

export default function StatusTable({ endpoints }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("rps");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    return [...endpoints].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (typeof av === "number" && typeof bv === "number") {
        return sortDir === "asc" ? av - bv : bv - av;
      }
      const as = String(av);
      const bs = String(bv);
      return sortDir === "asc" ? as.localeCompare(bs) : bs.localeCompare(as);
    });
  }, [endpoints, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const sortIndicator = (key: SortKey) => {
    if (key !== sortKey) return null;
    return sortDir === "asc" ? " \u25b2" : " \u25bc";
  };

  if (endpoints.length === 0) {
    return (
      <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-3">
          Per-Endpoint Metrics
        </h3>
        <p className="text-sm text-gray-600">Waiting for data...</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-gray-900 border border-gray-800 p-4">
      <h3 className="text-sm font-medium text-gray-400 mb-3">
        Per-Endpoint Metrics
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-left">
              <th
                className="pb-2 pr-4 text-gray-500 font-medium cursor-pointer hover:text-gray-300"
                onClick={() => handleSort("name")}
              >
                Endpoint{sortIndicator("name")}
              </th>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className="pb-2 px-3 text-gray-500 font-medium cursor-pointer hover:text-gray-300 text-right"
                  onClick={() => handleSort(col.key)}
                >
                  {col.label}{sortIndicator(col.key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((ep) => (
              <tr
                key={ep.name}
                className="border-b border-gray-800/50 hover:bg-gray-800/30"
              >
                <td className="py-2 pr-4 font-mono text-gray-300">
                  {ep.name}
                </td>
                {COLUMNS.map((col) => {
                  const value = ep[col.key];
                  const numValue = typeof value === "number" ? value : 0;
                  const isLatency = ["p50", "p95", "p99"].includes(col.key);
                  const colorClass = isLatency
                    ? latencyColor(numValue)
                    : "text-gray-300";
                  return (
                    <td
                      key={col.key}
                      className={`py-2 px-3 text-right font-mono ${colorClass}`}
                    >
                      {col.format(numValue)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
