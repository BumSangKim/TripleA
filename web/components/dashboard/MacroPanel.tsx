// components/dashboard/MacroPanel.tsx
import { MacroIndicator } from "@/lib/types";
import Card from "@/components/ui/Card";
import MetricCard from "@/components/ui/MetricCard";

interface MacroPanelProps {
  indicators: MacroIndicator[];
}

function latestUpdateLabel(indicators: MacroIndicator[]): string {
  const dates = indicators.map((i) => i.date).filter(Boolean) as string[];
  if (!dates.length) return "데이터 없음";
  const latest = dates.sort().reverse()[0];
  try {
    const d = new Date(latest);
    if (isNaN(d.getTime())) return latest;
    const diff = Math.floor((Date.now() - d.getTime()) / 60_000);
    if (diff < 1) return "방금 전";
    if (diff < 60) return `${diff}분 전`;
    if (diff < 1440) return `${Math.floor(diff / 60)}시간 전`;
    return `${Math.floor(diff / 1440)}일 전`;
  } catch {
    return latest;
  }
}

export default function MacroPanel({ indicators }: MacroPanelProps) {
  const updateLabel = latestUpdateLabel(indicators);
  return (
    <Card
      title="매크로 데이터 현황"
      extra={<span className="text-slate-500 text-xs">업데이트: {updateLabel}</span>}
      className="col-span-2"
    >
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {indicators.slice(0, 9).map((ind) => (
          <MetricCard key={ind.key} indicator={ind} />
        ))}
      </div>
      {indicators.length === 0 && (
        <div className="text-center py-8 text-slate-500 text-sm">
          데이터 수집 중... 파이프라인을 실행해 주세요.
        </div>
      )}
    </Card>
  );
}
