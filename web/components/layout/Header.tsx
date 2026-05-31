// components/layout/Header.tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BASE_URL } from "@/lib/api";

interface SearchResult {
  type: string;
  key: string;
  title: string;
  url: string;
}

interface TickerItem {
  label: string;
  value: string;
  change: string;
  down: boolean;
}

const TYPE_ICON: Record<string, string> = {
  macro: "📊",
  document: "📁",
  alert: "🔔",
};

// 매크로 key → 티커 레이블 매핑 (DB indicators 테이블의 실제 key 사용)
const TICKER_KEYS: { key: string; label: string; decimals: number }[] = [
  { key: "SPY",      label: "S&P 500",  decimals: 2 },
  { key: "QQQ",      label: "NASDAQ",   decimals: 2 },
  { key: "KOSPI",    label: "KOSPI",    decimals: 2 },
  { key: "USD_KRW",  label: "USD/KRW",  decimals: 2 },
  { key: "WTI",      label: "WTI",      decimals: 2 },
];

const FALLBACK_TICKERS: TickerItem[] = [
  { label: "S&P 500", value: "5,278.40",  change: "+0.45%", down: false },
  { label: "NASDAQ",  value: "16,735.02", change: "+0.64%", down: false },
  { label: "KOSPI",   value: "2,726.45",  change: "-0.21%", down: true  },
  { label: "USD/KRW", value: "1,364.20",  change: "-0.21%", down: true  },
  { label: "WTI",     value: "97.63",     change: "+1.23",  down: false },
];

export interface HeaderProps {
  alertCount?: number;
}

