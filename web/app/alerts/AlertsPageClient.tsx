// app/alerts/AlertsPageClient.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AlertItem } from "@/lib/types";
import Card from "@/components/ui/Card";
import StatusChip from "@/components/ui/StatusChip";
import { cn } from "@/lib/utils";

const LEVEL_FILTER = ["전체", "danger", "warning", "info"];
const LEVEL_LABEL: Record<string, string> = { danger: "위험", warning: "경고", info: "정보" };

export default function AlertsPageClient() {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("전체");
  const [showRead, setShowRead] = useState(false);

  const fetchAlerts = () => {
    setLoading(true);
    api.getAlerts(100)
      .then(setAlerts)
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  const handleMarkRead = async (id: number) => {
    await api.markAlertRead(id);
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, is_read: true } : a)));
  };

  const handleMarkAllRead = async () => {
    const unread = alerts.filter((a) => !a.is_read);
    await Promise.all(unread.map((a) => api.markAlertRead(a.id)));
    setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })));
  };

  const filtered = alerts.filter((a) => {
    if (!showRead && a.is_read) return false;
    if (filter !== "전체" && a.level !== filter) return false;
    return true;
  });

  const unreadCount = alerts.filter((a) => !a.is_read).length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">알림 / 이상 징후</h1>
          <p className="text-sm text-slate-400">
            읽지 않은 알림 <span className="text-yellow-400 font-semibold">{unreadCount}개</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowRead(!showRead)}
            className={cn(
              "px-3 py-1.5 text-xs rounded-lg transition-colors",
              showRead ? "bg-slate-600 text-white" : "bg-slate-700 text-slate-400 hover:bg-slate-600"
            )}
          >
            {showRead ? "읽음 숨기기" : "읽음 표시"}
          </button>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-lg transition-colors"
            >
              모두 읽음
            </button>
          )}
        </div>
      </div>

      {/* 필터 탭 */}
      <div className="flex gap-2">
        {LEVEL_FILTER.map((l) => (
          <button
            key={l}
            onClick={() => setFilter(l)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              filter === l
                ? "bg-blue-600 text-white"
                : "bg-slate-700 text-slate-400 hover:bg-slate-600"
            )}
          >
            {LEVEL_LABEL[l] ?? l}
            {l !== "전체" && (
              <span className="ml-1 text-slate-500">
                ({alerts.filter((a) => a.level === l).length})
              </span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40 text-slate-500">로딩 중...</div>
      ) : (
        <Card>
          <div className="divide-y divide-slate-700">
            {filtered.length === 0 && (
              <div className="py-10 text-center text-slate-500">알림이 없습니다.</div>
            )}
            {filtered.map((alert) => (
              <div
                key={alert.id}
                className={cn(
                  "flex items-start gap-3 py-3 px-2 rounded-lg transition-colors",
                  alert.is_read ? "opacity-50" : "hover:bg-slate-700/30"
                )}
              >
                <div className={cn(
                  "w-2 h-2 rounded-full mt-1.5 shrink-0",
                  alert.level === "danger" ? "bg-red-500" :
                  alert.level === "warning" ? "bg-yellow-500" : "bg-blue-400"
                )} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <StatusChip status={alert.level as any} />
                    <span className="text-xs text-slate-500">{alert.category}</span>
                  </div>
                  <p className="text-sm font-medium text-white">{alert.title}</p>
                  {alert.message && (
                    <p className="text-xs text-slate-400 mt-0.5">{alert.message}</p>
                  )}
                  <p className="text-[10px] text-slate-600 mt-1">{alert.created_at}</p>
                </div>
                {!alert.is_read && (
                  <button
                    onClick={() => handleMarkRead(alert.id)}
                    className="shrink-0 px-2 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-slate-400 rounded transition-colors"
                  >
                    읽음
                  </button>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
