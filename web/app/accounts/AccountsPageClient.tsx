// app/accounts/AccountsPageClient.tsx
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { APIRequestError, api, BASE_URL } from "@/lib/api";
import type {
  AccountPolicyItem,
  AccountSnapshotCreate,
  AccountSnapshotItem,
  AccountSummary,
  ModeInfo,
  RebalanceResultItem,
  TradingMode,
} from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn, formatKRW } from "@/lib/utils";

const MODE_OPTIONS: { value: TradingMode; label: string }[] = [
  { value: "mock", label: "Mock" },
  { value: "test", label: "Test" },
  { value: "backtest", label: "Backtest" },
  { value: "paper", label: "Paper" },
  { value: "live", label: "Live" },
];

type SnapshotField =
  | "totalValue"
  | "cashValue"
  | "domesticStockValue"
  | "foreignStockValue"
  | "bondValue"
  | "etfValue"
  | "pensionValue"
  | "altValue";

type SnapshotFormState = Record<SnapshotField, string>;

const SNAPSHOT_FIELDS: { key: SnapshotField; label: string }[] = [
  { key: "totalValue", label: "총자산" },
  { key: "cashValue", label: "현금" },
  { key: "domesticStockValue", label: "국내주식" },
  { key: "foreignStockValue", label: "해외주식" },
  { key: "bondValue", label: "채권" },
  { key: "etfValue", label: "ETF" },
  { key: "pensionValue", label: "연금" },
  { key: "altValue", label: "대체" },
];

const EMPTY_SNAPSHOT_FORM: SnapshotFormState = {
  totalValue: "",
  cashValue: "",
  domesticStockValue: "",
  foreignStockValue: "",
  bondValue: "",
  etfValue: "",
  pensionValue: "",
  altValue: "",
};

interface Position {
  id: number;
  ticker: string;
  name: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  market_value: number;
  profit: number;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof APIRequestError && error.detail?.userAction) {
    return `${error.message} ${error.detail.userAction}`;
  }
  return error instanceof Error ? error.message : String(error);
}

function canSyncProvider(modeInfo: ModeInfo | null): boolean {
  return modeInfo !== null;
}

