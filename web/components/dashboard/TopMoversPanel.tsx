// components/dashboard/TopMoversPanel.tsx
import { TopMover } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface TopMoversPanelProps {
  movers: TopMover[];
}

// 미니 스파크라인 (임의)
function MiniSparkline({ up }: { up: boolean }) {
  const color = up ? "#f87171" : "#60a5fa";
  const points = up
    ? "0,12 10,10 20,8 30,5 40,7 50,3 60,2 70,4 80,1"
    : "0,2 10,4 20,3 30,6 40,8 50,7 60,9 70,11 80,12";
  return (
    <svg width={80} height={14} className="overflow-visible">
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function TopMoversPanel({ movers }: TopMoversPanelProps) {
  return (
    <Card title="보유 자산 Top Movers" extra={
      <div className="flex gap-1.5 text-[10px]">
        {["일간", "주간", "월간"].map((p, i) => (
          <button key={p} className={cn("px-2 py-0.5 rounded", i === 0 ? "bg-blue-600 text-white" : "text-slate-500 hover:text-slate-300")}>
            {p}
          </button>
        ))}
      </div>
    }>
      <div className="space-y-2">
        {movers.map((m, idx) => {
          const up = m.changeRate >= 0;
          const changeColor = up ? "text-red-400" : "text-blue-400";
          return (
            <div key={m.symbol} className="flex items-center gap-3 py-1.5 border-b border-slate-700/50 last:border-0">
              <span className="w-5 text-xs text-slate-500 text-center">{idx + 1}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white font-medium truncate">{m.symbol}</p>
                {m.name && <p className="text-[10px] text-slate-500 truncate">{m.name}</p>}
              </div>
              {m.price && (
                <span className="text-sm text-slate-300 font-mono">
                  {m.price > 10000
                    ? m.price.toLocaleString("ko-KR")
                    : `$${m.price.toFixed(2)}`}
                </span>
              )}
              <MiniSparkline up={up} />
              <span className={cn("text-sm font-medium w-14 text-right", changeColor)}>
                {up ? "▲" : "▼"} {Math.abs(m.changeRate).toFixed(2)}%
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
