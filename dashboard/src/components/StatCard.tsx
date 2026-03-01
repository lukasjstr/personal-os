import { cn } from "@/lib/utils";

interface StatCardProps {
  emoji: string;
  label: string;
  value: string | number;
  sub?: string;
  color?: "default" | "green" | "blue" | "yellow" | "red";
}

const COLOR_MAP = {
  default: "bg-zinc-800 border-zinc-700",
  green: "bg-green-950 border-green-800",
  blue: "bg-blue-950 border-blue-800",
  yellow: "bg-yellow-950 border-yellow-800",
  red: "bg-red-950 border-red-800",
};

const VALUE_COLOR = {
  default: "text-white",
  green: "text-green-400",
  blue: "text-blue-400",
  yellow: "text-yellow-400",
  red: "text-red-400",
};

export default function StatCard({ emoji, label, value, sub, color = "default" }: StatCardProps) {
  return (
    <div className={cn("rounded-xl border p-4", COLOR_MAP[color])}>
      <div className="text-2xl mb-2">{emoji}</div>
      <div className={cn("text-2xl font-bold", VALUE_COLOR[color])}>{value}</div>
      <div className="text-zinc-400 text-sm mt-0.5">{label}</div>
      {sub && <div className="text-zinc-500 text-xs mt-1">{sub}</div>}
    </div>
  );
}