function parseMoney(value: string): number {
  const parsed = Number(value.replaceAll(",", "").trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatDateTime(value?: string | null): string {
  if (!value) return "-";
  const normalized = value.includes("T") ? value : value.replace(" ", "T");
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function actionLabel(action: string): string {
  const labels: Record<string, string> = {
    HOLD: "관망",
    INCREASE: "확대",
    REDUCE: "축소",
  };
  return labels[action] ?? action;
}

function modeCanWrite(mode: TradingMode, modeInfo: ModeInfo | null): boolean {
  if (modeInfo) return modeInfo.canWriteUserData;
  return mode !== "mock" && mode !== "test";
}

export default function AccountsPageClient() {
  const [mode, setMode] = useState<TradingMode>("paper");
  const [modeInfo, setModeInfo] = useState<ModeInfo | null>(null);
  const [accounts, setAccounts] = useState<AccountSummary[]>([]);
  const [policies, setPolicies] = useState<AccountPolicyItem[]>([]);
  const [rebalanceResults, setRebalanceResults] = useState<RebalanceResultItem[]>([]);
  const [snapshots, setSnapshots] = useState<AccountSnapshotItem[]>([]);
  const [snapshotForm, setSnapshotForm] = useState<SnapshotFormState>(EMPTY_SNAPSHOT_FORM);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<number | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [posLoading, setPosLoading] = useState(false);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotSaving, setSnapshotSaving] = useState(false);
  const [rebalanceRunning, setRebalanceRunning] = useState(false);
  const [providerSyncing, setProviderSyncing] = useState(false);
  const [toggleBusyId, setToggleBusyId] = useState<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [snapshotMsg, setSnapshotMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [rebalanceMsg, setRebalanceMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [providerMsg, setProviderMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const canWrite = modeCanWrite(mode, modeInfo);
  const canSync = canSyncProvider(modeInfo);
  const selectedAccount = useMemo(
    () => accounts.find((account) => account.id === selected) ?? null,
    [accounts, selected],
  );
  const policyByType = useMemo(
    () => new Map(policies.map((policy) => [policy.accountType, policy])),
    [policies],
  );

  const fetchAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getDashboardSummary(mode);
      setAccounts(data.accounts ?? []);
      setModeInfo(data.modeInfo ?? null);
    } catch {
      setAccounts([]);
      setModeInfo(null);
    } finally {
      setLoading(false);
    }
  }, [mode]);

  const fetchPolicies = useCallback(async () => {
    try {
      setPolicies(await api.getAccountPolicies());
    } catch {
      setPolicies([]);
    }
  }, []);

  const fetchRebalanceResults = useCallback(async () => {
    try {
      setRebalanceResults(await api.getRebalanceResults(mode, 12));
    } catch {
      setRebalanceResults([]);
    }
  }, [mode]);

  const loadAccountDetails = useCallback(async (accountId: number) => {
    setPosLoading(true);
    setSnapshotLoading(true);
    try {
      const [positionResult, snapshotResult] = await Promise.allSettled([
        fetch(`${BASE_URL}/api/accounts/${accountId}/positions`).then(async (res) => {
          if (!res.ok) throw new Error("positions request failed");
          return res.json() as Promise<Position[]>;
        }),
        api.getAccountSnapshots(accountId, 8),
      ]);

      setPositions(positionResult.status === "fulfilled" ? positionResult.value : []);
      setSnapshots(snapshotResult.status === "fulfilled" ? snapshotResult.value : []);
    } finally {
      setPosLoading(false);
      setSnapshotLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchAccounts();
      fetchPolicies();
      fetchRebalanceResults();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchAccounts, fetchPolicies, fetchRebalanceResults]);

  const handleSelectAccount = async (id: number) => {
    if (selected === id) {
      setSelected(null);
      setPositions([]);
      setSnapshots([]);
      setSnapshotForm(EMPTY_SNAPSHOT_FORM);
      return;
    }
    const account = accounts.find((item) => item.id === id);
    setSelected(id);
    setSnapshotForm({
      ...EMPTY_SNAPSHOT_FORM,
      totalValue: account?.value ? String(Math.round(account.value)) : "",
    });
    setSnapshotMsg(null);
    await loadAccountDetails(id);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!canWrite) {
      setUploadMsg({ type: "err", text: `${mode} 모드에서는 업로드를 저장할 수 없습니다.` });
      if (fileRef.current) fileRef.current.value = "";
      return;
    }

    setUploading(true);
    setUploadMsg(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${BASE_URL}/api/accounts/upload-csv?mode=${mode}`, {
        method: "POST",
        body: form,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail ?? "업로드 실패");
      setUploadMsg({ type: "ok", text: `${data.inserted}개 종목 업로드 완료` });
      await fetchAccounts();
    } catch (error) {
      setUploadMsg({ type: "err", text: getErrorMessage(error) });
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const handleToggleInclusion = async (
    account: AccountSummary,
    e: React.MouseEvent<HTMLButtonElement>,
  ) => {
    e.stopPropagation();
    if (!canWrite) {
      setUploadMsg({ type: "err", text: `${mode} 모드에서는 계좌 설정을 저장할 수 없습니다.` });
      return;
    }
    setToggleBusyId(account.id);
    try {
      await api.setAccountRebalancingInclusion(account.id, !account.includeInRebalancing, mode);
      await fetchAccounts();
    } catch (error) {
      setUploadMsg({ type: "err", text: getErrorMessage(error) });
    } finally {
      setToggleBusyId(null);
    }
  };

  const handleSnapshotSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedAccount || snapshotSaving) return;
    if (!canWrite) {
      setSnapshotMsg({ type: "err", text: `${mode} 모드에서는 스냅샷을 저장할 수 없습니다.` });
      return;
    }

    const payload: AccountSnapshotCreate = {
      totalValue: parseMoney(snapshotForm.totalValue),
      cashValue: parseMoney(snapshotForm.cashValue),
      domesticStockValue: parseMoney(snapshotForm.domesticStockValue),
      foreignStockValue: parseMoney(snapshotForm.foreignStockValue),
      bondValue: parseMoney(snapshotForm.bondValue),
      etfValue: parseMoney(snapshotForm.etfValue),
      pensionValue: parseMoney(snapshotForm.pensionValue),
      altValue: parseMoney(snapshotForm.altValue),
    };

    if (payload.totalValue <= 0) {
      setSnapshotMsg({ type: "err", text: "총자산을 0보다 크게 입력하세요." });
      return;
    }

    setSnapshotSaving(true);
    setSnapshotMsg(null);
    try {
      await api.createManualSnapshot(selectedAccount.id, mode, payload);
      setSnapshotMsg({ type: "ok", text: "수동 스냅샷 저장 완료" });
      await Promise.all([fetchAccounts(), loadAccountDetails(selectedAccount.id)]);
    } catch (error) {
      setSnapshotMsg({ type: "err", text: getErrorMessage(error) });
    } finally {
      setSnapshotSaving(false);
    }
  };

  const handleRunRebalancing = async () => {
    if (!canWrite) {
      setRebalanceMsg({ type: "err", text: `${mode} 모드에서는 리밸런싱 결과를 저장할 수 없습니다.` });
      return;
    }
    setRebalanceRunning(true);
    setRebalanceMsg(null);
    try {
      const result = await api.runRebalancing(mode);
      setRebalanceMsg({ type: "ok", text: `run ${result.runId}에 ${result.saved}건 저장` });
      await fetchRebalanceResults();
    } catch (error) {
      setRebalanceMsg({ type: "err", text: getErrorMessage(error) });
    } finally {
      setRebalanceRunning(false);
    }
  };

  const handleProviderSync = async () => {
    if (!canSync) {
      setProviderMsg({ type: "err", text: "현재 모드 정보를 불러온 뒤 다시 시도하세요." });
      return;
    }

    setProviderSyncing(true);
    setProviderMsg(null);
    try {
      const result = await api.syncProviderAccounts(mode);
      const accountLabel = result.accountMasked ? ` (${result.accountMasked})` : "";
      setProviderMsg({
        type: "ok",
        text: `${result.provider} 동기화 완료${accountLabel}: ${result.syncedPositions}개 종목, 총 ${formatKRW(result.totalValue)}`,
      });
      await Promise.all([fetchAccounts(), fetchRebalanceResults()]);
      if (result.accountId) {
        setSelected(result.accountId);
        await loadAccountDetails(result.accountId);
      }
    } catch (error) {
      setProviderMsg({
        type: "err",
        text: `계좌 동기화 실패: ${getErrorMessage(error)}`,
      });
    } finally {
      setProviderSyncing(false);
    }
  };

  const totalValue = accounts.reduce((sum, account) => sum + account.value, 0);
  const totalProfit = accounts.reduce((sum, account) => sum + account.profit, 0);
  const includedAccounts = accounts.filter((account) => account.includeInRebalancing !== false).length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">계좌 현황</h1>
          <p className="text-sm text-slate-400">모드별 계좌 데이터, 정책, 리밸런싱 로그</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={mode}
            onChange={(e) => {
              setMode(e.target.value as TradingMode);
              setSelected(null);
              setPositions([]);
              setSnapshots([]);
              setSnapshotForm(EMPTY_SNAPSHOT_FORM);
              setUploadMsg(null);
              setSnapshotMsg(null);
              setRebalanceMsg(null);
              setProviderMsg(null);
            }}
            className="h-9 rounded-md border border-slate-600 bg-slate-800 px-3 text-sm text-white outline-none focus:border-blue-500"
          >
            {MODE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={handleProviderSync}
            disabled={providerSyncing || !canSync}
            className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
          >
            {providerSyncing ? "동기화 중..." : "계좌 동기화"}
          </button>
          <label className={cn(
            "cursor-pointer rounded-md px-3 py-2 text-sm font-medium transition-colors",
            uploading || !canWrite
              ? "bg-slate-700 text-slate-500"
              : "bg-blue-600 text-white hover:bg-blue-700",
          )}>
            {uploading ? "업로드 중..." : "CSV 업로드"}
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={handleUpload}
              disabled={uploading || !canWrite}
            />
          </label>
          <a
            href="data:text/csv;charset=utf-8,account_name,ticker,name,quantity,avg_price,current_price%0A한국투자,005930,삼성전자,100,70000,75000"
            download="sample_holdings.csv"
            className="rounded-md bg-slate-700 px-3 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-600"
          >
            샘플 다운로드
          </a>
        </div>
      </div>

      {(uploadMsg || snapshotMsg || rebalanceMsg || providerMsg) && (
        <div className="space-y-2">
          {[providerMsg, uploadMsg, snapshotMsg, rebalanceMsg].filter(Boolean).map((message) => (
            <div
              key={`${message?.type}-${message?.text}`}
              className={cn(
                "rounded-md px-4 py-2 text-sm",
                message?.type === "ok" ? "bg-green-500/20 text-green-300" : "bg-red-500/20 text-red-300",
              )}
            >
              {message?.text}
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
        <Card>
          <p className="text-xs text-slate-400">총 자산</p>
          <p className="mt-1 text-xl font-bold text-white">{formatKRW(totalValue)}</p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">총 손익</p>
          <p className={cn("mt-1 text-xl font-bold", totalProfit >= 0 ? "text-green-400" : "text-red-400")}>
            {totalProfit >= 0 ? "+" : ""}{formatKRW(totalProfit)}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">계좌 수</p>
          <p className="mt-1 text-xl font-bold text-white">{accounts.length}개</p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">리밸런싱 포함</p>
          <p className="mt-1 text-xl font-bold text-white">{includedAccounts}개</p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">현재 모드</p>
          <p className={cn("mt-1 text-xl font-bold", canWrite ? "text-sky-300" : "text-slate-400")}>
            {mode.toUpperCase()}
          </p>
        </Card>
      </div>

      <Card title="계좌 정책">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500">
                <th className="px-3 py-2 text-left">유형</th>
                <th className="px-3 py-2 text-left">역할</th>
                <th className="px-3 py-2 text-left">입출금</th>
                <th className="px-3 py-2 text-left">상품</th>
                <th className="px-3 py-2 text-left">리밸런싱</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60">
              {policies.map((policy) => (
                <tr key={policy.id} className="text-slate-300">
                  <td className="px-3 py-2 font-semibold text-white">{policy.accountType}</td>
                  <td className="px-3 py-2">{policy.role}</td>
                  <td className="px-3 py-2">{policy.depositPolicy ?? "-"}</td>
                  <td className="px-3 py-2">{policy.allowedProducts ?? "-"}</td>
                  <td className="px-3 py-2">{policy.rebalancePriority ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {loading ? (
        <div className="flex h-40 items-center justify-center text-slate-500">로딩 중...</div>
      ) : (
        <Card title="계좌 목록" extra={modeInfo?.provider ?? undefined}>
          <div className="divide-y divide-slate-700">
            {accounts.map((acct) => {
              const policy = acct.accountType ? policyByType.get(acct.accountType) : null;
              return (
                <div key={acct.id}>
                  <div
                    className="w-full cursor-pointer rounded px-2 py-3 transition-colors hover:bg-slate-700/30"
                    onClick={() => handleSelectAccount(acct.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && handleSelectAccount(acct.id)}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blue-600/30 text-sm font-bold text-blue-400">
                          {acct.name.charAt(0)}
                        </div>
                        <div className="min-w-0 text-left">
                          <p className="truncate text-sm font-semibold text-white">{acct.name}</p>
                          <div className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-slate-500">
                            <span>{acct.type ?? "일반계좌"}</span>
                            {acct.accountType && <span className="rounded bg-slate-700 px-1.5 py-0.5">{acct.accountType}</span>}
                            {acct.dataSource && <span className="rounded bg-slate-700 px-1.5 py-0.5">{acct.dataSource}</span>}
                            {policy?.role && <span className="rounded bg-slate-700 px-1.5 py-0.5">{policy.role}</span>}
                          </div>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        <button
                          type="button"
                          onClick={(e) => handleToggleInclusion(acct, e)}
                          disabled={toggleBusyId === acct.id || !canWrite}
                          className={cn(
                            "rounded-md px-2 py-1 text-[11px] transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                            acct.includeInRebalancing === false
                              ? "bg-slate-700 text-slate-400"
                              : "bg-emerald-500/15 text-emerald-300",
                          )}
                        >
                          {acct.includeInRebalancing === false ? "제외" : "포함"}
                        </button>
                        <div className="text-right">
                          <p className="text-sm font-bold text-white">{formatKRW(acct.value)}</p>
                          <p className={cn("text-xs", acct.profit >= 0 ? "text-green-400" : "text-red-400")}>
                            {acct.profit >= 0 ? "+" : ""}{formatKRW(acct.profit)}
                            <span className="ml-1 text-slate-500">({acct.profitRate >= 0 ? "+" : ""}{acct.profitRate.toFixed(2)}%)</span>
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {selected === acct.id && (
                    <div className="mx-2 mb-3 rounded-md border border-slate-700 bg-slate-900/30 p-4">
                      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
                        <form onSubmit={handleSnapshotSubmit} className="space-y-3">
                          <div className="flex items-center justify-between">
                            <h4 className="text-sm font-semibold text-slate-200">수동 스냅샷</h4>
                            <span className="text-xs text-slate-500">최근 동기화 {formatDateTime(acct.lastSyncedAt)}</span>
                          </div>
                          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                            {SNAPSHOT_FIELDS.map((field) => (
                              <label key={field.key} className="space-y-1 text-xs text-slate-400">
                                <span>{field.label}</span>
                                <input
                                  value={snapshotForm[field.key]}
                                  onChange={(event) => setSnapshotForm((prev) => ({
                                    ...prev,
                                    [field.key]: event.target.value,
                                  }))}
                                  inputMode="numeric"
                                  disabled={!canWrite}
                                  className="h-9 w-full rounded-md border border-slate-700 bg-slate-800 px-2 text-sm text-white outline-none focus:border-blue-500 disabled:text-slate-500"
                                />
                              </label>
                            ))}
                          </div>
                          <button
                            type="submit"
                            disabled={snapshotSaving || !canWrite}
                            className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
                          >
                            {snapshotSaving ? "저장 중..." : "스냅샷 저장"}
                          </button>
                        </form>

                        <div>
                          <div className="mb-3 flex items-center justify-between">
                            <h4 className="text-sm font-semibold text-slate-200">스냅샷 이력</h4>
                            {snapshotLoading && <span className="text-xs text-slate-500">로딩 중...</span>}
                          </div>
                          {snapshots.length === 0 ? (
                            <div className="rounded-md bg-slate-800/50 py-6 text-center text-sm text-slate-500">
                              저장된 스냅샷 없음
                            </div>
                          ) : (
                            <div className="max-h-56 overflow-y-auto rounded-md border border-slate-700">
                              <table className="w-full text-xs">
                                <thead>
                                  <tr className="border-b border-slate-700 text-slate-500">
                                    <th className="px-3 py-2 text-left">시점</th>
                                    <th className="px-3 py-2 text-right">총자산</th>
                                    <th className="px-3 py-2 text-right">현금</th>
                                    <th className="px-3 py-2 text-right">ETF</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-700/50">
                                  {snapshots.map((snapshot) => (
                                    <tr key={snapshot.id} className="text-slate-300">
                                      <td className="px-3 py-2">{formatDateTime(snapshot.snapshotAt)}</td>
                                      <td className="px-3 py-2 text-right text-white">{formatKRW(snapshot.totalValue)}</td>
                                      <td className="px-3 py-2 text-right">{formatKRW(snapshot.cashValue)}</td>
                                      <td className="px-3 py-2 text-right">{formatKRW(snapshot.etfValue)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="mt-4 overflow-hidden rounded-md border border-slate-700">
                        {posLoading ? (
                          <div className="py-4 text-center text-sm text-slate-500">보유 종목 로딩 중...</div>
                        ) : positions.length === 0 ? (
                          <div className="py-4 text-center text-sm text-slate-500">보유 종목 없음</div>
                        ) : (
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b border-slate-600 text-slate-500">
                                <th className="px-3 py-2 text-left">종목</th>
                                <th className="px-3 py-2 text-right">수량</th>
                                <th className="px-3 py-2 text-right">평균가</th>
                                <th className="px-3 py-2 text-right">현재가</th>
                                <th className="px-3 py-2 text-right">평가금액</th>
                                <th className="px-3 py-2 text-right">손익</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-700/50">
                              {positions.map((position) => (
                                <tr key={position.id} className="text-slate-300 hover:bg-slate-700/20">
                                  <td className="px-3 py-2">
                                    <p className="font-medium text-white">{position.name}</p>
                                    <p className="text-slate-500">{position.ticker}</p>
                                  </td>
                                  <td className="px-3 py-2 text-right">{position.quantity.toLocaleString()}</td>
                                  <td className="px-3 py-2 text-right">{position.avg_price?.toLocaleString()}</td>
                                  <td className="px-3 py-2 text-right">{position.current_price?.toLocaleString()}</td>
                                  <td className="px-3 py-2 text-right text-white">{formatKRW(position.market_value)}</td>
                                  <td className={cn("px-3 py-2 text-right", position.profit >= 0 ? "text-green-400" : "text-red-400")}>
                                    {position.profit >= 0 ? "+" : ""}{formatKRW(position.profit)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {accounts.length === 0 && (
            <div className="py-8 text-center text-slate-500">
              표시할 계좌가 없습니다.
            </div>
          )}
        </Card>
      )}

      <Card
        title="리밸런싱 실행 로그"
        extra={
          <button
            type="button"
            onClick={handleRunRebalancing}
            disabled={rebalanceRunning || !canWrite}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
          >
            {rebalanceRunning ? "실행 중..." : "계산 저장"}
          </button>
        }
      >
        {rebalanceResults.length === 0 ? (
          <div className="py-6 text-center text-sm text-slate-500">저장된 리밸런싱 로그 없음</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-700 text-slate-500">
                  <th className="px-3 py-2 text-left">시점</th>
                  <th className="px-3 py-2 text-left">자산군</th>
                  <th className="px-3 py-2 text-right">현재</th>
                  <th className="px-3 py-2 text-right">목표</th>
                  <th className="px-3 py-2 text-right">괴리</th>
                  <th className="px-3 py-2 text-left">액션</th>
                  <th className="px-3 py-2 text-right">금액</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60">
                {rebalanceResults.map((result) => (
                  <tr key={`${result.runId}-${result.id}-${result.assetClass}`} className="text-slate-300">
                    <td className="px-3 py-2">{formatDateTime(result.createdAt)}</td>
                    <td className="px-3 py-2 font-semibold text-white">{result.assetClass}</td>
                    <td className="px-3 py-2 text-right">{result.currentRatio.toFixed(1)}%</td>
                    <td className="px-3 py-2 text-right">{result.targetRatio.toFixed(1)}%</td>
                    <td className={cn("px-3 py-2 text-right", Math.abs(result.deviation) >= 5 ? "text-red-300" : "text-slate-300")}>
                      {formatPercent(result.deviation)}
                    </td>
                    <td className="px-3 py-2">{actionLabel(result.action)}</td>
                    <td className="px-3 py-2 text-right">{formatKRW(Math.abs(result.amount))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="CSV 형식">
        <pre className="overflow-x-auto rounded-md bg-slate-900 p-3 text-xs text-slate-300">
{`account_name,ticker,name,quantity,avg_price,current_price
한국투자,005930,삼성전자,100,70000,75000
한국투자,000660,SK하이닉스,50,120000,135000
미국주식,AAPL,Apple Inc,10,170.00,185.00`}
        </pre>
      </Card>
    </div>
  );
}