export default function Header({ alertCount: initialAlertCount = 0 }: HeaderProps) {
  const [dark, setDark] = useState(true);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [alertCount, setAlertCount] = useState(initialAlertCount);
  const [tickers, setTickers] = useState<TickerItem[]>(FALLBACK_TICKERS);
  const router = useRouter();
  const ref = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const today = new Date().toLocaleDateString("ko-KR", {
    year: "numeric", month: "2-digit", day: "2-digit",
  });

  // 이번 주 월~금 범위 계산
  const weekRange = (() => {
    const now = new Date();
    const day = now.getDay(); // 0=Sun, 1=Mon ...
    const monday = new Date(now);
    monday.setDate(now.getDate() - (day === 0 ? 6 : day - 1));
    const friday = new Date(monday);
    friday.setDate(monday.getDate() + 4);
    const fmt = (d: Date) =>
      `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(d.getDate()).padStart(2, "0")}`;
    return `${fmt(monday)} ~ ${fmt(friday)}`;
  })();

  // 미읽은 알림 카운트 fetch
  useEffect(() => {
    const fetchAlertCount = () => {
      fetch(`${BASE_URL}/api/alerts/recent?limit=100`)
        .then((r) => r.json())
        .then((data: { is_read: boolean }[]) => {
          setAlertCount(data.filter((a) => !a.is_read).length);
        })
        .catch(() => {});
    };
    fetchAlertCount();
    const id = setInterval(fetchAlertCount, 60_000); // 1분마다 갱신
    return () => clearInterval(id);
  }, []);

  // 매크로 티커 데이터 fetch
  useEffect(() => {
    fetch(`${BASE_URL}/api/macro/summary`)
      .then((r) => r.json())
      .then((data: { key: string; value: number; change: number; status: string }[]) => {
        const built: TickerItem[] = TICKER_KEYS.map(({ key, label, decimals }) => {
          const found = data.find((d) => d.key === key);
          if (!found) {
            const fallback = FALLBACK_TICKERS.find((t) => t.label === label);
            return fallback ?? { label, value: "-", change: "-", down: false };
          }
          const changeNum = found.change ?? 0;
          const changeStr = (changeNum >= 0 ? "+" : "") + changeNum.toFixed(decimals);
          return {
            label,
            value: key === "USD_KRW"
              ? found.value.toLocaleString("ko-KR", { maximumFractionDigits: 2 })
              : found.value.toLocaleString("en-US", { maximumFractionDigits: decimals }),
            change: changeStr,
            down: changeNum < 0,
          };
        });
        setTickers(built);
      })
      .catch(() => setTickers(FALLBACK_TICKERS));
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSearch = (v: string) => {
    setQuery(v);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (v.length < 1) { setResults([]); setOpen(false); return; }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(`${BASE_URL}/api/search?q=${encodeURIComponent(v)}`);
        const data = await res.json();
        setResults(data.results ?? []);
        setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
  };

  const handleSelect = (result: SearchResult) => {
    setOpen(false);
    setQuery("");
    router.push(result.url);
  };

  return (
    <header className="sticky top-0 z-30 bg-slate-900/90 backdrop-blur border-b border-slate-700 h-12 flex items-center px-5 gap-4">
      {/* Global search */}
      <div className="relative shrink-0 w-52" ref={ref}>
        <div className="flex items-center gap-2 bg-slate-800 border border-slate-700 rounded-lg px-2.5 h-7 focus-within:border-blue-500 transition-colors">
          <span className="text-slate-500 text-xs">🔍</span>
          <input
            type="text"
            value={query}
            onChange={(e) => handleSearch(e.target.value)}
            onFocus={() => results.length > 0 && setOpen(true)}
            placeholder="검색 (예: CPI, 금리, AAPL)"
            className="bg-transparent text-xs text-white placeholder:text-slate-600 focus:outline-none w-full"
          />
          {loading && <span className="text-slate-500 text-[10px] animate-pulse">•••</span>}
        </div>
        {open && results.length > 0 && (
          <div className="absolute top-8 left-0 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 overflow-hidden">
            {results.map((r, i) => (
              <button
                key={`${r.type}-${r.key}-${i}`}
                onClick={() => handleSelect(r)}
                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-slate-700 text-left transition-colors"
              >
                <span className="text-sm">{TYPE_ICON[r.type] ?? "🔖"}</span>
                <div className="min-w-0">
                  <p className="text-xs text-white truncate">{r.title}</p>
                  <p className="text-[10px] text-slate-500">{r.type}</p>
                </div>
              </button>
            ))}
          </div>
        )}
        {open && results.length === 0 && query.length > 0 && !loading && (
          <div className="absolute top-8 left-0 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 px-3 py-2">
            <p className="text-xs text-slate-500">검색 결과 없음</p>
          </div>
        )}
      </div>

      {/* Ticker bar — 실제 매크로 데이터 or 폴백 */}
      <div className="flex items-center gap-4 text-xs font-mono flex-1 overflow-hidden">
        {tickers.map((t) => (
          <span key={t.label} className="flex items-center gap-1.5 shrink-0">
            <span className="text-slate-500">{t.label}</span>
            <span className="text-white">{t.value}</span>
            <span className={t.down ? "text-blue-400" : "text-red-400"}>{t.change}</span>
          </span>
        ))}
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex flex-col items-end text-right">
          <span className="text-xs text-slate-500">{today}</span>
          <span className="text-[10px] text-slate-600">{weekRange}</span>
        </div>

        {/* Alert bell */}
        <button
          onClick={() => router.push("/alerts")}
          className="relative text-slate-400 hover:text-white transition-colors"
        >
          <span className="text-base">🔔</span>
          {alertCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[9px] text-white flex items-center justify-center font-bold">
              {alertCount > 9 ? "9+" : alertCount}
            </span>
          )}
        </button>

        {/* Theme toggle */}
        <button
          onClick={() => setDark(!dark)}
          className="text-slate-400 hover:text-white transition-colors text-base"
          title="테마 전환"
        >
          {dark ? "🌙" : "☀️"}
        </button>

        {/* Profile */}
        <div className="flex items-center gap-2 cursor-pointer">
          <div className="w-7 h-7 bg-blue-600 rounded-full flex items-center justify-center text-white text-xs font-bold">
            범
          </div>
          <span className="text-sm text-slate-300 hidden md:block">김범상</span>
        </div>
      </div>
    </header>
  );
}
