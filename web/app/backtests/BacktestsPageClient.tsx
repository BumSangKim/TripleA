// app/backtests/BacktestsPageClient.tsx
"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { APIRequestError, api } from "@/lib/api";
import type { BacktestPoint, BacktestRunRequest, BacktestRunResponse } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn, formatKRW } from "@/lib/utils";

type Frequency = BacktestRunRequest["rebalanceFrequency"];

const FREQUENCY_OPTIONS: { value: Frequency; label: string }[] = [
  { value: "monthly", label: "월간" },
  { value: "quarterly", label: "분기" },
  { value: "weekly", label: "주간" },
];

const RISK_PROFILE_OPTIONS: { value: BacktestRunRequest["riskProfile"]; label: string }[] = [
  { value: "balanced", label: "Balanced" },
  { value: "aggressive", label: "Aggressive" },
  { value: "defensive", label: "Defensive" },
];

function getErrorMessage(error: unknown): string {
  if (error instanceof APIRequestError && error.detail?.userAction) {
    return `${error.message} ${error.detail.userAction}`;
  }
  return error instanceof Error ? error.message : String(error);
}

function parseAmount(value: string): number {
  return Number(value.replaceAll(",", "").trim());
}

function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function shortDate(value: string): string {
  return value.slice(2).replaceAll("-", ".");
}

