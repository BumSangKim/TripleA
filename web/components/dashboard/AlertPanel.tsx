// components/dashboard/AlertPanel.tsx
"use client";
import { AlertItem } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useState } from "react";

interface AlertPanelProps {
  alerts: AlertItem[];
}

const LEVEL_STYLE: Record<string, { icon: string; text: string; bg: string }> = {
  danger:  { icon: "🚨", text: "text-red-400",    bg: "bg-red-500/10 border-red-500/20" },
  warning: { icon: "⚠️", text: "text-yellow-400", bg: "bg-yellow-500/10 border-yellow-500/20" },
  info:    { icon: "ℹ️", text: "text-blue-400",   bg: "bg-blue-500/10 border-blue-500/20" },
};

export default function AlertPanel({ alerts: initial }: AlertPanelProps) {
  const [alerts, setAlerts] = useState(initial);

  const handleRead = async (id: number) => {
    try {
      await api.markAlertRead(id);
      setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, is_read: true } : a)));
    } catch {
      // no-op
    }
  };

  const unread = alerts.filter((a) => !a.is_read).length;

  return (
    <Card
      title={`알림 / 이상 징후${unread > 0 ? ` (${unread})` : ""}`}
      extra={<a href="/alerts" className="text-blue-400 hover:underline">더보기 &gt;</a>}
    >
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {alerts.map((alert) => {
          const s = LEVEL_STYLE[alert.level] || LEVEL_STYLE.info;
          return (
            <div
              key={alert.id}
              className={cn(
                "flex items-start gap-2.5 p-2.5 rounded-lg border text-xs transition-opacity",
                s.bg,
                alert.is_read && "opacity-50"
              )}
            >
              <span className="shrink-0 mt-0.5">{s.icon}</span>
              <div className="flex-1 min-w-0">
                <p className={cn("font-medium", s.text)}>{alert.title}</p>
                {alert.message && <p className="text-slate-400 mt-0.5">{alert.message}</p>}
                <p className="text-slate-600 mt-1">{timeAgo(alert.created_at)}</p>
              </div>
              {!alert.is_read && (
                <button
                  onClick={() => handleRead(alert.id)}
                  className="text-slate-500 hover:text-white shrink-0 text-xs"
                  title="읽음 처리"
                >
                  ✕
                </button>
              )}
            </div>
          );
        })}
        {alerts.length === 0 && (
          <p className="text-center text-slate-500 text-sm py-4">알림이 없습니다.</p>
        )}
      </div>
    </Card>
  );
}

function timeAgo(dateStr: string): string {
  try {
    const d = new Date(dateStr.replace(" ", "T"));
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60)  return `${Math.round(diff)}초 전`;
    if (diff < 3600) return `${Math.round(diff / 60)}분 전`;
    if (diff < 86400) return `${Math.round(diff / 3600)}시간 전`;
    return `${Math.round(diff / 86400)}일 전`;
  } catch {
    return dateStr;
  }
}
