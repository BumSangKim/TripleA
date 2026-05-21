// components/dashboard/InsightPanel.tsx
import { Insights } from "@/lib/types";
import Card from "@/components/ui/Card";

interface InsightPanelProps {
  insights: Insights;
}

export default function InsightPanel({ insights }: InsightPanelProps) {
  return (
    <Card title="오늘의 인사이트" className="col-span-full">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <InsightItem icon="📊" label="매크로 요약" text={insights.macroSummary} />
        <InsightItem icon="💼" label="포트폴리오" text={insights.portfolioSummary} />
        <InsightItem icon="⚡" label="시장 위험" text={insights.marketRisk} />
        <InsightItem icon="🎯" label="권장 대응" text={insights.recommendation} highlight />
      </div>
    </Card>
  );
}

function InsightItem({
  icon, label, text, highlight,
}: { icon: string; label: string; text: string; highlight?: boolean }) {
  return (
    <div className={`p-3 rounded-lg border text-sm ${highlight ? "bg-blue-500/10 border-blue-500/20" : "bg-slate-700/50 border-slate-700"}`}>
      <div className="flex items-center gap-1.5 mb-1.5">
        <span>{icon}</span>
        <span className="text-xs text-slate-400 font-medium">{label}</span>
      </div>
      <p className={`text-sm leading-snug ${highlight ? "text-blue-300" : "text-slate-300"}`}>
        {text}
      </p>
    </div>
  );
}
