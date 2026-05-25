// app/macro/MacroPageClient.tsx
"use client";
import { useCallback, useEffect, useState } from "react";
import { api, BASE_URL } from "@/lib/api";
import type { MacroIndicator } from "@/lib/types";
import StatusChip from "@/components/ui/StatusChip";
import Card from "@/components/ui/Card";

type HistoryPoint = { date: string; value: number };
type HistoryRange = { days: number; label: string };

const HISTORY_RANGES: HistoryRange[] = [
  { days: 30, label: "1개월" },
  { days: 90, label: "3개월" },
  { days: 180, label: "6개월" },
  { days: 365, label: "1년" },
  { days: 365 * 3, label: "3년" },
  { days: 365 * 5, label: "5년" },
];

function MiniChart({
  data,
  status,
}: {
  data: number[];
  status: MacroIndicator["status"];
}) {
  if (!data || data.length < 2) return null;
  const w = 80,
    h = 28;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");
  const color =
    status === "rising" ? "#22c55e" : status === "falling" ? "#ef4444" : "#60a5fa";
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-20 h-7">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function formatAxisValue(value: number) {
  const abs = Math.abs(value);
  if (abs >= 1000) return value.toLocaleString("ko-KR", { maximumFractionDigits: 0 });
  if (abs >= 100) return value.toLocaleString("ko-KR", { maximumFractionDigits: 1 });
  if (abs >= 10) return value.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
  return value.toLocaleString("ko-KR", { maximumFractionDigits: 3 });
}

function HistoryChart({ indicator, unit }: { indicator: string; unit?: string | null }) {
  const [data, setData] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(365);

  const fetchHistory = useCallback(() => {
    setLoading(true);
    fetch(`${BASE_URL}/api/macro/history/${encodeURIComponent(indicator)}?days=${days}`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [indicator, days]);

  useEffect(() => {
    const timer = window.setTimeout(fetchHistory, 0);
    return () => window.clearTimeout(timer);
  }, [fetchHistory]);

  if (loading) return <div className="h-40 flex items-center justify-center text-slate-600 text-sm">데이터 확인 중...</div>;
  if (!data.length) return <div className="h-40 flex items-center justify-center text-slate-600 text-sm">데이터 없음</div>;

  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 460, H = 140;
  const axisLeft = 58;
  const axisRight = 12;
  const axisTop = 10;
  const axisBottom = 24;
  const chartW = W - axisLeft - axisRight;
  const chartH = H - axisTop - axisBottom;
  const tickValues = max === min ? [max] : [max, min + range / 2, min];

  const points = data
    .map((d, i) => {
      const x = axisLeft + (data.length === 1 ? chartW / 2 : (i / (data.length - 1)) * chartW);
      const y = axisTop + chartH - ((d.value - min) / range) * chartH;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-2">
        {HISTORY_RANGES.map((rangeOption) => (
          <button
            key={rangeOption.days}
            onClick={() => setDays(rangeOption.days)}
            aria-pressed={days === rangeOption.days}
            className={`px-2 py-0.5 rounded text-xs transition-colors ${
              days === rangeOption.days ? "bg-blue-600 text-white" : "bg-slate-700 text-slate-400 hover:bg-slate-600"
            }`}
          >
            {rangeOption.label}
          </button>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-36" role="img" aria-label={`${indicator} 히스토리 차트`}>
        {tickValues.map((tick) => {
          const y = axisTop + chartH - ((tick - min) / range) * chartH;
          return (
            <g key={tick}>
              <line x1={axisLeft} y1={y} x2={W - axisRight} y2={y} stroke="#334155" strokeWidth="0.8" />
              <text x={axisLeft - 6} y={y + 3} textAnchor="end" className="fill-slate-500 text-[10px]">
                {formatAxisValue(tick)}
              </text>
            </g>
          );
        })}
        <line x1={axisLeft} y1={axisTop} x2={axisLeft} y2={axisTop + chartH} stroke="#475569" strokeWidth="1" />
        <line x1={axisLeft} y1={axisTop + chartH} x2={W - axisRight} y2={axisTop + chartH} stroke="#475569" strokeWidth="1" />
        <polyline points={points} fill="none" stroke="#60a5fa" strokeWidth="2" />
        {data.length === 1 && (
          <circle
            cx={axisLeft + chartW / 2}
            cy={axisTop + chartH - ((data[0].value - min) / range) * chartH}
            r="3"
            fill="#60a5fa"
          />
        )}
        {unit && (
          <text x={axisLeft} y={H - 4} className="fill-slate-500 text-[10px]">
            {unit}
          </text>
        )}
      </svg>
      <div className="flex justify-between pl-14 pr-3 text-[10px] text-slate-600 mt-1">
        <span>{data[0]?.date}</span>
        <span>{data[data.length - 1]?.date}</span>
      </div>
    </div>
  );
}

export default function MacroPageClient() {
  const [indicators, setIndicators] = useState<MacroIndicator[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api
      .getMacroSummary()
      .then(setIndicators)
      .catch(() => setIndicators([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = indicators.filter((i) =>
    i.name.toLowerCase().includes(search.toLowerCase()) ||
    i.key.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">매크로 데이터</h1>
          <p className="text-sm text-slate-400">경제 지표 현황 및 추세 분석</p>
        </div>
        <input
          type="text"
          placeholder="지표 검색..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-1.5 text-sm text-white
                     placeholder:text-slate-500 focus:outline-none focus:border-blue-500 w-48"
        />
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40 text-slate-500">데이터 로딩 중...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((ind) => (
            <Card key={ind.key}>
              <div
                className="cursor-pointer"
                onClick={() => setSelected(selected === ind.key ? null : ind.key)}
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="text-xs text-slate-400">{ind.key}</p>
                    <p className="text-sm font-semibold text-white mt-0.5">{ind.name}</p>
                  </div>
                  <StatusChip status={ind.status} />
                </div>
                <div className="flex items-end justify-between">
                  <div>
                    <span className="text-2xl font-bold text-white">
                      {ind.value != null ? ind.value.toFixed(2) : "—"}
                    </span>
                    <span className="text-xs text-slate-500 ml-1">{ind.unit}</span>
                    {ind.change != null && (
                      <p className={`text-xs mt-0.5 ${ind.change >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {ind.change >= 0 ? "▲" : "▼"} {Math.abs(ind.change).toFixed(3)}
                      </p>
                    )}
                  </div>
                  <MiniChart data={ind.history ?? []} status={ind.status} />
                </div>
                <p className="text-[10px] text-slate-600 mt-2">{ind.date}</p>
                <p className="text-[10px] text-blue-400 mt-1">
                  {selected === ind.key ? "▲ 차트 닫기" : "▼ 히스토리 차트 보기"}
                </p>
              </div>

              {selected === ind.key && (
                <div className="mt-3 pt-3 border-t border-slate-700">
                  <HistoryChart indicator={ind.key} unit={ind.unit} />
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="text-center py-20 text-slate-600">검색 결과가 없습니다.</div>
      )}
    </div>
  );
}
