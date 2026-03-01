import { cn } from "@/lib/utils";

interface ProgressBarProps {
  value: number; // 0-100
  label?: string;
  showValue?: boolean;
  color?: "blue" | "green" | "yellow" | "red" | "purple";
  size?: "sm" | "md";
}

const COLOR = {
  blue: "bg-blue-500",
  green: "bg-green-500",
  yellow: "bg-yellow-500",
  red: "bg-red-500",
  purple: "bg-purple-500",
};

export default function ProgressBar({
  value,
  label,
  showValue = true,
  color = "blue",
  size = "md",
}: ProgressBarProps) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div className="w-full">
      {(label || showValue) && (
        <div className="flex justify-between mb-1 text-xs text-zinc-400">
          {label && <span>{label}</span>}
          {showValue && <span>{pct}%</span>}
        </div>
      )}
      <div className={cn("w-full bg-zinc-700 rounded-full", size === "sm" ? "h-1.5" : "h-2")}>
        <div
          className={cn("rounded-full transition-all duration-500", COLOR[color], size === "sm" ? "h-1.5" : "h-2")}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
