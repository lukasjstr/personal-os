"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Target,
  RefreshCw,
  Calendar,
  Brain,
  Settings,
  ShoppingCart,
  Dumbbell,
  Trophy,
  BookOpen,
  Lightbulb,
  Menu,
  X,
  Zap,
  BarChart3,
  Users,
  Kanban,
  GraduationCap,
  DollarSign,
  ChevronDown,
  ChevronRight,
  User,
  CalendarDays,
  Bell,
  BellOff,
} from "lucide-react";
import { useDashboard } from "@/hooks/useApi";
import XPBar from "./XPBar";

// ─── Nav structure ────────────────────────────────────────────────────────────

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
  emoji?: string;
  badge?: string;
}

interface NavSection {
  id: string;
  title: string;
  items: NavItem[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    id: "heute",
    title: "HEUTE",
    items: [
      { href: "/cockpit", label: "Cockpit", icon: Target, emoji: "🎯" },
      { href: "/kanban", label: "Kanban", icon: Kanban, emoji: "📋" },
      { href: "/calendar", label: "Kalender", icon: Calendar, emoji: "📅" },
    ],
  },
  {
    id: "leben",
    title: "LEBEN",
    items: [
      { href: "/mission", label: "Mission", icon: Target, emoji: "🪨" },
      { href: "/objectives", label: "Ziele & KRs", icon: Target, emoji: "🎯" },
      { href: "/routines", label: "Routinen", icon: RefreshCw, emoji: "🔄" },
      { href: "/weekly", label: "Wochenziele", icon: CalendarDays, emoji: "📖" },
      { href: "/goals/coach", label: "Ziel-Coach", icon: Zap, emoji: "✨" },
    ],
  },
  {
    id: "wachstum",
    title: "WACHSTUM",
    items: [
      { href: "/learning", label: "Lernen", icon: GraduationCap, emoji: "🧠" },
      { href: "/brain-dumps", label: "Brain Dumps", icon: Brain, emoji: "💭" },
      { href: "/reflection", label: "Reflektionen", icon: BookOpen, emoji: "🪞" },
    ],
  },
  {
    id: "gesundheit",
    title: "GESUNDHEIT",
    items: [
      { href: "/fitness", label: "Fitness", icon: Dumbbell, emoji: "🏋️" },
      { href: "/supplements", label: "Supplements", icon: Zap, emoji: "💊" },
      { href: "/shopping", label: "Einkaufen", icon: ShoppingCart, emoji: "🛒", badge: "shopping_items" },
    ],
  },
  {
    id: "finanzen",
    title: "FINANZEN",
    items: [
      { href: "/finance", label: "Übersicht", icon: DollarSign, emoji: "💰" },
    ],
  },
  {
    id: "beziehungen",
    title: "BEZIEHUNGEN",
    items: [
      { href: "/relationships", label: "Kontakte", icon: Users, emoji: "👥" },
    ],
  },
  {
    id: "system",
    title: "SYSTEM",
    items: [
      { href: "/automation", label: "Automatisierung", icon: Zap, emoji: "⚡" },
      { href: "/review/quarterly", label: "Q-Review (V3)", icon: BarChart3, emoji: "📊" },
      { href: "/quarterly", label: "Quartals-Review", icon: BarChart3, emoji: "📈" },
      { href: "/achievements", label: "Achievements", icon: Trophy, emoji: "🎮" },
      { href: "/profile", label: "Lebens-Profil", icon: User, emoji: "🧬" },
      { href: "/suggestions", label: "AI Insights", icon: Lightbulb, emoji: "💡" },
      { href: "/settings", label: "Einstellungen", icon: Settings, emoji: "⚙️" },
    ],
  },
];

// Bottom nav items for mobile (5 most important)
const MOBILE_BOTTOM_NAV: NavItem[] = [
  { href: "/cockpit", label: "Cockpit", icon: Target, emoji: "🎯" },
  { href: "/kanban", label: "Kanban", icon: Kanban, emoji: "📋" },
  { href: "/mission", label: "Mission", icon: Target, emoji: "🪨" },
  { href: "/objectives", label: "Ziele", icon: Target, emoji: "🎯" },
  { href: "/settings", label: "Settings", icon: Settings, emoji: "⚙️" },
];

