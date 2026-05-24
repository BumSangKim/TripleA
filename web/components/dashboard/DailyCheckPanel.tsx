// components/dashboard/DailyCheckPanel.tsx
"use client";
import { useEffect, useState } from "react";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";

const CHECK_ITEMS = [
  { id: "macro",    label: "매크로 지표 확인",   desc: "PCE 물가지수 등 주요 지표 발표 체계" },
  { id: "target",   label: "목표/괴리 점검",      desc: "현재 목표 및 괴리 비중 점검" },
  { id: "rebal",    label: "리밸런싱 점검",       desc: "현재 조치 및 규칙 사항 확인" },
  { id: "datasync", label: "데이터 동기화 확인",  desc: "모든 데이터 이상 없이 동기화" },
];

const TODAY_KEY = () => `triplea_daily_check_${new Date().toISOString().slice(0, 10)}`;

export default function DailyCheckPanel() {
  const [checked, setChecked] = useState<Record<string, boolean>>({});

  // 마운트 시 오늘 날짜 키로 localStorage에서 복원
  useEffect(() => {
    try {
      const raw = localStorage.getItem(TODAY_KEY());
      if (raw) setChecked(JSON.parse(raw));
    } catch {
      // localStorage 접근 실패 시 기본값 유지
    }
  }, []);

  const toggle = (id: string) => {
    setChecked((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      try {
        localStorage.setItem(TODAY_KEY(), JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  const doneCount = Object.values(checked).filter(Boolean).length;

  return (
    <Card title="오늘의 점검 포인트" extra={
      <span className="text-xs text-slate-500">{doneCount}/{CHECK_ITEMS.length} 완료</span>
    }>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {CHECK_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => toggle(item.id)}
            className={cn(
              "flex items-start gap-2.5 p-3 rounded-lg border text-left transition-all",
              checked[item.id]
                ? "bg-green-500/10 border-green-500/30"
                : "bg-slate-700/50 border-slate-600 hover:border-slate-500"
            )}
          >
            <div className={cn(
              "w-4 h-4 rounded border-2 flex items-center justify-center shrink-0 mt-0.5 transition-all",
              checked[item.id]
                ? "bg-green-500 border-green-500"
                : "border-slate-500"
            )}>
              {checked[item.id] && (
                <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 12 12">
                  <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </div>
            <div>
              <p className={cn("text-sm font-medium", checked[item.id] ? "text-green-400" : "text-white")}>
                {item.label}
              </p>
              <p className="text-[10px] text-slate-500 mt-0.5">{item.desc}</p>
            </div>
          </button>
        ))}
      </div>
    </Card>
  );
}
