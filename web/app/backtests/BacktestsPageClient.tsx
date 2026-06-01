// app/backtests/BacktestsPageClient.tsx
"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { APIRequestError, api } from "@/lib/api";
import type { BacktestDecision, BacktestPoint, BacktestPosition, BacktestTrade, BacktestRunRequest, BacktestRunResponse } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn, formatKRW } from "@/lib/utils";
import SectorComponentDiagnosticPanel from "./SectorComponentDiagnosticPanel";
import AICapexTokenDiagnosticPanel from "./AICapexTokenDiagnosticPanel";

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
        <div className="space-y-4">
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
          <SectorComponentDiagnosticPanel />
          <AICapexTokenDiagnosticPanel />
        </div>

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

      {latest && latest.positions.length > 0 && (
        <PositionsTable positions={latest.positions} />
      )}

      {latest && latest.decisions.length > 0 && (
        <DecisionLog decisions={latest.decisions} />
      )}

      {latest && latest.trades.length > 0 && (
        <TradesTable trades={latest.trades} />
      )}
    </div>
  );
}

function PositionsTable({ positions }: { positions: BacktestPosition[] }) {
  const dates = [...new Set(positions.map((p) => p.date))].sort().reverse();
  const [selectedDate, setSelectedDate] = useState<string>(dates[0] ?? "");
  const activeDate = dates.includes(selectedDate) ? selectedDate : dates[0] ?? "";
  const rows = positions.filter((p) => p.date === activeDate);

  return (
    <Card
      title="포지션 상세"
      extra={
        <select
          value={activeDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-200 outline-none focus:border-blue-500"
        >
          {dates.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-700 text-slate-500">
              <th className="px-3 py-2 text-left">자산코드</th>
              <th className="px-3 py-2 text-right">수량</th>
              <th className="px-3 py-2 text-right">가격</th>
              <th className="px-3 py-2 text-right">환율</th>
              <th className="px-3 py-2 text-right">평가금액(KRW)</th>
              <th className="px-3 py-2 text-right">비중(%)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/60">
            {rows.map((pos) => (
              <tr key={pos.assetCode}>
                <td className="px-3 py-2 font-mono text-sky-300">{pos.assetCode}</td>
                <td className="px-3 py-2 text-right text-slate-200">{pos.quantity.toFixed(4)}</td>
                <td className="px-3 py-2 text-right text-slate-300">{pos.price.toLocaleString()}</td>
                <td className="px-3 py-2 text-right text-slate-400">{pos.fxRate.toFixed(2)}</td>
                <td className="px-3 py-2 text-right text-white">{formatKRW(pos.marketValue)}</td>
                <td className="px-3 py-2 text-right text-slate-300">{(pos.weight * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function DecisionLog({ decisions }: { decisions: BacktestDecision[] }) {
  const dates = decisions.map((decision) => decision.date).sort().reverse();
  const [selectedDate, setSelectedDate] = useState<string>(dates[0] ?? "");
  const activeDate = dates.includes(selectedDate) ? selectedDate : dates[0] ?? "";
  const decision = decisions.find((item) => item.date === activeDate) ?? decisions[0];

  return (
    <Card
      title="Decision log"
      extra={
        <select
          value={activeDate}
          onChange={(e) => setSelectedDate(e.target.value)}
          className="rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-200 outline-none focus:border-blue-500"
        >
          {dates.map((date) => (
            <option key={date} value={date}>
              {date}
            </option>
          ))}
        </select>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[220px_minmax(0,1fr)]">
        <div className="rounded-md border border-slate-700 bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">Macro regime</p>
          <p className="mt-1 text-lg font-semibold text-white">{decision.macroRegime ?? "-"}</p>
          <p className="mt-1 text-sm text-slate-400">score {decision.macroScore ?? "-"}</p>
        </div>
        <div className="space-y-3">
          <WeightList title="Bucket weights" weights={decision.bucketWeights} />
          <WeightList title="Final weights" weights={decision.finalWeights} />
          {Object.keys(decision.bottleneckScores).length > 0 && (
            <WeightList title="Bottleneck scores" weights={decision.bottleneckScores} valueScale="score" />
          )}
        </div>
      </div>
      {decision.reasons.length > 0 && (
        <ul className="mt-4 grid gap-2 text-xs text-slate-300 md:grid-cols-2">
          {decision.reasons.slice(0, 8).map((reason, index) => (
            <li key={`${decision.date}-${index}`} className="rounded-md border border-slate-700 bg-slate-900/50 px-3 py-2">
              {reason}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function WeightList({
  title,
  weights,
  valueScale = "weight",
}: {
  title: string;
  weights: Record<string, number>;
  valueScale?: "weight" | "score";
}) {
  const rows = Object.entries(weights).sort((a, b) => b[1] - a[1]);
  return (
    <div>
      <p className="mb-2 text-xs font-semibold text-slate-400">{title}</p>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {rows.map(([key, value]) => (
          <div key={key} className="flex items-center justify-between gap-3 rounded-md border border-slate-700 bg-slate-900/60 px-3 py-2 text-xs">
            <span className="truncate font-mono text-sky-300">{key}</span>
            <span className="shrink-0 text-white">
              {valueScale === "score" ? value.toFixed(1) : `${(value * 100).toFixed(1)}%`}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TradesTable({ trades }: { trades: BacktestTrade[] }) {
  const SIDE_STYLE: Record<string, string> = {
    BUY: "text-green-300",
    SELL: "text-red-300",
  };

  return (
    <Card title={`거래 내역 (${trades.length}건)`}>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-slate-700 text-slate-500">
              <th className="px-3 py-2 text-left">날짜</th>
              <th className="px-3 py-2 text-left">자산코드</th>
              <th className="px-3 py-2 text-left">구분</th>
              <th className="px-3 py-2 text-right">수량</th>
              <th className="px-3 py-2 text-right">가격</th>
              <th className="px-3 py-2 text-right">순거래금액(KRW)</th>
              <th className="px-3 py-2 text-left">사유</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700/60">
            {trades.map((trade, index) => (
              <tr key={`${trade.date}-${trade.assetCode}-${index}`}>
                <td className="px-3 py-2 text-slate-400">{trade.date}</td>
                <td className="px-3 py-2 font-mono text-sky-300">{trade.assetCode}</td>
                <td className={cn("px-3 py-2 font-semibold", SIDE_STYLE[trade.side] ?? "text-slate-200")}>
                  {trade.side}
                </td>
                <td className="px-3 py-2 text-right text-slate-200">{trade.quantity.toFixed(4)}</td>
                <td className="px-3 py-2 text-right text-slate-300">{trade.price.toLocaleString()}</td>
                <td className="px-3 py-2 text-right text-white">{formatKRW(trade.netAmount)}</td>
                <td className="px-3 py-2 text-slate-400">{trade.reason ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
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