export default function BacktestsPageClient() {
  const [name, setName] = useState("Core allocation");
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("2024-12-31");
  const [initialCapital, setInitialCapital] = useState("100000000");
  const [strategyMode] = useState<BacktestRunRequest["strategyMode"]>("triplea_dynamic");
  const [riskProfile, setRiskProfile] = useState<BacktestRunRequest["riskProfile"]>("balanced");
  const [universeId] = useState<BacktestRunRequest["universeId"]>("default_global");
  const [frequency, setFrequency] = useState<Frequency>("monthly");
  const [feeBps, setFeeBps] = useState("5");
  const [slippageBps, setSlippageBps] = useState("5");
  const [taxBps, setTaxBps] = useState("0");
  const [dataLookbackYears, setDataLookbackYears] = useState("5");
  const [latest, setLatest] = useState<BacktestRunResponse | null>(null);
  const [runs, setRuns] = useState<BacktestRunResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const result = await api.getBacktestRuns(12);
      setRuns(result);
      setLatest((current) => current ?? result[0] ?? null);
    } catch {
      setRuns([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(fetchHistory, 0);
    return () => window.clearTimeout(timer);
  }, [fetchHistory]);


  const handleRun = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const capital = parseAmount(initialCapital);
      const payload: BacktestRunRequest = {
        name,
        startDate,
        endDate,
        initialCapital: capital,
        strategyMode,
        riskProfile,
        universeId,
        rebalanceFrequency: frequency,
        baseCurrency: "KRW",
        feeBps: Number(feeBps),
        slippageBps: Number(slippageBps),
        taxBps: Number(taxBps),
        dataLookbackYears: Number(dataLookbackYears),
      };
      const result = await api.runBacktest(payload);
      setLatest(result);
      await fetchHistory();
      setMsg({ type: "ok", text: `백테스트 #${result.runId} 저장 완료` });
    } catch (error) {
      setMsg({ type: "err", text: getErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  };

  const initialAmount = parseAmount(initialCapital);
  const costInputs = [feeBps, slippageBps, taxBps].map((value) => Number(value));
  const lookbackYears = Number(dataLookbackYears);
  const canRun = !loading
    && Number.isFinite(initialAmount)
    && initialAmount > 0
    && costInputs.every((value) => Number.isFinite(value) && value >= 0)
    && Number.isFinite(lookbackYears)
    && lookbackYears >= 1;

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">백테스트</h1>
          <p className="mt-1 text-sm text-slate-400">BacktestProvider · 결과 저장 · 주문 차단</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-md border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200">
            BACKTEST
          </span>
          <button
            type="button"
            onClick={handleRun}
            disabled={!canRun}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
          >
            {loading ? "실행 중..." : "실행"}
          </button>
        </div>
      </div>

      {msg && (
        <div
          className={cn(
            "rounded-md px-4 py-2 text-sm",
            msg.type === "ok" ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300",
          )}
        >
          {msg.text}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
        <Card title="조건">
          <div className="space-y-4">
            <label className="block">
              <span className="text-xs text-slate-400">이름</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-xs text-slate-400">시작일</span>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">종료일</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500"
                />
              </label>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-xs text-slate-400">전략 모드</span>
                <select
                  value={strategyMode}
                  disabled
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none disabled:text-slate-500"
                >
                  <option value="triplea_dynamic">TripleA Dynamic</option>
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">위험 프로파일</span>
                <select
                  value={riskProfile}
                  onChange={(e) => setRiskProfile(e.target.value as BacktestRunRequest["riskProfile"])}
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500"
                >
                  {RISK_PROFILE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">투자 유니버스</span>
                <select
                  value={universeId}
                  disabled
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none disabled:text-slate-500"
                >
                  <option value="default_global">default_global</option>
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">초기자본</span>
                <input
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(e.target.value)}
                  inputMode="numeric"
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">주기</span>
                <select
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value as Frequency)}
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500"
                >
                  {FREQUENCY_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <span className="text-xs text-slate-400">수수료 bps</span>
                <input
                  value={feeBps}
                  onChange={(e) => setFeeBps(e.target.value)}
                  inputMode="decimal"
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">슬리피지 bps</span>
                <input
                  value={slippageBps}
                  onChange={(e) => setSlippageBps(e.target.value)}
                  inputMode="decimal"
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">세금 bps</span>
                <input
                  value={taxBps}
                  onChange={(e) => setTaxBps(e.target.value)}
                  inputMode="decimal"
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500"
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-400">데이터 룩백</span>
                <input
                  value={dataLookbackYears}
                  onChange={(e) => setDataLookbackYears(e.target.value)}
                  inputMode="numeric"
                  className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500"
                />
              </label>
            </div>
          </div>
        </Card>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
            <Metric label="총수익률" value={latest ? formatPercent(latest.totalReturn) : "-"} tone={latest ? (latest.totalReturn >= 0 ? "good" : "bad") : "neutral"} />
            <Metric label="연환산" value={latest ? formatPercent(latest.annualReturn) : "-"} tone={latest ? (latest.annualReturn >= 0 ? "good" : "bad") : "neutral"} />
            <Metric label="MDD" value={latest ? `${latest.maxDrawdown.toFixed(2)}%` : "-"} tone="warn" />
            <Metric label="변동성" value={latest ? `${latest.volatility.toFixed(2)}%` : "-"} />
          </div>

          <Card
            title="자산곡선"
            extra={latest ? `${shortDate(latest.startDate)} - ${shortDate(latest.endDate)}` : "대기"}
          >
            <EquityCurve points={latest?.points ?? []} />
          </Card>

          <Card title="Drawdown">
            <DrawdownCurve points={latest?.points ?? []} />
          </Card>
        </div>
      </div>

      <Card title="실행 이력">
        {historyLoading ? (
          <div className="py-8 text-center text-sm text-slate-500">이력 로딩 중...</div>
        ) : runs.length === 0 ? (
          <div className="py-8 text-center text-sm text-slate-500">저장된 백테스트가 없습니다.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-700 text-slate-500">
                  <th className="px-3 py-2 text-left">ID</th>
                  <th className="px-3 py-2 text-left">이름</th>
                  <th className="px-3 py-2 text-left">기간</th>
                  <th className="px-3 py-2 text-right">초기자본</th>
                  <th className="px-3 py-2 text-right">총수익률</th>
                  <th className="px-3 py-2 text-right">MDD</th>
                  <th className="px-3 py-2 text-left">선택</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60">
                {runs.map((run) => (
                  <tr key={run.runId}>
                    <td className="px-3 py-2 text-white">{run.runId}</td>
                    <td className="px-3 py-2 text-slate-200">{run.name}</td>
                    <td className="px-3 py-2 text-slate-300">
                      {shortDate(run.startDate)} - {shortDate(run.endDate)}
                    </td>
                    <td className="px-3 py-2 text-right text-slate-300">{formatKRW(run.initialCapital)}</td>
                    <td className={cn("px-3 py-2 text-right font-semibold", run.totalReturn >= 0 ? "text-green-300" : "text-red-300")}>
                      {formatPercent(run.totalReturn)}
                    </td>
                    <td className="px-3 py-2 text-right text-amber-300">{run.maxDrawdown.toFixed(2)}%</td>
                    <td className="px-3 py-2">
                      <button
                        type="button"
                        onClick={() => setLatest(run)}
                        className="rounded-md bg-slate-700 px-2 py-1 text-xs text-slate-200 transition-colors hover:bg-slate-600"
                      >
                        보기
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "good" | "bad" | "warn" | "neutral" }) {
  const color = {
    good: "text-green-300",
    bad: "text-red-300",
    warn: "text-amber-300",
    neutral: "text-white",
  }[tone];
  return (
    <Card>
      <p className="text-xs text-slate-400">{label}</p>
      <p className={cn("mt-1 text-xl font-bold", color)}>{value}</p>
    </Card>
  );
}

function EquityCurve({ points }: { points: BacktestPoint[] }) {
  return (
    <ChartShell emptyText="실행 결과가 없습니다.">
      <LineChart
        points={points.map((point) => ({ x: point.date, y: point.value }))}
        valueFormatter={formatKRW}
        stroke="#38bdf8"
      />
    </ChartShell>
  );
}

function DrawdownCurve({ points }: { points: BacktestPoint[] }) {
  return (
    <ChartShell emptyText="Drawdown 데이터가 없습니다.">
      <LineChart
        points={points.map((point) => ({ x: point.date, y: point.drawdown }))}
        valueFormatter={(value) => `${value.toFixed(2)}%`}
        stroke="#f59e0b"
        forceZeroTop
      />
    </ChartShell>
  );
}

function ChartShell({ children, emptyText }: { children: ReactNode; emptyText: string }) {
  if (!children) {
    return <div className="flex h-72 items-center justify-center text-sm text-slate-500">{emptyText}</div>;
  }
  return <div className="h-72 w-full">{children}</div>;
}

function LineChart({
  points,
  valueFormatter,
  stroke,
  forceZeroTop = false,
}: {
  points: { x: string; y: number }[];
  valueFormatter: (value: number) => string;
  stroke: string;
  forceZeroTop?: boolean;
}) {
  if (points.length === 0) {
    return <div className="flex h-full items-center justify-center text-sm text-slate-500">데이터 없음</div>;
  }

  const width = 760;
  const height = 260;
  const padLeft = 72;
  const padRight = 20;
  const padTop = 18;
  const padBottom = 36;
  const values = points.map((point) => point.y);
  const minValue = Math.min(...values);
  const maxValue = forceZeroTop ? 0 : Math.max(...values);
  const range = Math.max(maxValue - minValue, Math.abs(maxValue) * 0.01, 1);
  const xStep = points.length > 1 ? (width - padLeft - padRight) / (points.length - 1) : 0;
  const yFor = (value: number) => padTop + ((maxValue - value) / range) * (height - padTop - padBottom);
  const polyline = points
    .map((point, index) => `${padLeft + index * xStep},${yFor(point.y)}`)
    .join(" ");
  const first = points[0];
  const last = points[points.length - 1];
  const midIndex = Math.floor((points.length - 1) / 2);
  const mid = points[midIndex];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full" role="img">
      {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
        const y = padTop + ratio * (height - padTop - padBottom);
        const value = maxValue - ratio * range;
        return (
          <g key={ratio}>
            <line x1={padLeft} y1={y} x2={width - padRight} y2={y} stroke="#334155" strokeWidth="1" />
            <text x={8} y={y + 4} fill="#94a3b8" fontSize="11">
              {valueFormatter(value)}
            </text>
          </g>
        );
      })}
      <polyline points={polyline} fill="none" stroke={stroke} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
      {[first, mid, last].map((point, index) => (
        <text
          key={`${point.x}-${index}`}
          x={padLeft + (index === 0 ? 0 : index === 1 ? midIndex * xStep : (points.length - 1) * xStep)}
          y={height - 10}
          fill="#64748b"
          fontSize="11"
          textAnchor={index === 0 ? "start" : index === 1 ? "middle" : "end"}
        >
          {shortDate(point.x)}
        </text>
      ))}
    </svg>
  );
}
