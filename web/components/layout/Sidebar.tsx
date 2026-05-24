// components/layout/Sidebar.tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { BASE_URL } from "@/lib/api";

const NAV_ITEMS = [
  { href: "/",           label: "대시보드",   icon: "⬛" },
  { href: "/macro",      label: "매크로",     icon: "📊" },
  { href: "/portfolio",  label: "포트폴리오", icon: "💼" },
  { href: "/accounts",   label: "계좌",       icon: "🏦" },
  { href: "/backtests",  label: "백테스트",   icon: "📈" },
  { href: "/orders",     label: "주문",       icon: "🧾" },
  { href: "/targets",    label: "목표관리",   icon: "🎯" },
  { href: "/reports",    label: "리포트",     icon: "📋" },
  { href: "/documents",  label: "자료실",     icon: "📁" },
  { href: "/calendar",   label: "캘린더",     icon: "📅" },
  { href: "/alerts",     label: "알림",       icon: "🔔", badge: true },
  { href: "/settings",   label: "설정",       icon: "⚙️" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    const fetchUnread = () => {
      fetch(`${BASE_URL}/api/alerts/recent?limit=100`)
        .then((r) => r.json())
        .then((alerts: { is_read?: boolean }[]) => {
          setUnreadCount(alerts.filter((a) => !a.is_read).length);
        })
        .catch(() => {});
    };
    fetchUnread();
    const timer = setInterval(fetchUnread, 60_000);
    return () => clearInterval(timer);
  }, []);

  return (
    <aside className="w-56 bg-slate-900 border-r border-slate-700 flex flex-col shrink-0 h-screen sticky top-0">
      {/* Logo */}
      <div className="flex items-center gap-2 px-5 py-5 border-b border-slate-700">
        <div className="w-7 h-7 bg-blue-600 rounded-md flex items-center justify-center text-white text-xs font-bold">
          AAA
        </div>
        <span className="text-white font-bold text-base tracking-tight">TripleA</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          const showBadge = item.badge && unreadCount > 0;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-5 py-2.5 text-sm transition-colors",
                active
                  ? "bg-blue-600/20 text-blue-400 border-r-2 border-blue-500"
                  : "text-slate-400 hover:text-white hover:bg-slate-800"
              )}
            >
              <span className="text-base leading-none">{item.icon}</span>
              <span className="flex-1">{item.label}</span>
              {showBadge && (
                <span className="min-w-[18px] h-[18px] px-1 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Version */}
      <div className="px-5 py-3 border-t border-slate-700">
        <p className="text-[10px] text-slate-600">v1.3.7</p>
        <div className="flex items-center gap-1.5 mt-1">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span className="text-[10px] text-slate-500">시스템 정상</span>
        </div>
      </div>
    </aside>
  );
}
