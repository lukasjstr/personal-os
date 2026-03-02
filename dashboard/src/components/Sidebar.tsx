"use client";

import { useState } from "react";
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
  Dumbbell,
  Trophy,
  BookOpen,
  Menu,
  X,
} from "lucide-react";
import { useDashboard } from "@/hooks/useApi";
import XPBar from "./XPBar";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/objectives", label: "Objectives", icon: Target },
  { href: "/tasks", label: "Tasks", icon: CheckSquare, badge: "open_tasks" },
  { href: "/logs", label: "Logs", icon: ScrollText },
  { href: "/routines", label: "Routinen", icon: RefreshCw },
  { href: "/fitness", label: "Fitness", icon: Dumbbell },
  { href: "/calendar", label: "Kalender", icon: Calendar },
  { href: "/brain-dumps", label: "Brain Dumps", icon: Brain },
  { href: "/shopping", label: "Einkauf", icon: ShoppingCart, badge: "shopping_items" },
  { href: "/achievements", label: "Erfolge", icon: Trophy },
  { href: "/reflection", label: "Reflexion", icon: BookOpen },
  { href: "/docs", label: "Dokumente", icon: FileText },
  { href: "/settings", label: "Einstellungen", icon: Settings },
];

export default function Sidebar() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const { data: dash } = useDashboard();
  const stats = dash?.stats;

  const getBadge = (key: string): number => {
    if (!stats) return 0;
    if (key === "open_tasks") return stats.open_tasks ?? 0;
    if (key === "shopping_items") return stats.shopping_items ?? 0;
    return 0;
  };

  return (
    <>
      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-zinc-900 border-b border-zinc-800 flex items-center px-4 z-40">
        <button
          onClick={() => setOpen(true)}
          className="p-2 -ml-1 text-zinc-400 hover:text-white transition-colors"
          aria-label="Menü öffnen"
        >
          <Menu size={22} />
        </button>
        <span className="ml-2 font-bold text-white text-sm">Personal OS</span>
        <span className="ml-1.5 text-zinc-500 text-xs">v3</span>
        {stats && stats.level != null && (
          <span className="ml-auto text-xs font-bold bg-gradient-to-br from-yellow-500 to-orange-600 text-white px-2 py-0.5 rounded-full">
            Lv.{stats.level}
          </span>
        )}
      </div>

      {/* Backdrop (mobile) */}
      {open && (
        <div
          className="md:hidden fixed inset-0 bg-black/60 z-40"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed left-0 top-0 h-screen w-64 md:w-56 bg-zinc-900 border-r border-zinc-800 flex flex-col z-50",
          "transition-transform duration-200 ease-in-out",
          open ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
      >
        {/* Mobile header inside sidebar */}
        <div className="md:hidden flex items-center justify-between px-5 py-4 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <div>
              <div className="font-bold text-white text-sm">Personal OS</div>
              <div className="text-zinc-500 text-xs">Dashboard v3</div>
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="p-1.5 text-zinc-400 hover:text-white transition-colors"
            aria-label="Menü schließen"
          >
            <X size={18} />
          </button>
        </div>

        {/* Logo (desktop only) */}
        <div className="hidden md:block px-5 py-4 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <div className="flex-1 min-w-0">
              <div className="font-bold text-white text-sm">Personal OS</div>
              <div className="text-zinc-500 text-xs">Dashboard v3</div>
            </div>
            {stats && stats.level != null && (
              <span className="text-xs font-bold bg-gradient-to-br from-yellow-500 to-orange-600 text-white px-2 py-0.5 rounded-full shrink-0">
                Lv.{stats.level}
              </span>
            )}
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const badgeCount = item.badge ? getBadge(item.badge) : 0;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg mb-0.5 text-sm transition-colors min-h-[44px]",
                  active
                    ? "bg-blue-600 text-white"
                    : "text-zinc-400 hover:text-white hover:bg-zinc-800"
                )}
              >
                <item.icon size={16} className="shrink-0" />
                <span className="flex-1">{item.label}</span>
                {badgeCount > 0 && (
                  <span
                    className={cn(
                      "text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0",
                      active
                        ? "bg-white/20 text-white"
                        : item.badge === "open_tasks" && badgeCount > 15
                        ? "bg-red-900/60 text-red-400"
                        : item.badge === "open_tasks" && badgeCount > 10
                        ? "bg-yellow-900/60 text-yellow-400"
                        : "bg-zinc-700 text-zinc-300"
                    )}
                  >
                    {badgeCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* XP Footer */}
        <div className="border-t border-zinc-800">
          {stats && stats.total_xp !== undefined ? (
            <XPBar
              level={stats.level}
              levelTitle={stats.level_title}
              totalXp={stats.total_xp}
              xpProgress={stats.xp_progress}
              xpToNext={stats.xp_to_next}
              compact
            />
          ) : (
            <div className="px-4 py-3">
              <div className="text-zinc-600 text-xs">v3.0 · Phase 3</div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
