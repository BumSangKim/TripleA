// components/dashboard/SystemStatusPanel.tsx
"use client";
import { useEffect, useState } from "react";
import Card from "@/components/ui/Card";
import { BASE_URL } from "@/lib/api";

interface SystemStatus {
  macro_last_update: string | null;
  holdings_last_update: string | null;
  total_indicators: number;
  recent_7d_rows: number;
  success_rate: number;
  unread_alerts: number;
  pipeline_status: string;
  timestamp: string;
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span className={`w-1.5 h-1.5 rounded-full inline-block ${ok ? "bg-green-400" : "bg-yellow-400 animate-pulse"}`} />
  );
}

function formatTs(ts: string | null) {
  if (!ts) return "—";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts.slice(0, 16);
  return d.toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function SystemStatusPanel() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BASE_URL}/api/system/status`)
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Card title="데이터 동기화 / 입력 현황">
        <div className="animate-pulse space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-4 bg-slate-700 rounded" />
          ))}
        </div>
      </Card>
    );
  }

  const rows = status
    ? [
        { label: "매크로 DB 갱신 시각",   value: formatTs(status.macro_last_update), ok: !!status.macro_last_update },
        { label: "계좌 CSV 업로드 시각",   value: formatTs(status.holdings_last_update), ok: !!status.holdings_last_update },
        { label: "파이프라인 실행 상태",   value: status.pipeline_status, ok: status.pipeline_status === "정상" },
        { label: "수집 성공률 (최근 7일)", value: `${status.success_rate}%`, ok: status.success_rate > 90 },
        { label: "총 지표 수",             value: `${status.total_indicators.toLocaleString()}건`, ok: status.total_indicators > 0 },
      ]
    : [];

  return (
    <Card title="데이터 동기화 / 입력 현황">
      <div className="space-y-2 text-xs">
        {rows.map((row) => (
          <div key={row.label} className="flex items-center justify-between">
            <span className="text-slate-400">{row.label}</span>
            <div className="flex items-center gap-1.5">
              <StatusDot ok={row.ok} />
              <span className="text-white font-medium">{row.value}</span>
            </div>
          </div>
        ))}
        {status && (
          <div className="flex items-center justify-between pt-1 border-t border-slate-700">
            <span className="text-slate-400">미읽은 알림</span>
            <span className={status.unread_alerts > 0 ? "text-yellow-400 font-semibold" : "text-white"}>
              {status.unread_alerts}개
            </span>
          </div>
        )}
        {!status && (
          <p className="text-xs text-slate-600 text-center py-2">API 연결 확인 필요</p>
        )}
      </div>
    </Card>
  );
}
