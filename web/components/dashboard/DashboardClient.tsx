// components/dashboard/DashboardClient.tsx
"use client";

import { useEffect, useState, useCallback } from "react";
import type { DashboardSummary } from "@/lib/types";
import { api } from "@/lib/api";
import KPIBar from "./KPIBar";
import MacroPanel from "./MacroPanel";
import AccountPanel from "./AccountPanel";
import TargetPanel from "./TargetPanel";
import SuggestionPanel from "./SuggestionPanel";
import TopMoversPanel from "./TopMoversPanel";
import CalendarPanel from "./CalendarPanel";
import AlertPanel from "./AlertPanel";
import InsightPanel from "./InsightPanel";
import SystemStatusPanel from "./SystemStatusPanel";
import DocumentsPanel from "./DocumentsPanel";
import DailyCheckPanel from "./DailyCheckPanel";
import MemoPanel from "./MemoPanel";

// Mock data fallback (API 없을 때)
const MOCK_DATA: DashboardSummary = {
  kpi: {
    totalAssets: 1_254_560_000,
    cash: 125_480_000,
    todayProfit: 3_247_800,
    todayProfitRate: 0.26,
    riskLevel: "보통",
  },
  macro: [
    { key: "cpi",      name: "CPI YoY",   value: 3.4,  unit: "%",  change: 0.2,  status: "rising",  date: "2024-05-10" },
    { key: "interest", name: "기준금리",   value: 5.50, unit: "%",  change: 0,    status: "stable",  date: "2024-05-01" },
    { key: "unrate",   name: "실업률",     value: 3.9,  unit: "%",  change: -0.1, status: "falling", date: "2024-05-03" },
    { key: "usdkrw",   name: "USD/KRW",   value: 1364.2,unit:"원", change: 3.10, status: "rising",  date: "2024-05-24" },
    { key: "vix",      name: "VIX",       value: 14.32,unit: "pt", change: -0.37,status: "falling", date: "2024-05-24" },
    { key: "pmi",      name: "PMI",       value: 51.4, unit: "pt", change: 0.6,  status: "rising",  date: "2024-05-01" },
    { key: "dgs10",    name: "미국 10년채",value: 4.48, unit: "%",  change: -0.02,status: "falling", date: "2024-05-24" },
    { key: "dxy",      name: "달러인덱스", value: 104.7,unit: "pt", change: -0.3, status: "falling", date: "2024-05-24" },
    { key: "wti",      name: "WTI 유가",  value: 79.2, unit: "$",  change: 1.2,  status: "rising",  date: "2024-05-24" },
  ],
  accounts: [
    { id: 1, name: "종합투자계좌", type: "종합", value: 842_315_000, profit: 2_715_300,  profitRate: 0.25  },
    { id: 2, name: "ISA계좌",     type: "ISA",  value: 218_460_000, profit: 1_028_200,  profitRate: 0.40  },
    { id: 3, name: "연금저축계좌", type: "연금",  value: 142_910_000, profit: 765_000,    profitRate: 0.55  },
    { id: 4, name: "해외주식계좌", type: "해외",  value: 50_875_000,  profit: -676_300,   profitRate: -1.31 },
  ],
  allocation: [
    { asset: "국내주식", value: 360_000_000, ratio: 28.7 },
    { asset: "해외주식", value: 429_500_000, ratio: 34.2 },
    { asset: "채권",     value: 97_800_000,  ratio: 7.8  },
    { asset: "ETF",      value: 186_900_000, ratio: 14.9 },
    { asset: "현금",     value: 126_680_000, ratio: 10.1 },
    { asset: "기타/대기",value: 53_680_000,  ratio: 4.3  },
  ],
  targets: [
    { asset_class: "국내주식", currentRatio: 28.7, targetRatio: 25.0, deviation: 3.7,  level: "warning" },
    { asset_class: "해외주식", currentRatio: 34.2, targetRatio: 35.0, deviation: -0.8, level: "normal"  },
    { asset_class: "채권",     currentRatio: 7.8,  targetRatio: 10.0, deviation: -2.2, level: "warning" },
    { asset_class: "ETF",      currentRatio: 14.9, targetRatio: 15.0, deviation: -0.1, level: "normal"  },
    { asset_class: "현금",     currentRatio: 10.1, targetRatio: 15.0, deviation: -4.9, level: "danger"  },
  ],
  suggestions: [
    { asset: "국내주식", action: "비중 축소", reason: "목표 초과 3.7%", deviation: 3.7  },
    { asset: "해외주식", action: "관망",      reason: "목표 비중 유지 (-0.8%)", deviation: -0.8 },
    { asset: "채권",     action: "비중 확대", reason: "목표 미달 2.2%", deviation: -2.2 },
    { asset: "ETF",      action: "관망",      reason: "목표 비중 유지 (-0.1%)", deviation: -0.1 },
    { asset: "현금",     action: "비중 확대", reason: "현금 비중 부족 4.9%", deviation: -4.9 },
  ],
  topMovers: [
    { symbol: "NVDA",      name: "엔비디아",       price: 1024.86, changeRate: 4.21,  contribution: null },
    { symbol: "AAPL",      name: "애플",           price: 189.98,  changeRate: 1.67,  contribution: null },
    { symbol: "MSFT",      name: "마이크로소프트",  price: 420.35,  changeRate: 1.31,  contribution: null },
    { symbol: "005930.KS", name: "삼성전자",        price: 79800,   changeRate: 1.45,  contribution: null },
    { symbol: "TSLA",      name: "테슬라",          price: 174.40,  changeRate: -1.23, contribution: null },
  ],
  calendar: [
    { date: "2024-05-24", time: "21:30", title: "미국 PCE 물가지수",          country: "US", importance: "high"   },
    { date: "2024-05-25", time: "23:00", title: "미국 5월 미시건 소비심리",    country: "US", importance: "medium" },
    { date: "2024-05-28", time: "22:00", title: "미국 5월 CB 소비자신뢰지수", country: "US", importance: "medium" },
    { date: "2024-05-30", time: "21:30", title: "미국 1분기 GDP (수정)",       country: "US", importance: "high"   },
    { date: "2024-05-31", time: "21:30", title: "미국 4월 개인소비지출",        country: "US", importance: "high"   },
  ],
  alerts: [
    { id: 1, level: "danger",  category: "target",    title: "목표 현금비율 미달",  message: "현재 10.1% (목표 15%)",   is_read: false, created_at: "2024-05-24 08:35" },
    { id: 2, level: "warning", category: "target",    title: "월 투자 목표 미달",   message: "W 8.2M / W 10M (-18.0%)", is_read: false, created_at: "2024-05-24 08:30" },
    { id: 3, level: "info",    category: "macro",     title: "VIX 낮은 수준",      message: "14.32 (전일 대비 -2.51%)", is_read: true,  created_at: "2024-05-24 08:25" },
    { id: 4, level: "warning", category: "macro",     title: "환율 변동 상대",      message: "USD/KRW 1,364.20 (▲3.10)", is_read: false, created_at: "2024-05-24 08:20" },
    { id: 5, level: "danger",  category: "portfolio", title: "S&P 500 하락",       message: "-0.45% (전일 대비)",       is_read: false, created_at: "2024-05-24 01:00" },
  ],
  insights: {
    macroSummary: "물가 상승률이 둔화되고 있으며 금리 인상 속도가 완화될 전망입니다.",
    portfolioSummary: "총자산은 전일 대비 +0.26% 변동했습니다.",
    marketRisk: "현재 시장 위험도는 보통 수준입니다.",
    recommendation: "PCE 물가지수 발표 전 포지션 비중을 점검하고 현금 비중을 유지하십시오.",
  },
};

