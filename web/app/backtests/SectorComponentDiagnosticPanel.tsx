"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { APIRequestError, api } from "@/lib/api";
import type {
  SectorComponentRunResponse,
  SectorComponentScopePayload,
  SectorComponentSectorOption,
  SectorComponentUiMetadataResponse,
  SectorComponentWarning,
} from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";

function getErrorMessage(error: unknown): string {
  if (error instanceof APIRequestError && error.detail?.userAction) {
    return `${error.message} ${error.detail.userAction}`;
  }
  return error instanceof Error ? error.message : String(error);
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatWeight(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${(value * 100).toFixed(1)}%`;
}

function warningLabel(warning: SectorComponentWarning): string {
  const code = typeof warning.code === "string" ? warning.code : "WARNING";
  const message = typeof warning.message === "string" ? warning.message : "";
  if (message.startsWith(`${code}:`)) {
    return message;
  }
  return message ? `${code}: ${message}` : code;
}

function statusTone(status: string): string {
  return status === "OK"
    ? "border-green-500/30 bg-green-500/10 text-green-200"
    : "border-amber-500/30 bg-amber-500/10 text-amber-200";
}

export default function SectorComponentDiagnosticPanel() {
  const [metadata, setMetadata] = useState<SectorComponentUiMetadataResponse | null>(null);
  const [selectedValue, setSelectedValue] = useState("ALL");
  const [result, setResult] = useState<SectorComponentRunResponse | null>(null);
  const [loadingMetadata, setLoadingMetadata] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMetadata = useCallback(async () => {
    setLoadingMetadata(true);
    setError(null);
    try {
      const nextMetadata = await api.getSectorComponentUiMetadata();
      setMetadata(nextMetadata);
      setSelectedValue(nextMetadata.allSectorOption.value);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoadingMetadata(false);
    }
  }, []);

  useEffect(() => {
    const id = window.setTimeout(loadMetadata, 0);
    return () => window.clearTimeout(id);
  }, [loadMetadata]);

  const selectedScope = useMemo<SectorComponentScopePayload | null>(() => {
    if (!metadata) {
      return null;
    }
    if (selectedValue === metadata.allSectorOption.value) {
      return metadata.allSectorOption.sectorScope;
    }
    const selectedSector = metadata.sectorOptions.find((option) => option.value === selectedValue);
    return selectedSector ? { mode: "single", sectorId: selectedSector.sectorId } : null;
  }, [metadata, selectedValue]);

  const selectedOption = useMemo<SectorComponentSectorOption | null>(() => {
    if (!metadata || selectedValue === metadata.allSectorOption.value) {
      return null;
    }
    return metadata.sectorOptions.find((option) => option.value === selectedValue) ?? null;
  }, [metadata, selectedValue]);

  const handleRun = async () => {
    if (!selectedScope) {
      setError("선택 가능한 섹터 범위가 없습니다.");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const nextResult = await api.runSectorComponentBacktest({ sectorScope: selectedScope });
      setResult(nextResult);
    } catch (runError) {
      setError(getErrorMessage(runError));
    } finally {
      setRunning(false);
    }
  };

  const warnings = [...(metadata?.warnings ?? []), ...(result?.warnings ?? [])];
  const reasonCodes = [...(metadata?.reasonCodes ?? []), ...(result?.reasonCodes ?? [])];
  const canRun = Boolean(selectedScope) && !loadingMetadata && !running;

  return (
    <Card
      title="섹터 컴포넌트 진단"
      extra={metadata ? `${metadata.parameterVersion} · ${metadata.modelVersion}` : "대기"}
    >
      <div className="space-y-4">
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
          <label className="block">
            <span className="text-xs text-slate-400">섹터 범위</span>
            <select
              value={selectedValue}
              onChange={(event) => setSelectedValue(event.target.value)}
              disabled={!metadata || loadingMetadata || running}
              className="mt-1 h-9 w-full rounded-md border border-slate-600 bg-slate-900 px-3 text-sm text-white outline-none focus:border-blue-500 disabled:text-slate-500"
            >
              {metadata ? (
                <>
                  <option value={metadata.allSectorOption.value}>{metadata.allSectorOption.label}</option>
                  {metadata.sectorOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </>
              ) : (
                <option value="ALL">전체 섹터</option>
              )}
            </select>
          </label>
          <button
            type="button"
            onClick={handleRun}
            disabled={!canRun}
            className="self-end rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
          >
            {running ? "검증 중..." : "검증"}
          </button>
        </div>

        {error && (
          <div className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
            {error}
          </div>
        )}

        {result && (
          <div className={cn("rounded-md border px-3 py-2 text-sm", statusTone(result.status))}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">상태 {result.status}</span>
              <span className="text-xs opacity-80">{result.semantics}</span>
            </div>
          </div>
        )}

        {selectedOption && (
          <div className="rounded-md border border-slate-700 bg-slate-900/50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-xs text-slate-500">Reference portfolio</p>
                <p className="font-mono text-sm text-slate-200">{selectedOption.portfolioId}</p>
              </div>
              <span className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-300">
                {selectedOption.assetCount} assets
              </span>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {selectedOption.assets.slice(0, 8).map((asset) => (
                <div key={asset.assetCode} className="rounded border border-slate-700 bg-slate-950/40 px-2 py-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-sky-300">{asset.assetCode}</span>
                    <span className="text-slate-200">{formatWeight(asset.weight)}</span>
                  </div>
                  <div className="mt-1 truncate text-slate-400">{asset.name ?? asset.role}</div>
                  <div className="mt-1 text-slate-500">{asset.category ?? "-"} · {asset.market ?? "-"}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500">
                <th className="px-3 py-2 text-left">섹터</th>
                <th className="px-3 py-2 text-left">상태</th>
                <th className="px-3 py-2 text-right">총수익률</th>
                <th className="px-3 py-2 text-right">MDD</th>
                <th className="px-3 py-2 text-right">변동성</th>
                <th className="px-3 py-2 text-right">Hit rate</th>
                <th className="px-3 py-2 text-right">관측치</th>
                <th className="px-3 py-2 text-right">경고</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60">
              {(result?.comparisonRows ?? []).map((row) => (
                <tr key={row.sectorId}>
                  <td className="px-3 py-2">
                    <div className="font-semibold text-slate-200">{row.displayName}</div>
                    <div className="font-mono text-[11px] text-slate-500">{row.portfolioId}</div>
                  </td>
                  <td className="px-3 py-2">
                    <span className={cn("rounded border px-2 py-1", statusTone(row.status))}>{row.status}</span>
                  </td>
                  <td className="px-3 py-2 text-right text-slate-200">{formatPercent(row.totalReturn)}</td>
                  <td className="px-3 py-2 text-right text-amber-300">{formatPercent(row.maxDrawdown)}</td>
                  <td className="px-3 py-2 text-right text-slate-300">{formatPercent(row.volatility)}</td>
                  <td className="px-3 py-2 text-right text-slate-300">{formatPercent(row.hitRate)}</td>
                  <td className="px-3 py-2 text-right text-slate-400">{row.observationCount}</td>
                  <td className="px-3 py-2 text-right text-slate-400">{row.warningCount}</td>
                </tr>
              ))}
              {!result && (
                <tr>
                  <td colSpan={8} className="px-3 py-8 text-center text-slate-500">
                    섹터 범위를 선택하고 검증을 시작하세요.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <AuditList title="Reason codes" items={reasonCodes} emptyText="기록된 reason code가 없습니다." />
          <AuditList title="Warnings" items={warnings.map(warningLabel)} emptyText="표시할 warning이 없습니다." />
        </div>

        {result && (
          <div className="grid gap-2 rounded-md border border-slate-700 bg-slate-900/50 p-3 text-xs text-slate-400 sm:grid-cols-3">
            <div>
              <span className="block text-slate-500">Snapshot</span>
              <span className="font-mono text-slate-200">{result.dataSnapshotId}</span>
            </div>
            <div>
              <span className="block text-slate-500">Parameter</span>
              <span className="font-mono text-slate-200">{result.parameterVersion}</span>
            </div>
            <div>
              <span className="block text-slate-500">Model</span>
              <span className="font-mono text-slate-200">{result.modelVersion}</span>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function AuditList({ title, items, emptyText }: { title: string; items: string[]; emptyText: string }) {
  return (
    <div className="rounded-md border border-slate-700 bg-slate-900/50 p-3">
      <p className="text-xs font-semibold text-slate-400">{title}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-xs text-slate-500">{emptyText}</p>
      ) : (
        <ul className="mt-2 space-y-1 text-xs text-slate-300">
          {[...new Set(items)].slice(0, 8).map((item) => (
            <li key={item} className="break-all font-mono">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
