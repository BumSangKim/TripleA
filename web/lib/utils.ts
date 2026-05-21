// lib/utils.ts
export function formatKRW(value: number): string {
  if (value >= 1_000_000_000_000) {
    return `₩${(value / 1_000_000_000_000).toFixed(2)}조`;
  }
  if (value >= 100_000_000) {
    return `₩${(value / 100_000_000).toFixed(0)}억`;
  }
  if (value >= 10_000) {
    return `₩${(value / 10_000).toFixed(0)}만`;
  }
  return `₩${value.toLocaleString()}`;
}

export function formatNumber(value: number, decimals = 2): string {
  return value.toFixed(decimals);
}

export function formatChange(value: number | null): string {
  if (value === null || value === undefined) return "-";
  return value >= 0 ? `+${value.toFixed(2)}` : `${value.toFixed(2)}`;
}

export function getRiskColor(level: "normal" | "warning" | "danger"): string {
  switch (level) {
    case "danger":  return "text-red-400";
    case "warning": return "text-yellow-400";
    default:        return "text-green-400";
  }
}

export function getStatusColor(status: "rising" | "falling" | "stable"): string {
  switch (status) {
    case "rising":  return "text-red-400";
    case "falling": return "text-blue-400";
    default:        return "text-slate-400";
  }
}

export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(" ");
}