// ─── Component ────────────────────────────────────────────────────────────────

function NotificationBell() {
  const [pushEnabled, setPushEnabled] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if ("Notification" in window) {
      setPushEnabled(Notification.permission === "granted");
    }
  }, []);

  const togglePush = async () => {
    if (loading) return;
    setLoading(true);
    try {
      if (pushEnabled) {
        // Can't programmatically revoke — tell user
        setPushEnabled(false);
        return;
      }
      const permission = await Notification.requestPermission();
      if (permission === "granted") {
        setPushEnabled(true);
        // Subscribe via service worker
        const reg = await navigator.serviceWorker.ready;
        const { subscribeToPush } = await import("./PWARegister");
        await subscribeToPush(reg);
      }
    } catch (err) {
      console.warn("Push toggle failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={togglePush}
      className="p-1 rounded-md hover:bg-zinc-700 transition-colors shrink-0"
      title={pushEnabled ? "Push aktiv" : "Push aktivieren"}
    >
      {pushEnabled ? (
        <Bell className="h-4 w-4 text-indigo-400" />
      ) : (
        <BellOff className="h-4 w-4 text-zinc-500" />
      )}
    </button>
  );
}

export default function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const pathname = usePathname();
  const { data: dash } = useDashboard();
  const stats = dash?.stats;

  // Load collapsed state from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem("sidebar_collapsed");
      if (stored) setCollapsed(JSON.parse(stored));
    } catch {}
  }, []);

  const toggleSection = (id: string) => {
    setCollapsed((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      try {
        localStorage.setItem("sidebar_collapsed", JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  const getBadge = (key: string): number => {
    if (!stats) return 0;
    if (key === "shopping_items") return stats.shopping_items ?? 0;
    return 0;
  };

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="px-5 py-4 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🤖</span>
          <div className="flex-1 min-w-0">
            <div className="font-bold text-white text-sm">Personal OS</div>
            <div className="text-zinc-500 text-xs">Dashboard v3</div>
          </div>
          <NotificationBell />
          {stats && stats.level != null && (
            <span className="text-xs font-bold bg-gradient-to-br from-yellow-500 to-orange-600 text-white px-2 py-0.5 rounded-full shrink-0">
              Lv.{stats.level}
            </span>
          )}
        </div>
      </div>

      {/* Nav Sections */}
      <nav className="flex-1 overflow-y-auto py-2 px-2">
        {NAV_SECTIONS.map((section) => {
          const isCollapsed = collapsed[section.id] ?? false;
          return (
            <div key={section.id} className="mb-1">
              {/* Section Header */}
              <button
                onClick={() => toggleSection(section.id)}
                className="w-full flex items-center justify-between px-3 py-1.5 text-zinc-500 hover:text-zinc-400 transition-colors group"
              >
                <span className="text-[10px] font-semibold tracking-widest uppercase">
                  {section.title}
                </span>
                {isCollapsed ? (
                  <ChevronRight size={12} className="opacity-60 group-hover:opacity-100" />
                ) : (
                  <ChevronDown size={12} className="opacity-60 group-hover:opacity-100" />
                )}
              </button>

              {/* Section Items */}
              {!isCollapsed && (
                <div className="mb-1">
                  {section.items.map((item) => {
                    const active = isActive(item.href);
                    const badgeCount = item.badge ? getBadge(item.badge) : 0;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={() => setMobileOpen(false)}
                        className={cn(
                          "flex items-center gap-2.5 px-3 py-2 rounded-lg mb-0.5 text-sm transition-colors min-h-[38px]",
                          active
                            ? "bg-indigo-600 text-white"
                            : "text-zinc-400 hover:text-white hover:bg-zinc-800"
                        )}
                      >
                        <span className="text-base w-5 text-center shrink-0 leading-none">
                          {item.emoji}
                        </span>
                        <span className="flex-1 text-[13px]">{item.label}</span>
                        {badgeCount > 0 && (
                          <span
                            className={cn(
                              "text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0",
                              active ? "bg-white/20 text-white" : "bg-zinc-700 text-zinc-300"
                            )}
                          >
                            {badgeCount}
                          </span>
                        )}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
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
    </>
  );

  return (
    <>
      {/* ── Mobile: top bar ── */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-14 bg-zinc-900 border-b border-zinc-800 flex items-center px-4 z-40">
        <button
          onClick={() => setMobileOpen(true)}
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

      {/* ── Mobile: slide-in drawer backdrop ── */}
      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/60 z-40"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ── Desktop sidebar / Mobile drawer ── */}
      <aside
        className={cn(
          "fixed left-0 top-0 h-screen w-64 md:w-56 bg-zinc-900 border-r border-zinc-800 flex flex-col z-50",
          "transition-transform duration-200 ease-in-out",
          // On mobile: slide out unless mobileOpen; on desktop: always visible
          "md:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        )}
      >
        {/* Mobile: close button row */}
        <div className="md:hidden flex items-center justify-between px-5 py-4 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <span className="text-2xl">🤖</span>
            <div>
              <div className="font-bold text-white text-sm">Personal OS</div>
              <div className="text-zinc-500 text-xs">Dashboard v3</div>
            </div>
          </div>
          <button
            onClick={() => setMobileOpen(false)}
            className="p-1.5 text-zinc-400 hover:text-white transition-colors"
            aria-label="Menü schließen"
          >
            <X size={18} />
          </button>
        </div>

        {/* Desktop logo + nav */}
        <div className="hidden md:flex md:flex-col flex-1 overflow-hidden">
          <SidebarContent />
        </div>

        {/* Mobile nav content (below close button) */}
        <div className="md:hidden flex flex-col flex-1 overflow-hidden">
          <nav className="flex-1 overflow-y-auto py-2 px-2">
            {NAV_SECTIONS.map((section) => {
              const isCollapsed = collapsed[section.id] ?? false;
              return (
                <div key={section.id} className="mb-1">
                  <button
                    onClick={() => toggleSection(section.id)}
                    className="w-full flex items-center justify-between px-3 py-1.5 text-zinc-500 hover:text-zinc-400 transition-colors group"
                  >
                    <span className="text-[10px] font-semibold tracking-widest uppercase">
                      {section.title}
                    </span>
                    {isCollapsed ? (
                      <ChevronRight size={12} className="opacity-60 group-hover:opacity-100" />
                    ) : (
                      <ChevronDown size={12} className="opacity-60 group-hover:opacity-100" />
                    )}
                  </button>
                  {!isCollapsed && (
                    <div className="mb-1">
                      {section.items.map((item) => {
                        const active = isActive(item.href);
                        const badgeCount = item.badge ? getBadge(item.badge) : 0;
                        return (
                          <Link
                            key={item.href}
                            href={item.href}
                            onClick={() => setMobileOpen(false)}
                            className={cn(
                              "flex items-center gap-2.5 px-3 py-2 rounded-lg mb-0.5 text-sm transition-colors min-h-[44px]",
                              active
                                ? "bg-indigo-600 text-white"
                                : "text-zinc-400 hover:text-white hover:bg-zinc-800"
                            )}
                          >
                            <span className="text-base w-5 text-center shrink-0 leading-none">
                              {item.emoji}
                            </span>
                            <span className="flex-1 text-[13px]">{item.label}</span>
                            {badgeCount > 0 && (
                              <span className="text-xs px-1.5 py-0.5 rounded-full font-medium shrink-0 bg-zinc-700 text-zinc-300">
                                {badgeCount}
                              </span>
                            )}
                          </Link>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </nav>
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
        </div>
      </aside>

      {/* ── Mobile: bottom navigation bar ── */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 h-16 bg-zinc-900 border-t border-zinc-800 flex items-center justify-around z-30 px-2">
        {MOBILE_BOTTOM_NAV.map((item) => {
          const active = isActive(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center gap-0.5 px-3 py-1 rounded-lg transition-colors min-w-[56px]",
                active ? "text-indigo-400" : "text-zinc-500 hover:text-zinc-300"
              )}
            >
              <span className="text-xl leading-none">{item.emoji}</span>
              <span className="text-[10px] font-medium">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </>
  );
}
