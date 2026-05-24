// app/settings/SettingsPageClient.tsx
"use client";
import { useEffect, useState } from "react";
import { BASE_URL } from "@/lib/api";

interface TargetSetting {
  id?: number;
  asset_class: string;
  targetRatio: number;
  warning_thr: number;
  danger_thr: number;
}

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

// ── 알림 임계값 설정 섹션 ─────────────────────────────────────────────
function AlertThresholdSection() {
  const [targets, setTargets] = useState<TargetSetting[]>([]);
  const [saving, setSaving] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BASE_URL}/api/targets`)
      .then((r) => r.json())
      .then((data: Array<{ asset_class: string; targetRatio: number; warning_thr?: number; danger_thr?: number }>) =>
        setTargets(
          data.map((t) => ({
            asset_class: t.asset_class,
            targetRatio: t.targetRatio ?? 0,
            warning_thr: t.warning_thr ?? 3,
            danger_thr: t.danger_thr ?? 5,
          }))
        )
      )
      .catch(() => {});
  }, []);

  const handleChange = (idx: number, field: "warning_thr" | "danger_thr", val: number) => {
    setTargets((prev) => prev.map((t, i) => (i === idx ? { ...t, [field]: val } : t)));
  };

  const handleSave = async (t: TargetSetting) => {
    setSaving(t.asset_class);
    try {
      await fetch(`${BASE_URL}/api/targets`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          asset_class: t.asset_class,
          target_value: t.targetRatio,
          warning_thr: t.warning_thr,
          danger_thr: t.danger_thr,
        }),
      });
      setSaved(t.asset_class);
      setTimeout(() => setSaved(null), 2000);
    } finally {
      setSaving(null);
    }
  };

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xl">🔔</span>
        <h2 className="text-sm font-semibold text-white">알림 임계값 설정</h2>
      </div>
      <p className="text-xs text-slate-400 mb-4">
        각 자산군의 목표 비중 이탈 경고/위험 임계값을 설정합니다.
        변경 후 저장 버튼을 눌러주세요.
      </p>
      {targets.length === 0 ? (
        <p className="text-xs text-slate-500">목표 데이터를 불러오는 중...</p>
      ) : (
        <div className="space-y-3">
          {targets.map((t, idx) => (
            <div key={t.asset_class} className="grid grid-cols-5 gap-3 items-center text-xs">
              <span className="text-white font-medium col-span-1">{t.asset_class}</span>
              <div className="col-span-1">
                <label className="text-slate-500 block mb-0.5">목표 (%)</label>
                <span className="text-slate-300">{t.targetRatio.toFixed(1)}</span>
              </div>
              <div className="col-span-1">
                <label className="text-slate-500 block mb-0.5">경고 임계값 (%)</label>
                <input
                  type="number"
                  min={0} max={20} step={0.5}
                  value={t.warning_thr}
                  onChange={(e) => handleChange(idx, "warning_thr", parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white focus:outline-none focus:border-yellow-500"
                />
              </div>
              <div className="col-span-1">
                <label className="text-slate-500 block mb-0.5">위험 임계값 (%)</label>
                <input
                  type="number"
                  min={0} max={20} step={0.5}
                  value={t.danger_thr}
                  onChange={(e) => handleChange(idx, "danger_thr", parseFloat(e.target.value) || 0)}
                  className="w-full bg-slate-700 border border-slate-600 rounded px-2 py-1 text-white focus:outline-none focus:border-red-500"
                />
              </div>
              <div className="col-span-1 flex items-end">
                <button
                  onClick={() => handleSave(t)}
                  disabled={saving === t.asset_class}
                  className="w-full py-1.5 rounded bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white transition-colors"
                >
                  {saved === t.asset_class ? "✓ 저장됨" : saving === t.asset_class ? "저장 중..." : "저장"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 데이터 동기화 설정 섹션 ────────────────────────────────────────────
function TelegramButton() {
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const send = async () => {
    setSending(true);
    setResult(null);
    try {
      const res = await fetch(`${BASE_URL}/api/alerts/notify/telegram?level_filter=danger`, { method: "POST" });
      const d = await res.json();
      if (res.ok) {
        setResult(d.sent ? `📤 ${d.sent}개 전송됨` : "전송할 알림 없음");
      } else {
        setResult(`⚠️ ${d.detail || "오류"}`);
      }
    } catch {
      setResult("연결 오류");
    } finally {
      setSending(false);
      setTimeout(() => setResult(null), 4000);
    }
  };

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={send}
        disabled={sending}
        className="px-4 py-2 bg-blue-500 hover:bg-blue-400 disabled:opacity-50 rounded text-white text-xs transition-colors"
      >
        {sending ? "전송 중..." : "📱 Telegram 전송"}
      </button>
      {result && <span className="text-xs text-slate-300">{result}</span>}
    </div>
  );
}

function DataSyncSection() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genResult, setGenResult] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BASE_URL}/api/system/status`)
      .then((r) => r.json())
      .then((d) => setStatus(d))
      .catch(() => {});
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    setGenResult(null);
    try {
      const res = await fetch(`${BASE_URL}/api/alerts/generate`, { method: "POST" });
      const d = await res.json();
      setGenResult(`${d.created || 0}개 알림 생성됨`);
    } catch {
      setGenResult("오류 발생");
    } finally {
      setGenerating(false);
    }
  };

  const fmt = (ts: string | null) => {
    if (!ts) return "—";
    try {
      return new Date(ts).toLocaleString("ko-KR", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
    } catch {
      return ts.slice(0, 16);
    }
  };

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xl">🔄</span>
        <h2 className="text-sm font-semibold text-white">데이터 동기화</h2>
      </div>
      {status ? (
        <div className="space-y-2 text-xs mb-4">
          {[
            { label: "파이프라인 상태",      value: status.pipeline_status, highlight: status.pipeline_status === "정상" },
            { label: "매크로 DB 최종 갱신",  value: fmt(status.macro_last_update) },
            { label: "계좌 CSV 최종 업로드", value: fmt(status.holdings_last_update) },
            { label: "수집 성공률 (7일)",    value: `${status.success_rate}%` },
            { label: "총 지표 수",           value: `${status.total_indicators.toLocaleString()}건` },
            { label: "미읽은 알림",          value: `${status.unread_alerts}개` },
          ].map((item) => (
            <div key={item.label} className="flex justify-between items-center">
              <span className="text-slate-400">{item.label}</span>
              <span className={item.highlight !== undefined ? (item.highlight ? "text-green-400 font-medium" : "text-yellow-400") : "text-white"}>
                {item.value}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-500 mb-4">상태 불러오는 중...</p>
      )}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded text-white text-xs transition-colors"
        >
          {generating ? "실행 중..." : "알림 자동 생성"}
        </button>
        <TelegramButton />
        {genResult && <span className="text-xs text-green-400">{genResult}</span>}
      </div>
    </div>
  );
}

// ── 보안 설정 섹션 ─────────────────────────────────────────────────────
function SecuritySection() {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xl">🔒</span>
        <h2 className="text-sm font-semibold text-white">보안 설정</h2>
      </div>
      <div className="space-y-3 text-xs">
        <div className="flex justify-between items-center">
          <span className="text-slate-400">인증 방식</span>
          <span className="text-white">JWT (Bearer Token)</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-slate-400">토큰 유효 시간</span>
          <span className="text-white">24시간</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-slate-400">데모 계정</span>
          <span className="text-white font-mono">{process.env.NEXT_PUBLIC_DEMO_USERNAME ?? "admin"}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-slate-400">CORS 허용 도메인</span>
          <span className="text-white">{process.env.NEXT_PUBLIC_API_URL ? new URL(process.env.NEXT_PUBLIC_API_URL).host : "localhost:3000"}</span>
        </div>
        <p className="text-slate-600 text-[10px] pt-2 border-t border-slate-700 mt-2">
          ⚠️ 운영 배포 시 JWT_SECRET, DEMO_PASSWORD 환경변수를 반드시 변경하세요.
        </p>
      </div>
    </div>
  );
}

// ── API 연동 섹션 ─────────────────────────────────────────────────────
interface ApiKeyStatus {
  label: string;
  env: string;
  status: boolean;
}

function ApiIntegrationSection() {
  const [apiKeys, setApiKeys] = useState<ApiKeyStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${BASE_URL}/api/settings/api-keys`)
      .then((r) => r.json())
      .then((data: ApiKeyStatus[]) => setApiKeys(data))
      .catch(() => setApiKeys([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xl">🔗</span>
        <h2 className="text-sm font-semibold text-white">API 연동 현황</h2>
      </div>
      <div className="space-y-2 text-xs">
        {loading ? (
          <p className="text-slate-500">Loading...</p>
        ) : (
          apiKeys.map((k) => (
            <div key={k.label} className="flex justify-between items-center">
              <div>
                <span className="text-white">{k.label}</span>
                <span className="text-slate-600 ml-2">{k.env}</span>
              </div>
              <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${k.status ? "bg-green-500/10 text-green-400" : "bg-slate-700 text-slate-500"}`}>
                {k.status ? "설정됨" : "미설정"}
              </span>
            </div>
          ))
        )}
        <p className="text-slate-600 text-[10px] pt-2 border-t border-slate-700 mt-2">
          API 키는 ./API_KEY/ 디렉터리에서 관리됩니다.
        </p>
      </div>
    </div>
  );
}

// ── 메인 페이지 ──────────────────────────────────────────────────────
export default function SettingsPageClient() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-white">설정</h1>
        <p className="text-xs text-slate-500 mt-0.5">대시보드 설정 및 환경 구성</p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <AlertThresholdSection />
        <DataSyncSection />
        <SecuritySection />
        <ApiIntegrationSection />
      </div>
    </div>
  );
}
