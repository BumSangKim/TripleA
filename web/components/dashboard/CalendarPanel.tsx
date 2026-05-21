// components/dashboard/CalendarPanel.tsx
import { CalendarEvent } from "@/lib/types";
import Card from "@/components/ui/Card";
import { cn } from "@/lib/utils";

interface CalendarPanelProps {
  events: CalendarEvent[];
}

const IMPORTANCE_STYLE: Record<string, { dot: string; badge: string; text: string }> = {
  high:   { dot: "bg-red-400",    badge: "bg-red-500/20 text-red-400",    text: "높음" },
  medium: { dot: "bg-yellow-400", badge: "bg-yellow-500/20 text-yellow-400", text: "보통" },
  low:    { dot: "bg-slate-500",  badge: "bg-slate-700 text-slate-400",   text: "낮음" },
};

const FLAG: Record<string, string> = { US: "🇺🇸", KR: "🇰🇷", EU: "🇪🇺", JP: "🇯🇵" };

function dDay(dateStr: string): string {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(dateStr);
  target.setHours(0, 0, 0, 0);
  const diff = Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  if (diff === 0) return "D-Day";
  if (diff > 0) return `D-${diff}`;
  return `D+${Math.abs(diff)}`;
}

export default function CalendarPanel({ events }: CalendarPanelProps) {
  return (
    <Card
      title="주요 일정 / 경제 캘린더"
      extra={<a href="/calendar" className="text-blue-400 hover:underline">더보기 &gt;</a>}
    >
      <div className="space-y-2">
        {events.map((ev, i) => {
          const imp = IMPORTANCE_STYLE[ev.importance] || IMPORTANCE_STYLE.low;
          return (
            <div key={i} className="flex items-center gap-3 py-1.5 border-b border-slate-700/50 last:border-0">
              <span className={cn("w-1.5 h-1.5 rounded-full shrink-0 mt-0.5", imp.dot)} />
              <div className="flex-1 min-w-0">
                <p className="text-sm text-white truncate">{ev.title}</p>
                <p className="text-[10px] text-slate-500">
                  {Flag(ev.country)} {ev.date} {ev.time && `${ev.time} (ET)`}
                </p>
              </div>
              <div className="text-right shrink-0">
                <span className={cn("inline-block px-1.5 py-0.5 rounded text-[10px] font-medium", imp.badge)}>
                  {imp.text}
                </span>
                <p className="text-[10px] text-slate-500 mt-0.5">{dDay(ev.date)}</p>
              </div>
            </div>
          );
        })}
        {events.length === 0 && (
          <p className="text-center text-slate-500 text-sm py-4">등록된 일정이 없습니다.</p>
        )}
      </div>
    </Card>
  );
}

function Flag(country: string) {
  return FLAG[country] || "🌐";
}
