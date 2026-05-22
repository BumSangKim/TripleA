// lib/api.ts
import type {
  AccountPolicyItem,
  AccountSnapshotCreate,
  AccountSnapshotItem,
  CalendarEvent,
  DashboardSummary,
  DocumentItem,
  AlertItem,
  MacroIndicator,
  ModeInfo,
  RebalanceResultItem,
  RebalanceRunResponse,
  SuggestionItem,
  TargetItem,
  TradingMode,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function withQuery(path: string, params: Record<string, string | number | boolean | null | undefined>): string {
  const [base, rawQuery] = path.split("?");
  const search = new URLSearchParams(rawQuery ?? "");
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `${base}?${query}` : base;
}

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  getDashboardSummary: (mode?: TradingMode): Promise<DashboardSummary> =>
    fetchJSON<DashboardSummary>(withQuery("/api/dashboard/summary", { mode })),

  getModes: (): Promise<ModeInfo[]> =>
    fetchJSON<ModeInfo[]>("/api/modes"),

  getMacroSummary: (): Promise<MacroIndicator[]> =>
    fetchJSON<MacroIndicator[]>("/api/macro/summary"),

  getMacroHistory: (indicator: string, days = 30) =>
    fetchJSON<{ date: string; value: number }[]>(
      `/api/macro/history/${indicator}?days=${days}`
    ),

  getTargets: (): Promise<TargetItem[]> =>
    fetchJSON<TargetItem[]>("/api/targets"),

  updateTarget: (data: { asset_class: string; target_value: number; warning_thr?: number; danger_thr?: number }) =>
    fetchJSON("/api/targets", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  getRebalancingSuggestions: (): Promise<SuggestionItem[]> =>
    fetchJSON<SuggestionItem[]>("/api/rebalancing/suggestions"),

  runRebalancing: (mode?: TradingMode): Promise<RebalanceRunResponse> =>
    fetchJSON<RebalanceRunResponse>(withQuery("/api/rebalancing/run", { mode }), {
      method: "POST",
    }),

  getRebalanceResults: (mode?: TradingMode, limit = 50): Promise<RebalanceResultItem[]> =>
    fetchJSON<RebalanceResultItem[]>(withQuery("/api/rebalancing/results", { mode, limit })),

  getAccountPolicies: (): Promise<AccountPolicyItem[]> =>
    fetchJSON<AccountPolicyItem[]>("/api/account-policies"),

  getAccountSnapshots: (accountId: number, limit = 20): Promise<AccountSnapshotItem[]> =>
    fetchJSON<AccountSnapshotItem[]>(withQuery(`/api/accounts/${accountId}/snapshots`, { limit })),

  createManualSnapshot: (
    accountId: number,
    mode: TradingMode,
    data: AccountSnapshotCreate,
  ): Promise<AccountSnapshotItem> =>
    fetchJSON<AccountSnapshotItem>(withQuery(`/api/accounts/${accountId}/manual-snapshot`, { mode }), {
      method: "POST",
      body: JSON.stringify(data),
    }),

  setAccountRebalancingInclusion: (accountId: number, include: boolean, mode: TradingMode) =>
    fetchJSON<{ ok: boolean; account_id: number; include: boolean }>(
      withQuery(`/api/accounts/${accountId}/rebalancing-inclusion`, { include, mode }),
      { method: "PATCH" },
    ),

  getAlerts: (limit = 10): Promise<AlertItem[]> =>
    fetchJSON<AlertItem[]>(`/api/alerts/recent?limit=${limit}`),

  markAlertRead: (id: number) =>
    fetchJSON(`/api/alerts/${id}/read`, { method: "PATCH" }),

  getDocuments: (): Promise<DocumentItem[]> =>
    fetchJSON<DocumentItem[]>("/api/documents"),

  createDocument: (doc: Omit<DocumentItem, "id" | "created_at" | "updated_at">): Promise<DocumentItem> =>
    fetchJSON<DocumentItem>("/api/documents", {
      method: "POST",
      body: JSON.stringify(doc),
    }),

  getCalendarEvents: (): Promise<CalendarEvent[]> =>
    fetchJSON<CalendarEvent[]>("/api/calendar/events"),

  getHealth: () => fetchJSON<{ status: string }>("/api/health"),
};
