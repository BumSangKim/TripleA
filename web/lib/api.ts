// lib/api.ts
import type { DashboardSummary, MacroIndicator, TargetItem, SuggestionItem, AlertItem, DocumentItem, CalendarEvent } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  getDashboardSummary: (): Promise<DashboardSummary> =>
    fetchJSON<DashboardSummary>("/api/dashboard/summary"),

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
