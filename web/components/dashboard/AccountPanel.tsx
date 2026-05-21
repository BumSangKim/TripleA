// components/dashboard/AccountPanel.tsx
import { AccountSummary, AllocationItem } from "@/lib/types";
import Card from "@/components/ui/Card";
import { formatKRW } from "@/lib/utils";

interface AccountPanelProps {
  accounts: AccountSummary[];
  allocation: AllocationItem[];
}

const ASSET_COLORS: Record<string, string> = {
  "국내주식": "#3b82f6",
  "해외주식": "#10b981",
  "채권":     "#f59e0b",
  "ETF":      "#8b5cf6",
  "현금":     "#6b7280",
  "기타/대기": "#374151",
};

function DonutChart({ items }: { items: AllocationItem[] }) {
  const total = items.reduce((s, i) => s + i.ratio, 0);
  let cum = 0;
  const cx = 60, cy = 60, r = 48, strokeW = 14;
  const circumference = 2 * Math.PI * r;

  return (
    <div className="flex items-center gap-4">
      <svg width={120} height={120} viewBox="0 0 120 120" className="shrink-0">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e293b" strokeWidth={strokeW} />
        {items.map((item) => {
          const pct = item.ratio / total;
          const dash = pct * circumference;
          const offset = circumference - cum * circumference;
          cum += pct;
          return (
            <circle
              key={item.asset}
              cx={cx} cy={cy} r={r}
              fill="none"
              stroke={ASSET_COLORS[item.asset] || "#64748b"}
              strokeWidth={strokeW}
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={offset}
              transform={`rotate(-90 ${cx} ${cy})`}
              className="transition-all"
            />
          );
        })}
      </svg>
      <div className="flex flex-col gap-1 text-xs">
        {items.map((item) => (
          <div key={item.asset} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: ASSET_COLORS[item.asset] || "#64748b" }} />
            <span className="text-slate-400">{item.asset}</span>
            <span className="text-white ml-auto pl-2 font-medium">{item.ratio.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AccountPanel({ accounts, allocation }: AccountPanelProps) {
  return (
    <Card title="계좌 현황" extra={<a href="/accounts" className="text-blue-400 hover:underline">더보기 &gt;</a>}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 도넛 차트 */}
        <div>
          <p className="text-xs text-slate-500 mb-2">자산 구성</p>
          <DonutChart items={allocation} />
        </div>

        {/* 계좌 목록 */}
        <div>
          <p className="text-xs text-slate-500 mb-2">계좌 목록</p>
          <div className="space-y-1.5">
            {accounts.map((acc) => (
              <div key={acc.id} className="flex items-center justify-between py-1.5 border-b border-slate-700/50 last:border-0">
                <div>
                  <p className="text-sm text-white font-medium">{acc.name}</p>
                  <p className="text-[10px] text-slate-500">{acc.type}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-white">{formatKRW(acc.value)}</p>
                  <p className={`text-[10px] ${acc.profitRate >= 0 ? "text-red-400" : "text-blue-400"}`}>
                    {acc.profitRate >= 0 ? "▲" : "▼"} {Math.abs(acc.profitRate).toFixed(2)}%
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}
