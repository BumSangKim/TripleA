// app/portfolio/PortfolioPageClient.tsx
"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AllocationItem, AccountSummary } from "@/lib/types";
import Card from "@/components/ui/Card";
import StatusChip from "@/components/ui/StatusChip";
import { cn, formatKRW } from "@/lib/utils";

const ASSET_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#ec4899", "#14b8a6"];

function DonutChart({ items }: { items: AllocationItem[] }) {
  const total = items.reduce((s, i) => s + i.value, 0) || 1;
  let cumulative = 0;
  const segments = items.map((item, idx) => {
    const ratio = item.value / total;
    const start = cumulative;
    cumulative += ratio;
    const startAngle = start * 2 * Math.PI - Math.PI / 2;
    const endAngle = cumulative * 2 * Math.PI - Math.PI / 2;
    const r = 70;
    const cx = 90, cy = 90;
    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);
    const largeArc = ratio > 0.5 ? 1 : 0;
    return {
      d: `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`,
      color: ASSET_COLORS[idx % ASSET_COLORS.length],
      label: item.asset,
      ratio,
    };
  });

  return (
    <div className="flex flex-col md:flex-row items-center gap-6">
      <svg viewBox="0 0 180 180" className="w-36 h-36 shrink-0">
        {segments.map((s, i) => (
          <path key={i} d={s.d} fill={s.color} opacity={0.85} />
        ))}
        <circle cx="90" cy="90" r="42" fill="#0f172a" />
        <text x="90" y="86" textAnchor="middle" className="text-[10px]" fill="#94a3b8" fontSize="10">
          총자산
        </text>
        <text x="90" y="100" textAnchor="middle" fill="white" fontSize="11" fontWeight="bold">
          {formatKRW(total)}
        </text>
      </svg>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        {segments.map((s, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: s.color }} />
            <span className="text-slate-400 text-xs">{s.label}</span>
            <span className="text-white font-semibold text-xs ml-auto">{(s.ratio * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function PortfolioPageClient() {
  const [allocation, setAllocation] = useState<AllocationItem[]>([]);
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortBy, setSortBy] = useState<"value" | "ratio">("value");

  useEffect(() => {
    Promise.all([
      api.getDashboardSummary(),
    ])
      .then(([summary]) => {
        setAllocation(summary.allocation ?? []);
        setAccounts(summary.accounts ?? []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const totalValue = accounts.reduce((s, a) => s + a.value, 0);
  const totalProfit = accounts.reduce((s, a) => s + a.profit, 0);
  const totalProfitRate = totalValue > 0 ? (totalProfit / (totalValue - totalProfit)) * 100 : 0;

  const sorted = [...allocation].sort((a, b) =>
    sortBy === "value" ? b.value - a.value : b.ratio - a.ratio
  );

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">포트폴리오</h1>
        <p className="text-sm text-slate-400">전체 자산 배분 및 계좌별 현황</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40 text-slate-500">로딩 중...</div>
      ) : (
        <>
          {/* KPI */}
          <div className="grid grid-cols-3 gap-4">
            <Card>
              <p className="text-xs text-slate-400">총 평가금액</p>
              <p className="text-2xl font-bold text-white mt-1">{formatKRW(totalValue)}</p>
            </Card>
            <Card>
              <p className="text-xs text-slate-400">총 손익</p>
              <p className={cn("text-2xl font-bold mt-1", totalProfit >= 0 ? "text-green-400" : "text-red-400")}>
                {totalProfit >= 0 ? "+" : ""}{formatKRW(totalProfit)}
              </p>
            </Card>
            <Card>
              <p className="text-xs text-slate-400">수익률</p>
              <p className={cn("text-2xl font-bold mt-1", totalProfitRate >= 0 ? "text-green-400" : "text-red-400")}>
                {totalProfitRate >= 0 ? "+" : ""}{totalProfitRate.toFixed(2)}%
              </p>
            </Card>
          </div>

          {/* 도넛 차트 */}
          <Card title="자산 배분">
            <DonutChart items={allocation} />
          </Card>

          {/* 자산 클래스 상세 테이블 */}
          <Card
            title="자산 클래스별 비중"
            extra={
              <div className="flex gap-2">
                {(["value", "ratio"] as const).map((s) => (
                  <button
                    key={s}
                    onClick={() => setSortBy(s)}
                    className={cn(
                      "px-2 py-0.5 text-xs rounded transition-colors",
                      sortBy === s ? "bg-blue-600 text-white" : "bg-slate-700 text-slate-400 hover:bg-slate-600"
                    )}
                  >
                    {s === "value" ? "금액순" : "비중순"}
                  </button>
                ))}
              </div>
            }
          >
            <div className="space-y-3">
              {sorted.map((item, idx) => (
                <div key={item.asset}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2.5 h-2.5 rounded-full"
                        style={{ background: ASSET_COLORS[idx % ASSET_COLORS.length] }}
                      />
                      <span className="text-sm text-white">{item.asset}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-sm font-semibold text-white">{formatKRW(item.value)}</span>
                      <span className="text-xs text-slate-500 ml-2">{item.ratio.toFixed(1)}%</span>
                    </div>
                  </div>
                  <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${item.ratio}%`,
                        background: ASSET_COLORS[idx % ASSET_COLORS.length],
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* 계좌별 요약 */}
          <Card title="계좌별 현황">
            <div className="divide-y divide-slate-700">
              {accounts.map((acct) => (
                <div key={acct.id} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-600/30 flex items-center justify-center text-blue-400 text-xs font-bold">
                      {acct.name.charAt(0)}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">{acct.name}</p>
                      <p className="text-xs text-slate-500">{acct.type ?? "일반"}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-white">{formatKRW(acct.value)}</p>
                    <p className={cn("text-xs", acct.profit >= 0 ? "text-green-400" : "text-red-400")}>
                      {acct.profit >= 0 ? "▲" : "▼"} {Math.abs(acct.profitRate).toFixed(2)}%
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
