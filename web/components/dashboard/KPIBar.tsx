// components/dashboard/KPIBar.tsx
"use client";
import { useEffect, useState } from "react";
import { KPISummary, TargetItem } from "@/lib/types";
import { formatKRW } from "@/lib/utils";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface KPIBarProps {
  kpi: KPISummary;
  targets?: TargetItem[];
}

/** 목표달성률: normal인 항목 비율 × 100 */
function computeAchievementRate(targets: TargetItem[]): number {
  if (!targets.length) return 0;
  const normal = targets.filter((t) => t.level === "normal").length;
  return Math.round((normal / targets.length) * 100 * 10) / 10;
}

export default function KPIBar({ kpi, targets = [] }: KPIBarProps) {
  const [syncOk, setSyncOk] = useState<boolean | null>(null);
  const [syncTime, setSyncTime] = useState<string>("확인 중...");

  const achievementRate = computeAchievementRate(targets);

  useEffect(() => {
    fetch(`${BASE_URL}/api/system/status`)
      .then((r) => r.json())
      .then((d) => {
        setSyncOk(d.pipeline_status === "정상");
        if (d.macro_last_update) {
          const dt = new Date(d.macro_last_update);
          setSyncTime(dt.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }));
        } else {
          setSyncTime("데이터 없음");
        }
      })
      .catch(() => { setSyncOk(false); setSyncTime("API 오류"); });
  }, []);

  const riskColor = {
    "낮음": "text-green-400",
    "보통": "text-yellow-400",
    "높음": "text-red-400",
  }[kpi.riskLevel] || "text-slate-400";

  const profitColor = kpi.todayProfit >= 0 ? "text-red-400" : "text-blue-400";
  const profitPrefix = kpi.todayProfit >= 0 ? "▲" : "▼";

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {/* 매크로 종합 점수 */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
        <p className="text-xs text-slate-400 mb-1">매크로 종합 점수</p>
        <div className="flex items-end gap-1">
          <span className="text-3xl font-bold text-white">
            {kpi.macroScore != null ? kpi.macroScore : "—"}
          </span>
          <span className="text-slate-500 text-sm mb-0.5">/ 100</span>
        </div>
        <div className="mt-2 h-1.5 bg-slate-700 rounded-full">
          <div
            className={`h-full rounded-full ${
              kpi.macroScore == null ? "bg-slate-600"
              : kpi.macroScore >= 70 ? "bg-blue-500"
              : kpi.macroScore >= 50 ? "bg-yellow-500"
              : "bg-red-500"
            }`}
            style={{ width: `${kpi.macroScore ?? 0}%` }}
          />
        </div>
        <p className="text-[10px] text-slate-500 mt-1">
          {kpi.macroScore != null
            ? kpi.macroScore >= 70 ? "건전한 시장" : kpi.macroScore >= 50 ? "주의 필요" : "리스크 주의"
            : "데이터 없음"}
        </p>
      </div>

      {/* 총자산 */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
        <p className="text-xs text-slate-400 mb-1">총자산</p>
        <p className="text-xl font-bold text-white leading-tight">{formatKRW(kpi.totalAssets)}</p>
        <p className={`text-[10px] mt-1 ${kpi.todayProfitRate >= 0 ? "text-red-400" : "text-blue-400"}`}>
          {kpi.todayProfitRate >= 0 ? "▲" : "▼"} {Math.abs(kpi.todayProfitRate).toFixed(2)}% 전일 대비
        </p>
      </div>

      {/* 일간 손익 */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
        <p className="text-xs text-slate-400 mb-1">일간 손익</p>
        <p className={`text-xl font-bold leading-tight ${profitColor}`}>
          {profitPrefix} {formatKRW(Math.abs(kpi.todayProfit))}
        </p>
        <p className={`text-[10px] mt-1 ${profitColor}`}>
          {profitPrefix} {Math.abs(kpi.todayProfitRate).toFixed(2)}% 전일 대비
        </p>
      </div>

      {/* 목표 달성률 */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
        <p className="text-xs text-slate-400 mb-1">목표 달성률</p>
        <p className={`text-3xl font-bold ${achievementRate >= 60 ? "text-green-400" : achievementRate >= 40 ? "text-yellow-400" : "text-red-400"}`}>
          {targets.length > 0 ? `${achievementRate}%` : "—"}
        </p>
        <div className="mt-2 h-1.5 bg-slate-700 rounded-full">
          <div
            className={`h-full rounded-full transition-all ${achievementRate >= 60 ? "bg-green-500" : achievementRate >= 40 ? "bg-yellow-500" : "bg-red-500"}`}
            style={{ width: `${Math.min(achievementRate, 100)}%` }}
          />
        </div>
        <p className="text-[10px] text-slate-500 mt-1">
          {targets.length > 0
            ? `${targets.filter((t) => t.level === "normal").length}/${targets.length} 목표 정상`
            : "목표 데이터 없음"}
        </p>
      </div>

      {/* 리스크 대별 */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
        <p className="text-xs text-slate-400 mb-1">리스크 대별</p>
        <p className={`text-2xl font-bold ${riskColor}`}>{kpi.riskLevel}</p>
        {(() => {
          const riskBars = { "낮음": 2, "보통": 5, "높음": 8 }[kpi.riskLevel] ?? 5;
          const barColor = { "낮음": "bg-green-500", "보통": "bg-yellow-500", "높음": "bg-red-500" }[kpi.riskLevel] ?? "bg-yellow-500";
          return (
            <>
              <div className="flex gap-0.5 mt-2">
                {Array.from({ length: 10 }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 flex-1 rounded-full ${i < riskBars ? barColor : "bg-slate-700"}`}
                  />
                ))}
              </div>
              <p className="text-[10px] text-slate-500 mt-1">{riskBars} / 10</p>
            </>
          );
        })()}
      </div>

      {/* 데이터 동기화 상태 */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
        <p className="text-xs text-slate-400 mb-1">데이터 동기화 상태</p>
        <div className="flex items-center gap-2 mt-1">
          {syncOk === null ? (
            <span className="w-2.5 h-2.5 rounded-full bg-slate-500 animate-pulse" />
          ) : syncOk ? (
            <span className="w-2.5 h-2.5 rounded-full bg-green-400" />
          ) : (
            <span className="w-2.5 h-2.5 rounded-full bg-yellow-400 animate-pulse" />
          )}
          <span className={`text-lg font-bold ${syncOk ? "text-green-400" : syncOk === false ? "text-yellow-400" : "text-slate-400"}`}>
            {syncOk === null ? "확인 중" : syncOk ? "정상" : "미확인"}
          </span>
        </div>
        <p className="text-[10px] text-slate-500 mt-2 truncate">모든 데이터 최신</p>
        <p className="text-[10px] text-slate-600 mt-0.5 truncate">{syncTime}</p>
      </div>
    </div>
  );
}
