import type { ConnectionStatus, SnapshotData } from "../types/metrics";
import { formatElapsed } from "../utils/format";
import ConcurrencyChart from "./ConcurrencyChart";
import ConnectionStatusIndicator from "./ConnectionStatus";
import ErrorChart from "./ErrorChart";
import LatencyChart from "./LatencyChart";
import MetricsPanel from "./MetricsPanel";
import StatusTable from "./StatusTable";
import ThroughputChart from "./ThroughputChart";

interface Props {
  snapshots: SnapshotData[];
  latestSnapshot: SnapshotData | null;
  previousSnapshot: SnapshotData | null;
  connectionStatus: ConnectionStatus;
}

export default function Dashboard({
  snapshots,
  latestSnapshot,
  previousSnapshot,
  connectionStatus,
}: Props) {
  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold text-gray-100">
            LoadForge Dashboard
          </h1>
          {latestSnapshot && (
            <span className="text-sm text-gray-500">
              {formatElapsed(latestSnapshot.elapsed_seconds)} elapsed
            </span>
          )}
        </div>
        <ConnectionStatusIndicator status={connectionStatus} />
      </div>

      {/* Metric Cards */}
      <MetricsPanel
        latestSnapshot={latestSnapshot}
        previousSnapshot={previousSnapshot}
      />

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ThroughputChart snapshots={snapshots} />
        <LatencyChart snapshots={snapshots} />
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <ConcurrencyChart snapshots={snapshots} />
        <ErrorChart snapshots={snapshots} />
      </div>

      {/* Endpoint Table */}
      <StatusTable endpoints={latestSnapshot?.endpoints ?? []} />
    </div>
  );
}
