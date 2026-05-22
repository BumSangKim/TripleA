// app/macro/MacroPageClient.tsx
"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { MacroIndicator } from "@/lib/types";
import StatusChip from "@/components/ui/StatusChip";
import Card from "@/components/ui/Card";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type HistoryPoint = { date: string; value: number };

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

function HistoryChart({ indicator }: { indicator: string }) {
  const [data, setData] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(30);

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

  if (loading) return <div className="h-32 flex items-center justify-center text-slate-600 text-sm">로딩 중...</div>;
  if (!data.length) return <div className="h-32 flex items-center justify-center text-slate-600 text-sm">데이터 없음</div>;

  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 400, H = 100;

  const points = data
    .map((d, i) => {
      const x = (i / (data.length - 1)) * W;
      const y = H - ((d.value - min) / range) * (H - 16) - 8;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div>
      <div className="flex gap-2 mb-2">
        {[7, 30, 90, 180].map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`px-2 py-0.5 rounded text-xs transition-colors ${
              days === d ? "bg-blue-600 text-white" : "bg-slate-700 text-slate-400 hover:bg-slate-600"
            }`}
          >
            {d === 7 ? "1주" : d === 30 ? "1개월" : d === 90 ? "3개월" : "6개월"}
          </button>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-24">
        <polyline points={points} fill="none" stroke="#60a5fa" strokeWidth="2" />
        <line x1="0" y1={H - 4} x2={W} y2={H - 4} stroke="#334155" strokeWidth="1" />
      </svg>
      <div className="flex justify-between text-[10px] text-slate-600 mt-1">
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
                  <HistoryChart indicator={ind.key} />
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
