// components/dashboard/TargetPanel.tsx
import { TargetItem } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface TargetPanelProps {
  targets: TargetItem[];
}

/** 현재/목표 값 포맷 (원화 금액 or 비율) */
function fmtVal(val: number, unit?: string): string {
  if (unit === "원") {
    if (val >= 100_000_000) return `W ${(val / 100_000_000).toFixed(1)}억`;
    if (val >= 10_000_000)  return `W ${(val / 10_000_000).toFixed(1)}천만`;
    if (val >= 1_000_000)   return `W ${(val / 1_000_000).toFixed(1)}M`;
    return `W ${val.toLocaleString("ko-KR")}`;
  }
  return `${val.toFixed(1)}%`;
}

function DeviationBar({ current, target, max, level }: { current: number; target: number; max: number; level: string }) {
  const pct = Math.min(Math.max((current / max) * 100, 0), 100);
  const tPct = Math.min(Math.max((target / max) * 100, 0), 100);
  const barColor = level === "danger" ? "bg-red-500" : level === "warning" ? "bg-yellow-500" : "bg-blue-500";
  return (
    <div className="relative h-1.5 bg-slate-700 rounded-full mt-1">
      <div className={cn("h-full rounded-full transition-all", barColor)} style={{ width: `${pct}%` }} />
      <div
        className="absolute top-1/2 -translate-y-1/2 w-0.5 h-3 bg-white/60 rounded-full"
        style={{ left: `${tPct}%` }}
      />
    </div>
  );
}

export default function TargetPanel({ targets }: TargetPanelProps) {
  // 자산배분과 기타 목표 분리
  const allocTargets = targets.filter((t) => (t.target_type ?? "asset_allocation") === "asset_allocation");
  const specialTargets = targets.filter((t) => t.target_type && t.target_type !== "asset_allocation");

  const renderTarget = (t: TargetItem) => {
    const devColor = t.level === "danger"
      ? "text-red-400 bg-red-500/10"
      : t.level === "warning"
      ? "text-yellow-400 bg-yellow-500/10"
      : "text-slate-400 bg-slate-700";
    const devSign = t.deviation > 0 ? "+" : "";
    const unit = t.unit ?? "%";
    // bar의 max는 asset_allocation은 100%, 금액은 target×1.5
    const barMax = unit === "원" ? t.targetRatio * 1.5 : 100;

    return (
      <div key={`${t.target_type}-${t.asset_class}`} className="group">
        <div className="flex items-center justify-between mb-0.5">
          <span className="text-sm text-white">{t.asset_class}</span>
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-300">
              {fmtVal(t.currentRatio, unit)} / {fmtVal(t.targetRatio, unit)}
            </span>
            <span className={cn("px-1.5 py-0.5 rounded text-[11px] font-medium", devColor)}>
              {devSign}{t.deviation.toFixed(1)}{unit === "원" ? "%" : "%"}
            </span>
          </div>
        </div>
        <DeviationBar current={t.currentRatio} target={t.targetRatio} max={barMax} level={t.level} />
      </div>
    );
  };

  return (
    <Card
      title="목표수치와 괴리 현황"
      extra={<a href="/targets" className="text-blue-400 hover:underline">더보기 &gt;</a>}
    >
      <div className="space-y-3">
        {/* 자산배분 목표 */}
        {allocTargets.map(renderTarget)}

        {/* 구분선 + 기타 목표 */}
        {specialTargets.length > 0 && (
          <>
            <div className="border-t border-slate-700 pt-2 mt-1">
              <p className="text-[10px] text-slate-500 mb-2">투자/수익 목표</p>
              {specialTargets.map(renderTarget)}
            </div>
          </>
        )}

        {targets.length === 0 && (
          <p className="text-center text-slate-500 text-sm py-4">목표 데이터가 없습니다.</p>
        )}
      </div>
    </Card>
  );
}
