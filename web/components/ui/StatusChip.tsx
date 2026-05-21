// components/ui/StatusChip.tsx
import { cn } from "@/lib/utils";

interface StatusChipProps {
  status: "rising" | "falling" | "stable" | "normal" | "warning" | "danger" | "info";
  children?: React.ReactNode;
  className?: string;
}

const STATUS_MAP: Record<string, { bg: string; text: string; dot: string }> = {
  rising:  { bg: "bg-red-500/10",    text: "text-red-400",    dot: "bg-red-400" },
  falling: { bg: "bg-blue-500/10",   text: "text-blue-400",   dot: "bg-blue-400" },
  stable:  { bg: "bg-slate-500/10",  text: "text-slate-400",  dot: "bg-slate-400" },
  normal:  { bg: "bg-green-500/10",  text: "text-green-400",  dot: "bg-green-400" },
  warning: { bg: "bg-yellow-500/10", text: "text-yellow-400", dot: "bg-yellow-400" },
  danger:  { bg: "bg-red-500/10",    text: "text-red-400",    dot: "bg-red-400" },
  info:    { bg: "bg-blue-500/10",   text: "text-blue-400",   dot: "bg-blue-400" },
};

const STATUS_LABEL: Record<string, string> = {
  rising: "상승", falling: "하락", stable: "보합",
  normal: "정상", warning: "주의", danger: "경고", info: "정보",
};

export default function StatusChip({ status, children, className }: StatusChipProps) {
  const s = STATUS_MAP[status] || STATUS_MAP.stable;
  return (
    <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium", s.bg, s.text, className)}>
      <span className={cn("w-1.5 h-1.5 rounded-full", s.dot)} />
      {children ?? STATUS_LABEL[status]}
    </span>
  );
}
