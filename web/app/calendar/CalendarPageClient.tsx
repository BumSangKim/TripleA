// app/calendar/CalendarPageClient.tsx
"use client";
import { useEffect, useState } from "react";
import type { CalendarEvent } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";
import { BASE_URL } from "@/lib/api";

const IMPORTANCE_STYLE: Record<string, string> = {
  high: "bg-red-500/20 text-red-400",
  medium: "bg-yellow-500/20 text-yellow-400",
  low: "bg-slate-700 text-slate-400",
};

function getDDays(dateStr: string) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(dateStr);
  target.setHours(0, 0, 0, 0);
  const diff = Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (diff === 0) return "D-Day";
  if (diff > 0) return `D-${diff}`;
  return `D+${Math.abs(diff)}`;
}

export default function CalendarPageClient() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<"list" | "week">("list");
  const [filterImp, setFilterImp] = useState("all");

  useEffect(() => {
    fetch(`${BASE_URL}/api/calendar/events`)
      .then((r) => r.json())
      .then(setEvents)
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = events.filter((e) => filterImp === "all" || e.importance === filterImp);
  const sorted = [...filtered].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

  // Group by date
  const grouped = sorted.reduce<Record<string, CalendarEvent[]>>((acc, evt) => {
    const d = evt.date.split("T")[0];
    (acc[d] = acc[d] ?? []).push(evt);
    return acc;
  }, {});

  const today = new Date().toISOString().split("T")[0];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">경제 캘린더</h1>
          <p className="text-sm text-slate-400">주요 경제 지표 발표 일정 및 이벤트</p>
        </div>
        <div className="flex items-center gap-2">
          {/* 보기 모드 토글 */}
          <div className="flex rounded-lg overflow-hidden border border-slate-600">
            {(["list", "week"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={cn(
                  "px-2.5 py-1 text-xs transition-colors",
                  viewMode === mode ? "bg-blue-600 text-white" : "bg-slate-700 text-slate-400 hover:bg-slate-600"
                )}
              >
                {mode === "list" ? "리스트" : "주간"}
              </button>
            ))}
          </div>
          {/* 중요도 필터 */}
          {["all", "high", "medium", "low"].map((imp) => (
            <button
              key={imp}
              onClick={() => setFilterImp(imp)}
              className={cn(
                "px-2.5 py-1 text-xs rounded-lg transition-colors",
                filterImp === imp ? "bg-blue-600 text-white" : "bg-slate-700 text-slate-400 hover:bg-slate-600"
              )}
            >
              {imp === "all" ? "전체" : imp === "high" ? "중요" : imp === "medium" ? "보통" : "낮음"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40 text-slate-500">로딩 중...</div>
      ) : sorted.length === 0 ? (
        <div className="flex items-center justify-center h-40 text-slate-500">일정이 없습니다.</div>
      ) : (
        <div className="space-y-4">
          {Object.entries(grouped).map(([date, dayEvents]) => {
            const isToday = date === today;
            const isPast = date < today;
            return (
              <div key={date}>
                <div className={cn(
                  "flex items-center gap-2 mb-2",
                  isToday ? "text-blue-400" : isPast ? "text-slate-600" : "text-slate-400"
                )}>
                  <div className={cn(
                    "w-2 h-2 rounded-full",
                    isToday ? "bg-blue-400" : isPast ? "bg-slate-700" : "bg-slate-500"
                  )} />
                  <span className="text-xs font-semibold">{date}</span>
                  {isToday && (
                    <span className="text-[10px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">오늘</span>
                  )}
                </div>
                <div className={cn(
                  "ml-4 space-y-2",
                  isPast && "opacity-50"
                )}>
                  {dayEvents.map((evt) => (
                    <Card key={evt.id}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className={cn(
                              "text-[10px] px-1.5 py-0.5 rounded font-medium",
                              IMPORTANCE_STYLE[evt.importance ?? "low"] ?? IMPORTANCE_STYLE.low
                            )}>
                              {evt.importance === "high" ? "중요" : evt.importance === "medium" ? "보통" : "낮음"}
                            </span>
                            {evt.country && (
                              <span className="text-[10px] text-slate-500">{evt.country}</span>
                            )}
                          </div>
                          <p className="text-sm font-semibold text-white">{evt.title ?? evt.event}</p>
                          {evt.actual != null && (
                            <p className="text-xs text-slate-400 mt-0.5">
                              실제: <span className="text-green-400">{evt.actual}</span>
                              {evt.forecast != null && <> · 예측: <span className="text-blue-400">{evt.forecast}</span></>}
                              {evt.previous != null && <> · 이전: <span className="text-slate-500">{evt.previous}</span></>}
                            </p>
                          )}
                        </div>
                        <div className="shrink-0 text-right">
                          <div className={cn(
                            "text-sm font-bold",
                            getDDays(date) === "D-Day"
                              ? "text-yellow-400"
                              : date > today
                              ? "text-blue-400"
                              : "text-slate-600"
                          )}>
                            {getDDays(date)}
                          </div>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
