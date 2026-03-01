"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Target,
  CheckSquare,
  ScrollText,
  RefreshCw,
  Calendar,
  Brain,
  FileText,
  Settings,
  ShoppingCart,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard, emoji: "🏠" },
  { href: "/objectives", label: "Objectives", icon: Target, emoji: "🎯" },
  { href: "/tasks", label: "Tasks", icon: CheckSquare, emoji: "✅" },
  { href: "/logs", label: "Logs", icon: ScrollText, emoji: "📊" },
  { href: "/routines", label: "Routinen", icon: RefreshCw, emoji: "🔄" },
  { href: "/calendar", label: "Kalender", icon: Calendar, emoji: "📅" },
  { href: "/brain-dumps", label: "Brain Dumps", icon: Brain, emoji: "🧠" },
  { href: "/shopping", label: "Einkauf", icon: ShoppingCart, emoji: "🛒" },
  { href: "/docs", label: "Dokumente", icon: FileText, emoji: "📄" },
  { href: "/settings", label: "Einstellungen", icon: Settings, emoji: "⚙️" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-56 bg-zinc-900 border-r border-zinc-800 flex flex-col z-30">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🤖</span>
          <div>
            <div className="font-bold text-white text-sm">Personal OS</div>
            <div className="text-zinc-500 text-xs">Dashboard</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 px-2">
        {NAV.map((item) => {
          const active =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg mb-0.5 text-sm transition-colors",
                active
                  ? "bg-blue-600 text-white"
                  : "text-zinc-400 hover:text-white hover:bg-zinc-800"
              )}
            >
              <item.icon size={16} className="shrink-0" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-zinc-800">
        <div className="text-zinc-600 text-xs">v2.0 · Phase 2</div>
      </div>
    </aside>
  );
}
