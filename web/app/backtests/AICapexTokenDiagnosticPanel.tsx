"use client";

import { useState } from "react";
import { APIRequestError, api } from "@/lib/api";
import type { AICapexTokenDiagnosticResponse, AICapexTokenDiagnosticRow } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";

function getErrorMessage(error: unknown): string {
  if (error instanceof APIRequestError && error.detail?.userAction) {
    return `${error.message} ${error.detail.userAction}`;
  }
  return error instanceof Error ? error.message : String(error);
}

function formatRatio(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function statusTone(status: string): string {
  return status === "DIAGNOSTIC_ONLY"
    ? "border-sky-500/30 bg-sky-500/10 text-sky-200"
    : "border-amber-500/30 bg-amber-500/10 text-amber-200";
}

export default function AICapexTokenDiagnosticPanel() {
  const [result, setResult] = useState<AICapexTokenDiagnosticResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    try {
      setResult(await api.runAICapexTokenDiagnostic());
    } catch (runError) {
      setError(getErrorMessage(runError));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Card
      title="AI Capex-Token 진단"
      extra={result ? `${result.parameterVersion} · ${result.modelVersion}` : "diagnostic-only"}
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1 text-xs text-slate-400">
            <p>fixture 기반 입력부터 diagnostic score까지 검증합니다.</p>
            <p>Production gate는 닫혀 있으며 백테스트/주문 경로에 적용하지 않습니다.</p>
          </div>
          <button
            type="button"
            onClick={handleRun}
            disabled={running}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
          >
            {running ? "검증 중..." : "AI 진단 검증"}
          </button>
        </div>

        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {error}
          </div>
        )}

        {result && (
          <>
            <div className={cn("rounded-md border px-3 py-2 text-sm", statusTone(result.status))}>
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold">{result.status}</span>
                <span className="text-xs opacity-80">
                  productionReady={String(result.productionReady)}
                </span>
              </div>
            </div>

            <div className="grid gap-2 text-xs sm:grid-cols-2">
              <GateItem label="enabled" value={result.productionGate.enabled} />
              <GateItem label="productionEnabled" value={result.productionGate.productionEnabled} />
              <GateItem label="approved" value={result.productionGate.approved} />
              <GateItem label="backtest pass required" value={result.productionGate.requiresBacktestPass} />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-700 text-slate-500">
                    <th className="px-3 py-2 text-left">Fixture</th>
                    <th className="px-3 py-2 text-left">Scenario</th>
                    <th className="px-3 py-2 text-left">Status</th>
                    <th className="px-3 py-2 text-right">Components</th>
                    <th className="px-3 py-2 text-right">Confidence</th>
                    <th className="px-3 py-2 text-right">Quality</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/60">
                  {result.scenarioRows.map((row) => (
                    <ScenarioRow key={row.fixtureId} row={row} />
                  ))}
                </tbody>
              </table>
            </div>

            <div className="rounded-md border border-slate-700 bg-slate-900/50 p-3 text-xs">
              <p className="font-semibold text-slate-400">Reason codes</p>
              <p className="mt-2 break-all font-mono text-slate-300">
                {result.reasonCodes.slice(0, 10).join(", ") || "-"}
              </p>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

function GateItem({ label, value }: { label: string; value: boolean }) {
  return (
    <div className="rounded-md border border-slate-700 bg-slate-900/50 px-3 py-2">
      <span className="text-slate-500">{label}</span>
      <span className={cn("ml-2 font-mono", value ? "text-amber-300" : "text-green-300")}>{String(value)}</span>
    </div>
  );
}

function ScenarioRow({ row }: { row: AICapexTokenDiagnosticRow }) {
  return (
    <tr>
      <td className="px-3 py-2">
        <div className="font-mono text-sky-300">{row.fixtureId}</div>
        <div className="text-[11px] text-slate-500">{row.snapshotId}</div>
      </td>
      <td className="px-3 py-2 text-slate-200">
        {row.dominantScenario ?? row.intendedScenario ?? "-"}
      </td>
      <td className="px-3 py-2">
        <span className={cn("rounded border px-2 py-1", statusTone(row.status))}>{row.status}</span>
      </td>
      <td className="px-3 py-2 text-right text-slate-300">{row.componentCount}</td>
      <td className="px-3 py-2 text-right text-slate-300">{formatRatio(row.maxConfidence)}</td>
      <td className="px-3 py-2 text-right text-slate-300">{formatRatio(row.minDataQuality)}</td>
    </tr>
  );
}