interface DashboardClientProps {
  initialData: DashboardSummary | null;
}

export default function DashboardClient({ initialData }: DashboardClientProps) {
  const [data, setData] = useState<DashboardSummary>(initialData ?? MOCK_DATA);
  const [loading, setLoading] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(new Date().toLocaleTimeString("ko-KR"));
  const [apiError, setApiError] = useState(!initialData);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const fresh = await api.getDashboardSummary();
      setData(fresh);
      setLastUpdate(new Date().toLocaleTimeString("ko-KR"));
      setApiError(false);
    } catch {
      setApiError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  // 5분마다 자동 갱신
  useEffect(() => {
    const id = setInterval(refresh, 5 * 60 * 1000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="space-y-4">
      {apiError && (
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg px-4 py-2.5 flex items-center justify-between">
          <p className="text-yellow-400 text-sm">
            ⚠️ API 서버에 연결할 수 없어 샘플 데이터를 표시합니다.{" "}
            <code className="text-xs bg-yellow-500/10 px-1 rounded">uvicorn api.main:app --reload</code> 실행 후 새로고침하세요.
          </p>
          <button onClick={refresh} className="text-xs text-yellow-400 hover:text-yellow-300 ml-4">
            재시도
          </button>
        </div>
      )}

      {/* 상단 우측 갱신 */}
      <div className="flex items-center justify-end gap-2 text-xs text-slate-500">
        <span>마지막 업데이트: {lastUpdate}</span>
        <button
          onClick={refresh}
          disabled={loading}
          className="flex items-center gap-1 text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
        >
          {loading ? "⟳" : "↻"} 새로고침
        </button>
      </div>

      {/* KPI Bar */}
      <KPIBar kpi={data.kpi} targets={data.targets} />

      {/* 3열 메인 레이아웃 (목업 기준) */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* 왼쪽 열: 매크로 + 시스템 상태 + Top Movers */}
        <div className="space-y-4">
          <MacroPanel indicators={data.macro} />
          <SystemStatusPanel />
          <TopMoversPanel movers={data.topMovers} />
        </div>

        {/* 가운데 열: 계좌 현황 + 리밸런싱 + 자료 */}
        <div className="space-y-4">
          <AccountPanel accounts={data.accounts} allocation={data.allocation} />
          <SuggestionPanel suggestions={data.suggestions} targets={data.targets} />
          <DocumentsPanel />
        </div>

        {/* 오른쪽 열: 목표/괴리 + 캘린더 + 알림 */}
        <div className="space-y-4">
          <TargetPanel targets={data.targets} />
          <CalendarPanel events={data.calendar} />
          <AlertPanel alerts={data.alerts} />
        </div>
      </div>

      {/* 인사이트 (full width) */}
      <InsightPanel insights={data.insights} />

      {/* 하단: 점검 포인트 + 운영 메모 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="md:col-span-2">
          <DailyCheckPanel />
        </div>
        <MemoPanel />
      </div>
    </div>
  );
}
