import type { ConnectionStatus as Status } from "../types/metrics";

interface Props {
  status: Status;
}

const STATUS_CONFIG: Record<Status, { color: string; label: string }> = {
  connected: { color: "bg-green-500", label: "Connected" },
  connecting: { color: "bg-yellow-500", label: "Connecting..." },
  disconnected: { color: "bg-red-500", label: "Disconnected" },
};

export default function ConnectionStatus({ status }: Props) {
  const { color, label } = STATUS_CONFIG[status];
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${color}`} />
      <span className="text-gray-400">{label}</span>
    </div>
  );
}
