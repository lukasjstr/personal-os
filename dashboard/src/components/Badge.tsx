import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "green" | "blue" | "yellow" | "red" | "purple" | "outline";
}

const VARIANTS = {
  default: "bg-zinc-700 text-zinc-300",
  green: "bg-green-900 text-green-400",
  blue: "bg-blue-900 text-blue-400",
  yellow: "bg-yellow-900 text-yellow-400",
  red: "bg-red-900 text-red-400",
  purple: "bg-purple-900 text-purple-400",
  outline: "border border-zinc-600 text-zinc-400",
};

export default function Badge({ children, variant = "default" }: BadgeProps) {
  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium", VARIANTS[variant])}>
      {children}
    </span>
  );
}
