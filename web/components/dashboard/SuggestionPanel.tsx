// components/dashboard/SuggestionPanel.tsx
import { SuggestionItem, TargetItem } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface SuggestionPanelProps {
  suggestions: SuggestionItem[];
  targets: TargetItem[];
}

const ACTION_STYLE: Record<string, { bg: string; text: string; badge: string }> = {
  "비중 축소": { bg: "bg-red-500/10 border-red-500/20",    text: "text-red-400",    badge: "bg-red-500/20 text-red-400" },
  "비중 확대": { bg: "bg-green-500/10 border-green-500/20", text: "text-green-400",  badge: "bg-green-500/20 text-green-400" },
  "관망":      { bg: "bg-slate-700/50 border-slate-600",    text: "text-slate-400",  badge: "bg-slate-700 text-slate-400" },
};

export default function SuggestionPanel({ suggestions, targets }: SuggestionPanelProps) {
  return (
    <Card title="리밸런싱 점검 (룰 기반)" extra={<span className="text-slate-600">* 룰 기반 자동 분석</span>}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 border-b border-slate-700">
              <th className="text-left pb-2 font-medium">자산군</th>
              <th className="text-right pb-2 font-medium">현재</th>
              <th className="text-right pb-2 font-medium">목표</th>
              <th className="text-right pb-2 font-medium">괴리</th>
              <th className="text-left pb-2 font-medium pl-3">규칙/사유</th>
              <th className="text-right pb-2 font-medium">판단/조치</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/50">
            {suggestions.map((s) => {
              const t = targets.find((t) => t.asset_class === s.asset);
              const style = ACTION_STYLE[s.action] || ACTION_STYLE["관망"];
              return (
                <tr key={s.asset} className="hover:bg-slate-700/30 transition-colors">
                  <td className="py-2 text-white font-medium">{s.asset}</td>
                  <td className="py-2 text-right text-slate-300">{t ? `${t.currentRatio.toFixed(1)}%` : "—"}</td>
                  <td className="py-2 text-right text-slate-300">{t ? `${t.targetRatio.toFixed(1)}%` : "—"}</td>
                  <td className={cn("py-2 text-right font-medium", style.text)}>
                    {s.deviation > 0 ? "+" : ""}{s.deviation.toFixed(1)}%
                  </td>
                  <td className="py-2 pl-3 text-slate-400 max-w-[160px]">
                    <span className="text-[10px] leading-tight">{s.reason || "—"}</span>
                  </td>
                  <td className="py-2 text-right">
                    <span className={cn("inline-block px-2 py-0.5 rounded text-[10px] font-medium", style.badge)}>
                      {s.action}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="text-[10px] text-slate-600 mt-3">
        ※ 룰 기반 분석입니다. 최종 매매 결정은 본인의 판단을 따르십시오.
      </p>
    </Card>
  );
}
