import Dashboard from "./components/Dashboard";
import { useWebSocket } from "./hooks/useWebSocket";

function App() {
  const { snapshots, latestSnapshot, connectionStatus } = useWebSocket();
  const previousSnapshot =
    snapshots.length >= 2 ? snapshots[snapshots.length - 2] ?? null : null;

  return (
    <Dashboard
      snapshots={snapshots}
      latestSnapshot={latestSnapshot}
      previousSnapshot={previousSnapshot}
      connectionStatus={connectionStatus}
    />
  );
}

export default App;
