// app/orders/OrdersPageClient.tsx
"use client";

import { useState } from "react";
import { APIRequestError, api } from "@/lib/api";
import type { OrderDraftResponse, TradingMode } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn, formatKRW } from "@/lib/utils";

const MODE_OPTIONS: { value: TradingMode; label: string }[] = [
  { value: "paper", label: "Paper" },
  { value: "live", label: "Live" },
];

function getErrorMessage(error: unknown): string {
  if (error instanceof APIRequestError && error.detail?.userAction) {
    return `${error.message} ${error.detail.userAction}`;
  }
  return error instanceof Error ? error.message : String(error);
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    DRAFT: "후보",
    EMPTY: "후보 없음",
    APPROVED_NOT_SENT: "승인 기록",
  };
  return labels[status] ?? status;
}

export default function OrdersPageClient() {
  const [mode, setMode] = useState<TradingMode>("paper");
  const [maxAmount, setMaxAmount] = useState("1000000");
  const [draft, setDraft] = useState<OrderDraftResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const handleCreateDraft = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const amount = Number(maxAmount.replaceAll(",", "").trim());
      const result = await api.createOrderDraft({
        mode,
        source: "rebalancing",
        maxOrderAmount: Number.isFinite(amount) && amount > 0 ? amount : null,
      });
      setDraft(result);
      setMsg({ type: "ok", text: `${result.itemCount}개 주문 후보 생성` });
    } catch (error) {
      setMsg({ type: "err", text: getErrorMessage(error) });
    } finally {
      setLoading(false);
    }
  };

  const handleApprovePaper = async () => {
    if (!draft) return;
    setApproving(true);
    setMsg(null);
    try {
      const result = await api.executeOrderDraft({
        mode,
        orderDraftId: draft.draftId,
        confirmText: "모의 주문을 승인합니다",
      });
      setDraft(result);
      setMsg({ type: "ok", text: result.message ?? "승인 로그 저장 완료" });
    } catch (error) {
      setMsg({ type: "err", text: getErrorMessage(error) });
    } finally {
      setApproving(false);
    }
  };

  const canApprovePaper = mode === "paper" && draft?.status === "DRAFT" && draft.itemCount > 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">주문 후보</h1>
          <p className="text-sm text-slate-400">리밸런싱 기반 후보 생성과 수동 승인 로그</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={mode}
            onChange={(e) => {
              setMode(e.target.value as TradingMode);
              setDraft(null);
              setMsg(null);
            }}
            className="h-9 rounded-md border border-slate-600 bg-slate-800 px-3 text-sm text-white outline-none focus:border-blue-500"
          >
            {MODE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <input
            value={maxAmount}
            onChange={(e) => setMaxAmount(e.target.value)}
            inputMode="numeric"
            className="h-9 w-36 rounded-md border border-slate-600 bg-slate-800 px-3 text-sm text-white outline-none focus:border-blue-500"
          />
          <button
            type="button"
            onClick={handleCreateDraft}
            disabled={loading}
            className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
          >
            {loading ? "생성 중..." : "후보 생성"}
          </button>
          <button
            type="button"
            onClick={handleApprovePaper}
            disabled={!canApprovePaper || approving}
            className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-500"
          >
            {approving ? "승인 중..." : "Paper 승인 기록"}
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

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Card>
          <p className="text-xs text-slate-400">현재 모드</p>
          <p className={cn("mt-1 text-xl font-bold", mode === "live" ? "text-red-300" : "text-sky-300")}>
            {mode.toUpperCase()}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">Draft ID</p>
          <p className="mt-1 text-xl font-bold text-white">{draft?.draftId ?? "-"}</p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">상태</p>
          <p className="mt-1 text-xl font-bold text-white">{draft ? statusLabel(draft.status) : "-"}</p>
        </Card>
        <Card>
          <p className="text-xs text-slate-400">총 후보 금액</p>
          <p className="mt-1 text-xl font-bold text-white">{draft ? formatKRW(draft.totalAmount) : "-"}</p>
        </Card>
      </div>

      {mode === "live" && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          Live 모드는 후보 생성만 가능하며 실제 주문 실행은 비활성화되어 있습니다.
        </div>
      )}

      <Card title="후보 목록">
        {!draft ? (
          <div className="py-10 text-center text-sm text-slate-500">생성된 주문 후보가 없습니다.</div>
        ) : draft.items.length === 0 ? (
          <div className="py-10 text-center text-sm text-slate-500">리밸런싱 기준 후보가 없습니다.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-700 text-slate-500">
                  <th className="px-3 py-2 text-left">자산군</th>
                  <th className="px-3 py-2 text-left">방향</th>
                  <th className="px-3 py-2 text-right">후보 금액</th>
                  <th className="px-3 py-2 text-left">상태</th>
                  <th className="px-3 py-2 text-left">사유</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700/60">
                {draft.items.map((item) => (
                  <tr key={item.id ?? `${item.assetClass}-${item.side}`}>
                    <td className="px-3 py-2 text-white">{item.assetClass}</td>
                    <td className={cn("px-3 py-2 font-semibold", item.side === "BUY" ? "text-green-300" : "text-red-300")}>
                      {item.side}
                    </td>
                    <td className="px-3 py-2 text-right text-slate-200">{formatKRW(item.amount)}</td>
                    <td className="px-3 py-2 text-slate-300">{statusLabel(item.status)}</td>
                    <td className="px-3 py-2 text-slate-400">{item.reason ?? "-"}</td>
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
