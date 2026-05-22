// components/ui/MetricCard.tsx
"use client";
import { MacroIndicator } from "@/lib/types";
import StatusChip from "./StatusChip";

interface MetricCardProps {
  indicator: MacroIndicator;
}

// 미니 스파크라인 SVG
function Sparkline({ data, status }: { data: number[]; status: string }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 80, h = 24;
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  }).join(" ");
  const color = status === "rising" ? "#f87171" : status === "falling" ? "#60a5fa" : "#94a3b8";
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function MetricCard({ indicator }: MetricCardProps) {
  const changeColor = indicator.status === "rising" ? "text-red-400" : indicator.status === "falling" ? "text-blue-400" : "text-slate-400";
  const changePrefix = indicator.change !== null && indicator.change !== undefined
    ? (indicator.change >= 0 ? "▲" : "▼")
    : "";

  return (
    <div className="bg-slate-700/50 rounded-lg p-3 flex flex-col gap-1 hover:bg-slate-700 transition-colors">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-400 font-medium">{indicator.name}</span>
        <StatusChip status={indicator.status} />
      </div>
      <div className="flex items-end justify-between">
        <div>
          <span className="text-xl font-bold text-white">
            {indicator.value !== null && indicator.value !== undefined
              ? indicator.value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })
              : "—"}
          </span>
          <span className="text-xs text-slate-400 ml-1">{indicator.unit}</span>
        </div>
        {indicator.history && <Sparkline data={indicator.history} status={indicator.status} />}
      </div>
      {indicator.change !== null && indicator.change !== undefined && (
        <span className={`text-xs font-medium ${changeColor}`}>
          {changePrefix} {Math.abs(indicator.change).toFixed(2)}
          <span className="text-slate-500 ml-1">전기비</span>
        </span>
      )}
      {indicator.date && <span className="text-[10px] text-slate-600">{indicator.date}</span>}
    </div>
  );
}
